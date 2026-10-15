# Verification record



Verified locally on September 29, 2026 using the bundled Windows runtime.



- Backend: `python -m pytest -q` - **26 passed**. One upstream Starlette warning recommends its newer httpx2 test transport; no test failure.

- Frontend: `tsc --noEmit` - **passed**.

- Optimized Next.js build: **passed**, Next.js 15.5.26.

- Browser workflow on the optimized app: **passed**, no page errors, no horizontal document overflow at 390px.

- Browser coverage: login, project overview, email drafting, document upload, project chat, source viewer, demo Procore/Microsoft connections, Procore import, sync, risk resolve, risk reopen.

- Desktop and mobile screenshots inspected in `tmp/` (ignored QA output).

- API-key PDF: six pages rendered with Poppler and visually inspected; no clipped text or overlapping layout.

- Windows background launcher: **passed**, starts API and optimized frontend with logs in `backend/.local`.



Backend tests include six deterministic rules, repeat upload/risk behavior, encrypted tokens, OAuth replay/expiry, refresh-token rotation, tenant/project isolation, viewer restrictions, spreadsheet mapping/errors, source validation, mocked connector/model requests, empty-project health, and PostgreSQL vector-query SQL compilation.



Not exercised: real OAuth consent or paid AI requests, live Procore/Graph data shapes and permissions, a running PostgreSQL/Redis/Docker stack, production hosting, enterprise identity, or production performance/security review. Live credentials were not provided. The PostgreSQL vector query was compiled, not run against a server.



The supplied data, integrations, and AI summaries remain explicitly in demo mode. Source screenshots contain only fictional sample records.





## SiteSync operational update - September 29, 2026



- Light-blue brand, SS/buildings logo, Schimenti workspace and Greenwich project defaults verified in the browser.

- New workflow backend tests: working-day dependencies and cycles, baseline approval/replay, inspection forecast holds, progress bounds, partial/full package receipts and unknown ETAs, RFI attachments and trade-based distribution, cross-project attachment denial, email review revisions/replay, unknown Microsoft send outcomes without retry, and viewer restrictions.

- `scripts/operations-check.cjs`: passed on the production build. Covers schedule preview with edited duration, package creation, RFI generation with a text attachment and description-only input, automatic electrical distribution, approved simulated send, official-source research, populated Outlook compose URL and mobile overflow. No browser page errors.

- Screenshots visually checked: Schedule, RFI studio and mobile Schedule. Table and project-tab overflow scroll within their own containers on mobile.

- The new live send transport was tested with a mocked timeout; no actual email was sent. Live AI/image analysis, OAuth consent and carrier status integrations were not exercised. Demo images are attached but not analyzed. Carrier statuses are team-entered.



## Demo bug audit

Fixed imported activity durations counting nonworking days, ordered packages being labeled in transit, premature manual delivery bypassing package receipts, and confirmed inspections missing an appointment date. API validation messages now explain the specific input error; non-JSON server errors have a readable message.

Verification: 26 backend tests pass; production build passes; full operations browser walkthrough passes. The new `scripts/bug-check.cjs` also passes schedule application, invalid-inspection correction, ordered-package status, blocked premature delivery, receipt clearing schedule holds, and logout. No browser page errors. The isolated QA project was archived and temporary test packages removed. Real provider sends remain untested; email is simulated.

## Job-site usability update — September 30, 2026

Preserved existing screens, navigation, grid structure, and component order. Increased body text to 16px and secondary text to at least 15px; darkened foreground colors while retaining light-blue surfaces; enlarged existing controls to 44–48px minimum targets; restored strong keyboard focus. Natural wrapping and vertical growth accommodate the larger text.

Added shared dialog keyboard behavior and explicit discard confirmation, saved-RFI guards, two-step package receipt, and schedule preview/approval invalidation after edits. Clarified construction terminology, simulated connections, inspection-research limitations, email approval/results, and risk-score meaning.

`scripts/ux-check.cjs` checks login and 13 workspace views at 1440px, 768px, and 390px (42 combinations), plus dialog focus/escape/restoration, draft protection, receipt confirmation, edited schedule approval, and RFI save/email behavior. Mutating workflow responses are mocked: it does not alter project records or send emails. Demo authentication and existing project reads use the local API. Run with `UX_PREVIEW_URL=http://localhost:3000` against the production preview. Screenshots and measurements are written to `tmp/ux-review/`.

Browser results: no JavaScript page errors, full-page horizontal overflow, text below 15px, or controls below the 44px minimum in those views. This is an automated and visual review, not a formal accessibility certification or a test with physical gloves and assistive-technology users.

