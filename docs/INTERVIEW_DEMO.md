# Three-minute demonstration

Goal: show one infrastructure demand travelling from request to management report, with numbers that can be checked. Five blocks of 30 to 45 seconds. All data is synthetic (fictional "Orion Systems Engineering"), cutoff 2026-11-16.

The Atlassian site is private. In person, use the live site; otherwise use the screenshots in [the gallery](DEMO.md) in the same order (image numbers in brackets).

## Before starting (5 minutes)

1. Open five browser tabs:
   - Jira dashboard "InfraFlow | Demand Operations";
   - Jira issue KAN-13;
   - Confluence: Decision Register > Decision Brief - ORION-REQ-017;
   - Confluence: Weekly Portfolio Review - 2026-11-16;
   - the Jira board.
2. Open `reports/infraflow_management_workbook.xlsx` on the Forecast sheet, and `presentations/infraflow_executive_briefing.pptx` on slide 1.
3. In a terminal in the repository, run `.venv/bin/python -m pytest -q` once. Note the "passed" count.
4. Live Jira lists with relative dates (overdue, last 30 days) move with the calendar. If a live count differs from the 2026-11-16 report, say so.

## Script

**0:00-0:30 · The portfolio (Jira dashboard [01, 02]).**
1. Click the dashboard tab.
2. Say: "Fifty synthetic infrastructure demands from four sites. The dashboard runs on saved JQL filters: thirty-seven open, by status and priority."
3. Scroll to "Management attention": "Twenty demands that are overdue, unowned, blocked or need a finance review, each with an owner and a date."

**0:30-1:15 · One demand (KAN-13 [06, 07]).**
1. Click KAN-13.
2. Say: "The flight-test data team needs about 40 terabytes more encrypted storage by 18 December."
3. Expand the description.
4. Point to the gate check: "Option A costs €48,000 and 300 hours. The cost centre has €23,950 headroom, and the storage team has 180 unallocated hours before the due date. A fails both gates. Option B archives old campaign data for €14,500 and 160 hours. It fits, but frees only about 40% and needs the data owners' retention sign-off."

**1:15-2:00 · The decision (Confluence decision brief [08, 09]).**
1. Click the decision brief tab.
2. Say: "The score is 82, top band, but the score only orders the review. The board chair deferred the request to 8 December, with a reason, an owner and a review date."
3. Point to the what-if: "Releasing 120 hours of run work would fix capacity for A, but not funding."

**2:00-2:30 · Money and capacity (Excel [14, 15]).**
1. Show the Forecast sheet.
2. Say: "Forecast at completion €936,700 against €1,050,000. Actuals, plus open purchase orders, plus approved work without an order. Invoiced amounts are never counted twice. One cost centre is €3,800 over."
3. Switch to the Capacity sheet: "Network and Access is 30 hours over-allocated in December."

**2:30-3:00 · Management reporting (Confluence weekly review [10, 13], slide 1 [19]).**
1. Show the weekly review.
2. Say: "The weekly review and the slide deck show the same numbers. They are marked provisional because six data errors were found. For example, a US-dollar invoice has no approved conversion rate, so it is shown as USD 5,000 and never added to the euro figures. The financial table is a snapshot; the lists at the bottom are live Jira queries."

## Questions to expect

| Question | Answer |
|---|---|
| How do you know the numbers are right? | 179 automated tests. Totals are checked against values the data generator tallies independently, plus a hand-calculated ledger. Jira was compared field by field with the data set: no differences. Excel recalculated the formula workbook: 27 of 27 checks OK. |
| Is the report generated from Jira? | No. Money and hours are not in Jira. The Office files come from the data set. Jira is compared with the data set through recorded snapshots, and Confluence shows live Jira lists next to the static figures. |
| What does Jira not enforce? | The approval gates. The Free plan has no workflow validators, so the gates are process rules, enforced in the Python model. |
| What is simulated? | The company, the people (roles only), all amounts and hours, and the status history before the issues were created. |
| Did you find mistakes in your own work? | Yes. An early report added a USD invoice to euro amounts. I separated currencies and added tests that fail if they are mixed. Charts showed overlapping labels in Excel; the cause was a missing chart setting, fixed in the generator. |
| What would you do next? | Fix one saved filter that has a wrong query, run the REST client against the live site with an API token, and add a second cutoff to show a trend. |
| Did you use AI? | Yes, an AI coding assistant wrote most of the code and documents under my direction. I can explain the model, the formulas and the test strategy, and I checked the results in Jira, Confluence and Office myself. |

Answer the last question in your own words.
