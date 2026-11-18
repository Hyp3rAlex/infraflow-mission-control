"""Minimal Jira Cloud REST v3 client.

Credentials come from environment variables only (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN).
Reads are always allowed. Writes are refused unless the client was created with
``allow_write=True``; the CLI sets that only for ``--apply`` together with INFRAFLOW_ALLOW_WRITE=1.

Endpoints used (documented at developer.atlassian.com/cloud/jira/platform/rest/v3):
  POST /rest/api/3/search/jql          enhanced JQL search, paged with nextPageToken
  POST /rest/api/3/issue               create issue
  GET/POST /rest/api/3/issue/{key}/transitions
  POST /rest/api/3/issue/{key}/comment
  GET  /rest/api/3/filter/search, POST /rest/api/3/filter
"""
from __future__ import annotations

import os
import time
from typing import Callable, Iterator

import requests


class JiraError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class JiraAuthError(JiraError):
    """401: credentials missing, wrong or expired."""


class JiraPermissionError(JiraError):
    """403: authenticated but not allowed."""


class JiraRateLimitError(JiraError):
    """429 persisted after all retries."""


class WriteNotAllowed(JiraError):
    """A write was attempted on a read-only (dry-run) client."""


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, session=None, allow_write: bool = False,
                 max_retries: int = 4, sleep: Callable[[float], None] = time.sleep, timeout: float = 30):
        if not base_url.startswith("https://"):
            raise JiraError("JIRA_BASE_URL must be an https:// URL.")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.auth = (email, token)
        self.allow_write, self.max_retries, self.sleep, self.timeout = allow_write, max_retries, sleep, timeout

    @classmethod
    def from_env(cls, allow_write: bool = False, env=None, **kw) -> "JiraClient":
        env = os.environ if env is None else env
        missing = [k for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN") if not env.get(k)]
        if missing:
            raise JiraAuthError("Jira is not configured: set " + ", ".join(missing) + " in the environment (see .env.example).")
        return cls(env["JIRA_BASE_URL"], env["JIRA_EMAIL"], env["JIRA_API_TOKEN"], allow_write=allow_write, **kw)

    # ---- transport ---------------------------------------------------------
    def _request(self, method: str, path: str, write: bool = False, **kw) -> dict:
        if write and not self.allow_write:
            raise WriteNotAllowed(f"Refused {method} {path}: client is read-only. Use --apply with INFRAFLOW_ALLOW_WRITE=1.")
        last = "no attempt"
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, self.base_url + path, auth=self.auth, timeout=self.timeout,
                                            headers={"Accept": "application/json"}, **kw)
            except requests.RequestException as exc:           # network error: retry
                last = f"network error: {exc}"
                if attempt < self.max_retries:
                    self.sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code == 401:
                raise JiraAuthError("Jira rejected the credentials (401). Check JIRA_EMAIL and JIRA_API_TOKEN.", 401)
            if resp.status_code == 403:
                raise JiraPermissionError(f"Jira refused {method} {path} (403): missing permission.", 403)
            if resp.status_code == 429 or resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
                if attempt < self.max_retries:
                    retry_after = resp.headers.get("Retry-After", "")
                    self.sleep(min(float(retry_after), 60) if retry_after.replace(".", "", 1).isdigit() else min(2 ** attempt, 30))
                continue
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    detail = "; ".join(body.get("errorMessages", []) + [f"{k}: {v}" for k, v in body.get("errors", {}).items()])
                except ValueError:
                    detail = resp.text[:200]
                raise JiraError(f"Jira returned {resp.status_code} for {method} {path}: {detail}", resp.status_code)
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()
        if last == "HTTP 429":
            raise JiraRateLimitError(f"Rate limited on {method} {path} after {self.max_retries + 1} attempts.", 429)
        raise JiraError(f"{method} {path} failed after {self.max_retries + 1} attempts ({last}).")

    # ---- reads ---------------------------------------------------------------
    def search(self, jql: str, fields: list[str] | None = None, page_size: int = 50) -> Iterator[dict]:
        """Yield every issue matching the JQL, following nextPageToken until the last page."""
        token, seen_tokens = None, set()
        while True:
            body = {"jql": jql, "maxResults": page_size, "fields": fields or ["summary", "status", "priority", "duedate", "labels", "assignee", "updated"]}
            if token:
                body["nextPageToken"] = token
            page = self._request("POST", "/rest/api/3/search/jql", json=body)
            yield from page.get("issues", [])
            token = page.get("nextPageToken")
            if not token or page.get("isLast") is True:
                return
            if token in seen_tokens:
                raise JiraError("Pagination did not advance (repeated nextPageToken).")
            seen_tokens.add(token)

    def find_by_label(self, project: str, label: str) -> list[dict]:
        return list(self.search(f'project = {project} AND labels = "{label}"'))

    def list_filters(self, name: str = "") -> list[dict]:
        out, start = [], 0
        while True:
            page = self._request("GET", "/rest/api/3/filter/search", params={"filterName": name, "startAt": start, "maxResults": 50, "expand": "jql"})
            out += page.get("values", [])
            if page.get("isLast", True) or not page.get("values"):
                return out
            start += len(page["values"])

    # ---- writes (need allow_write) ----------------------------------------------
    def create_issue(self, fields: dict) -> dict:
        return self._request("POST", "/rest/api/3/issue", write=True, json={"fields": fields})

    def transition(self, key: str, status_name: str) -> None:
        options = self._request("GET", f"/rest/api/3/issue/{key}/transitions").get("transitions", [])
        match = [t for t in options if t.get("to", {}).get("name") == status_name]
        if not match:
            raise JiraError(f"{key}: no transition leads to status '{status_name}'.")
        self._request("POST", f"/rest/api/3/issue/{key}/transitions", write=True, json={"transition": {"id": match[0]["id"]}})

    def add_comment(self, key: str, adf_body: dict) -> dict:
        return self._request("POST", f"/rest/api/3/issue/{key}/comment", write=True, json={"body": adf_body})

    def create_filter(self, name: str, jql: str, description: str = "") -> dict:
        return self._request("POST", "/rest/api/3/filter", write=True, json={"name": name, "jql": jql, "description": description})


def simplify(issue: dict) -> dict:
    """Reduce a REST issue to the fields the reconciliation needs."""
    f = issue.get("fields", {})
    return dict(key=issue.get("key"), summary=f.get("summary"), status=(f.get("status") or {}).get("name"),
                priority=(f.get("priority") or {}).get("name"), duedate=f.get("duedate"), labels=sorted(f.get("labels") or []),
                assignee=(f.get("assignee") or {}).get("displayName") if f.get("assignee") else None, updated=f.get("updated"))