## Desktop and tablet workflow redesign — October 1, 2026

Implemented the six-tab project navigation, attention-first Overview, Schedule inspection views and blocker signals, Procurement conflict/incoming/received views, single-column RFI drafting/history, shared source-linked assistant, touch controls, upload previews, and undo for progress and receipts. Preserved the blue brand, existing fonts, and approval-before-send behavior.

- Optimized Next.js production build: passed, including TypeScript validation.
- `scripts/redesign-check.cjs`: passed against the production preview. This is the current browser regression script; earlier browser scripts above document historical layouts and contain superseded selectors and receipt-confirmation expectations.
- Verified progress and receipt undo payloads, inspection calendar and activity links, RFI quick picks, file selection and drag/drop previews, draft/save guards, and assistant source expansion.
- Checked Schedule, Procurement, RFIs, Agents, and More at 1440px, 1024px, and 768px: no JavaScript page errors, horizontal page overflow, or visible interaction targets below 48px in these views.
- Visually inspected real demo Schedule desktop and Procurement tablet captures. Screenshots and machine-readable checks are in `output/ux-redesign/`.

The workflow test mocks mutations and assistant responses; it reads local demo data but does not send email or change project records. Live OAuth, provider sends, and AI image analysis were not exercised. Demo photos are attached but not analyzed, as explained in the RFI form. This is not formal accessibility certification or physical job-site testing.

## Simpler daily workflow — October 5, 2026

Separated the daily Overview from a searchable Projects directory and added a sidebar Tutorial. Removed raw evidence JSON from next-step dialogs; recommendations now use event type and linked source names. Added distinct urgency and record-type chips, calendar date editing, completion rings, and sticky/outside-click/Escape dismissal for the assistant, including while requests run.

Completion is the average recorded percentage across active activities, not a risk score or an elapsed-time estimate. Explicit inspection/delivery milestone mappings derive 0/100 completion from current evidence and reopen if that evidence changes. Prerequisite links cannot complete the installation they hold. Field/imported activity percentages remain supported. The live Procore schedule/document connector is still outside the implemented scope.

Validation: the existing 26 backend tests passed; two additional tests passed for evidence completion/reopening, calendar validation, cross-project isolation, and prerequisite protection. TypeScript and optimized build passed. `scripts/simplicity-check.cjs` verifies distinct screens, search, tutorial, recommendations without raw JSON, mocked calendar saves, sticky/busy/outside chat dismissal, and no full-page overflow at 1440/1024/768px. Screenshots are in `output/simplicity/`. Calendar grids scroll horizontally on narrower screens. Browser mutations and AI answers are mocked; no external messages are sent.

## Launch landing page - October 13, 2026

Production build and signup persistence test passed. scripts/landing-check.cjs passed desktop (1440), tablet (768), and phone (390) checks, both interest modes, required consent, error preservation and retry, success confirmation, and no browser page errors. Submissions in browser QA are mocked; actual encrypted persistence, duplicate handling, validation and absence of a public listing are tested in an isolated database. The page is available at / and /launch; no permanent external deployment was performed. See deploy/LANDING-PAGE.md for private lead export and migration details.

## Landing-page refinement - October 14, 2026

Preserved brand palette, fonts and disclaimers. Unified demo CTAs, shortened hero preview, quiet integrations line, connected workflow snippets, spaced contractor band, accessible FAQ before the form, inline email/consent errors, and sticky navigation/form with responsive fallbacks. scripts/landing-refinement-check.cjs verifies CTA preselection, FAQ ARIA/order, validation/success, preview fit at 1440x900, sticky behavior and overflow at 1440/768/375. Browser submissions are mocked; no outbound messages or real signup records are created by this test. Signup backend behavior is unchanged.

## Procurement/submittal workflow — October 15, 2026
- Added project-scoped submittal links and inline evidence, nullable lead time, planning release-by dates, combined procurement review/edit, and consistent receipt totals.
- Added regression coverage for cross-project rejection, preserving omitted links, explicit unlinking, unknown lead time, and release date calculation.
- 13 targeted backend tests passed. TypeScript check and production build passed. Local demo started for browser checks.
- Live Procore field mapping and external-party access were not tested; these changes use records already available in SiteSync.
- Browser verification: procurement opened for Alo Yoga and Sage and Sound; Alo linked-submittal evidence and combined editor verified; 1440/1024/768/390px procurement checks showed no document overflow. No captured browser errors. Broader all-screen audit remains outstanding.
