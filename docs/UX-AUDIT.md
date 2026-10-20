# SiteSync UX audit

Done by walking the running app (desktop, light and dark) and reading the sample data against how a construction PM would judge it, plus two rounds of outside feedback. Status is as of this commit.

## What testers said works
- The multi-project overview and per-project status at a glance.
- Looks professional and is easy to navigate.

## Findings

| # | Finding | Why a PM would care | Status |
|---|---|---|---|
| 1 | Sample data contradicted itself: a tile install 25% done that starts next week; lighting controls due on site 9 days after the ceiling work that uses them begins; millwork ordered before its shop drawings were approved; the spa project (Sage and Sound) was a copy of the retail project, including emails naming Alo. | A construction reader stops trusting everything else the moment one date is impossible. | Fixed. A test now fails if any sample project is internally inconsistent. |
| 2 | Nothing explained how a task is identified or how to resolve it. | Testers could not tell what the system was doing a layer or two below the status. | Fixed. Every task has "Why am I seeing this?", the help button is now a real guide, and each check states what it looks at and when it clears. |
| 3 | Exceptions were only visible one project at a time, with one layer of detail. | The value for a PM is the exception plus the reasoning behind it. | Fixed. Dashboard > Exceptions lists all open items, most urgent first, and each opens to: why it was flagged, the records it is based on, and the work it affects and how soon. |
| 4 | Checks were hard-wired. | Every firm runs its own way (lookahead windows, what counts as "released", how urgent an overdue submittal is). | Fixed for the six built-in checks: Project > Settings > Rules. Not yet: custom checks, org-wide defaults. |
| 5 | AI chat looked broken after the first answer. | The panel did not scroll to the new answer, showed no "working" state, and put errors out of sight. | Fixed, plus a Clear chat button and a plain-lookup fallback when a model is busy. |
| 6 | Logo intro text was invisible in dark mode and the "y" was clipped. | First impression. | Fixed. |
| 7 | Three different counts for "what needs attention": bell (8, things due within a week), Exceptions tab (11), Overview ("11 to tackle"). | Looks like a bug even though each is correct. | Not fixed. Recommend labeling the bell "Due this week" or merging it into one number. |
| 8 | Greeting says "Good evening, Schimenti": the sample user's name is the company name. | Reads as a mistake in a customer demo. | Not fixed. Give the sample user a person's name. |
| 9 | "Confirm your email" banner shows on every page of a demo account that cannot confirm. | Constant noise in a sales demo. | Not fixed. Hide it for sample workspaces. |
| 10 | Same thing is called Tasks (project), Exceptions (dashboard) and Risks (internally and in the API). | Vocabulary should match the job. | Partly. Recommend picking one word with a construction PM. |
| 11 | Phone layout could not be rendered in this environment (the app correctly refuses to be framed and the window resize does not change the viewport). Checked by reading the CSS only. | Testers used phones. | Needs a real-device pass, especially the bottom dock overlapping lists and the new Exceptions rows. |

## Recommendations for customer demos
1. Lead with the Exceptions tab and open one all the way down. No other tool in this price range shows the reasoning behind a flag.
2. Then History: import the sample past-projects workbook and ask "what should I watch on this project". This is the part that is unique.
3. Ask one construction professional to review the vocabulary and the six checks. Likely additions: long-lead / buyout flags, submittal "ball in court" aging, RFI days open, and the standard 3-week lookahead layout.
4. Replace sample data with the prospect's own first. A 10-minute spreadsheet import of their real schedule beats any sample.

## Limits to be honest about
- The free AI model path is tested against a simulated server, not a live provider (no key was available).
- "Late" and "duration" in History use planned/expected dates unless the spreadsheet has actual-date columns. Imports now read them, and the app records actual dates as deliveries arrive and work completes, so this improves with use.
