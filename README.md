# SiteSync - construction project intelligence

A separate application built from `../handoff (1).md`, expanded with the SiteSync operational demo. The existing Ramirez Rod site is unchanged. The demo uses Schimenti Construction Company, Sage and Sound, and Alo Yoga in Greenwich, Connecticut. All project records and contacts are fictional; turnover dates are editable demo assumptions.

## Run the included demo

Requires Python 3.12+ and Node.js 22+. No API keys, Redis, Docker, or paid services are needed for demo mode.

In a terminal:

```powershell
cd construction-ai/backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd construction-ai/frontend
npm install
npm run dev
```

Use `pnpm install --ignore-workspace` and `pnpm dev` if you prefer pnpm; a lockfile is included. On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python`.

Open **http://localhost:3000**. Demo login:

- Email: `demo@example.com`
- Password: `DemoProject2026!`

After installing dependencies, Windows users can also run `./start-demo.ps1` from `construction-ai` to start both servers in the background. It prints the started process IDs and writes logs under `backend/.local`. Use `./start-demo.ps1 -ProductionBuild` after building the frontend to preview the optimized app. This launcher also recognizes the bundled Codex Node.js runtime.

The backend seeds fictional projects with dates relative to its first startup. Data persists in `backend/.local/construction.db`. Local signing and encryption secrets are generated in that same ignored directory. This directory is private development state, not a deployable artifact. All provider calls are disabled when `DEMO_MODE=true`.

The local app uses FastAPI + SQLAlchemy + SQLite and Next.js + React + TypeScript + Tailwind + TanStack Query. Production configuration uses PostgreSQL/pgvector and Redis/RQ. React component state handles ephemeral interface state.

`backend/requirements.lock.txt` records the exact tested Python packages; install it instead of `requirements.txt` for the tested environment.

## API-key guide

Open `output/pdf/sitesignal-api-keys-and-setup.pdf` for a six-page credential walkthrough with official links, exact callbacks, environment variables, and the live-mode runbook. The editable source is `scripts/create-guide.py`. Configuration starts in `backend/.env.example`.

## What works

| Area | Implemented behavior |
| --- | --- |
| Auth | Bcrypt passwords, expiring HTTP-only signed session cookie, login throttling, owner bootstrap, logout cookie removal |
| Organization | Rename workspace, create admin/member/viewer users, project membership and role restrictions |
| Projects | Portfolio, create blank/sample projects, import Procore projects idempotently |
| Procore | Demo connection and live OAuth authorization-code exchange, encrypted tokens, refresh, companies/projects, paginated RFI/submittal reads |
| Microsoft | Demo connection and live OAuth, refresh, paginated last-30-days mail sync, explicit alias matching, read-only workbook downloads |
| Uploads | CSV/XLSX procurement and schedules, flexible headers, row validation, PDF/TXT extraction, page-aware chunks, file/expansion limits |
| Risk engine | Late release, delivery after related work, RFI/upcoming work match, overdue submittal, approval blocking procurement, email review signal |
| Decisions | Inspect evidence, resolve/dismiss/reopen; manual decisions preserved across reruns |
| AI | Grounded local demo summaries, OpenAI and optional Anthropic adapters, source-ID validation, no-evidence response, prompt/response audit, organization request counter/rate limit |
| Drafts | Narrative RFIs with PNG/JPEG/PDF/TXT attachments, trade and directory-based distribution, editable/exportable drafts; Outlook compose and approved Microsoft interface send |
| Schedule | AI proposals in live mode, labeled templates in demo, working-day dependency validation, reviewed baseline replacement, progress updates and inspection/material holds |
| Procurement | Incoming package register, carrier links, ETA updates, full-receipt reconciliation, schedule-linked material needs |
| Agents | Daily deterministic coordinator recalculated on refresh; inspection research with official-source links, live OpenAI web search when configured |
| Documents | Source viewer, keyword retrieval; optional 1,536-dimensional OpenAI embeddings with project-filtered pgvector similarity |
| Background work | RQ queue, sync status, configurable 10-1,440 minute scheduler, retries for provider throttling, normalized upserts |
| Admin | Integration status/test/disconnect, matching aliases, workbook mappings, project grants, organization usage count |

### Try the complete workflow

1. Sign in, then open the Alo Yoga sample project.
2. Review the risk register and click a source chip to inspect the record.
3. Open Integrations and connect the two demo providers.
4. Import the Harbor House project from the demo Procore company.
5. Upload `samples/procurement.csv`, `samples/schedule.csv`, or `samples/coordination-notes.txt`.
6. Run the risk engine, ask “Which RFIs need attention?”, and inspect answer sources.
7. Generate an email/RFI draft, edit it, and copy it. No message is sent.
8. Add a viewer under organization settings and grant a project under project settings.

Sample CSV dates are fixed examples; seeded project dates are relative. Update CSV dates when demonstrating later.

## Live setup

1. Copy `backend/.env.example` to `backend/.env`.
2. Set `DEMO_MODE=false`, explicit `JWT_SECRET` and `TOKEN_ENCRYPTION_KEY`, and `BOOTSTRAP_EMAIL`/`BOOTSTRAP_PASSWORD` for an **empty** live database. Do not reuse the demo database.
3. Add the desired provider credentials and model IDs. The defaults follow the handoff; confirm account/model availability in your provider dashboard.
4. Provision PostgreSQL + pgvector and Redis, or use Docker Compose below.
5. Run `alembic upgrade head` from `backend` before starting a live API.
6. Run the API, RQ worker, scheduler, and frontend. Configure `API_INTERNAL_URL` on the frontend if the API is not at `http://127.0.0.1:8000`.
7. Complete provider consent in Integrations, import a project, and sync.

Local callback URLs:

```text
http://localhost:8000/api/integrations/procore/callback
http://localhost:8000/api/integrations/microsoft/callback
```

For production, use one HTTPS browser origin for Next.js and its `/api` proxy. Set **both** `APP_URL` and `API_URL` to that public origin; `API_INTERNAL_URL` points to the private FastAPI service. Register the resulting public callback URLs in both provider portals. `APP_ENV=production` requires HTTPS, strong secrets, Postgres, and demo mode off. Secrets must match across the API, worker, and scheduler; never publish `.env` or `.local`.

### Docker infrastructure and backend

Set the backend environment first, including explicit shared keys, then from `construction-ai`:

```sh
docker compose up --build
```

This runs Postgres, Redis, the migration, API, worker, and scheduler. Run the frontend separately. Containers bind database/API/Redis ports to loopback for local development. Use managed secrets, TLS, private networks, and real database passwords for deployment. Do not use the Compose default database password outside local development.

Without Docker, start an RQ worker with `rq worker --url <REDIS_URL> default`, and a scheduler with `python -m app.scheduler`. Prefer the Linux container worker on Windows. The scheduler checks project intervals once a minute; jobs have a 20-minute timeout. A stale in-progress job is marked failed after 30 minutes by the scheduler.

### Cloud workbook mappings

Project Settings > Advanced accepts:

```json
[
  {"drive_id":"YOUR_DRIVE_ID","item_id":"YOUR_ITEM_ID","kind":"procurement-log"},
  {"drive_id":"YOUR_DRIVE_ID","item_id":"YOUR_OTHER_ITEM_ID","kind":"schedule"}
]
```

Get those IDs through Microsoft Graph for a file the connected user may read. The app downloads and parses the first worksheet; it does not invoke Excel workbook row APIs or request file-write access. Graph uses the configured delegated scopes. `Mail.Send` is absent by default. To enable reviewed interface sends, add it to `MICROSOFT_SCOPES`, set `ENABLE_EMAIL_SEND=true`, and reconnect the Microsoft account. Keep `DEMO_MODE=true` for demonstrations; all sends remain simulated.

### Upload behavior

- Procurement requires Item, Status, Lead Time, Required On Site. Optional vendor, expected delivery, release date, notes, and submittal number.
- Schedule requires Activity Name, Start Date, Finish Date. Optional activity ID, trade, percent complete, predecessor/successor lists.
- Dates accept ISO or US month/day/year. Procurement lead time is an integer number of calendar days; schedule progress is 0-100.
- The entire batch validates before commit. Referenced submittals must exist in the same project. Repeat identical file uploads upsert identical source rows; a changed file is a separate upload. Cloud workbook rows upsert by workbook and row index; removed source rows are not automatically deleted.
- Documents support text PDFs/TXT, 10 MB upload limits, 300 PDF pages, and 2 MB extracted text. Scans require OCR before upload. Originals are not retained; extracted text and page chunks are stored.
- Live document ingestion queues embeddings if OpenAI is configured; keyword search works before embeddings finish. Anthropic-only mode uses keyword retrieval.

## API

Interactive API schema: **http://localhost:8000/docs**. Routes are under `/api`; the source defines all handoff Phase 1 endpoints plus login/logout, project creation, members, usage, source views, history, and settings. Requests from browser mutations must match `APP_URL`. All project access is checked server-side against organization and membership.

The `POST /organizations` route completes organization setup by renaming the signed-in user's organization. New enterprise tenants are provisioned outside the self-service UI. Self-registration is deliberately not exposed.

## Validation

```powershell
cd backend
.venv\Scripts\python -m pytest -q
cd ../frontend
npm run typecheck
npm run build
```

`scripts/browser-check.cjs` exercises the demo through Chromium/Edge: login, dashboards, uploads, connections, project import, sync, source viewing, chat, drafting, resolve/reopen, and mobile overflow. Set `PLAYWRIGHT_MODULE` to your installed Playwright package; the default points at the bundled workstation runtime. Start both app servers first.

Tests cover the actual risk rules and workflow boundaries rather than snapshot-only rendering. Provider tests are mocked: successful demo tests do not validate a real Procore tenant, Microsoft tenant, AI account, or production infrastructure.

## Limits and remaining phases

- This is a runnable MVP, not a certified production deployment. Perform a real sandbox integration and security review before using contractor data.
- Procore documents/drawings, webhook handling, automatic OCR, Procore write-back, enterprise SSO/SAML, Teams notifications, historical intelligence, and specialized superintendent/procurement/closeout agents remain later-phase work from the handoff.
- No automatic Procore writes exist. Email sending requires explicit review and approval. The demo never transmits email. No financial approvals, mobile app, BIM analysis, P6, or ERP integration is added.
- The legacy risk engine uses keyword matches and calendar dates. The Schedule tab separately validates dependency graphs and selected workdays. Forecasts remain conditional on unconfirmed inspections, delivery estimates and actual field progress. Email signals are review items, not confirmed delays.
- Project aliases may match more than one project. Administrators should use specific matching phrases and review results.
- Model source IDs are checked, but semantic factual accuracy still requires human review. Retrieval considers up to 3,000 rows per record type and 12 evidence items per answer.
- Secrets remain server-side; provider OAuth tokens are encrypted in the database. Production database/backups encryption, network controls, external grant revocation, and key rotation are deployment responsibilities.
- Disconnect deletes local tokens. Revoke the app in the provider portal to revoke the external authorization grant. JWT logout clears the cookie; already stolen JWTs remain valid until their eight-hour expiry. Password reset, session revocation, MFA, user deletion, and invitation email flows are not implemented.
- Audit prompts and answers persist with project data. Retention/deletion/export policies, backup restores, privacy agreements, tenant provisioning, usage billing, and observability still need operational implementation.
- Sync is request-driven and scheduled with RQ. Source deletions and incremental delta/webhook ingestion are not implemented; mailbox sync reads a rolling 30-day window.
- Schema is intentionally portable between the demo and PostgreSQL: UUIDs and timestamps are represented as strings, array-like fields as JSON. Database isolation relies on scoped API checks rather than Postgres RLS. Alembic's initial migration creates the versioned MVP schema; add new migrations for future model changes.

The credential guide contains the current official source links used for setup. No real accounts, secrets, external messages, or deployment were created as part of this build.


## SiteSync operational demo

Open a project and use **Schedule**, **Procurement**, **RFI studio**, and **Agents**.

- Schedule: set dates and workdays; describe scope; review/edit proposed durations; approve the baseline. Old activities remain as history. Re-link procurement and inspection holds after a baseline replacement. Update progress and inspection appointments as field work changes. The board and coordinator recompute every minute while open, on mutation, and when reopened on a new day. This is not an unattended booking or email service.
- Procurement: enter a verified vendor email, link installation activities, then add packages and tracking numbers. Carrier links open the carrier website; no live carrier polling is configured. Unknown ETAs remain unknown. All registered packages must be received before the material is marked delivered. Do not mark a partial receipt as a full delivery.
- RFI studio: supply description plus up to five PNG/JPEG/text-PDF/TXT files (10 MB combined). Demo drafting formats your description and does not analyze images; live OpenAI drafting can use the images. Anthropic currently uses extracted document text only. Review inferred trade, job type, technical facts and recipients. Save edits before exporting or preparing email. Originals are stored privately in the project-scoped workflow database and downloadable by authorized project members. This differs from the older document-index upload, which only retains extracted text.
- Directory: manage architect, engineer, project manager and vendor contacts under Agents. Distribution uses actual saved addresses, never guesses at real addresses. Reserved example.com addresses must be replaced before live sending.
- Email: Needs attention → Draft follow-up, or RFI studio → Email saved RFI. Edit recipients and content, open Outlook, or review and approve an interface send. Outlook links cannot attach files; download and attach them manually. Interface sends include small attachments (3 MB combined base64 limit). A Microsoft 202 response means accepted, not delivered. Ambiguous timeouts are not automatically retried. Check Outlook Sent Items before retrying an unknown/failed message. OAuth uses the organization’s connected mailbox, not an arbitrary From address.
- Research: Greenwich has a saved official-source reference checked 2026-09-29. It describes City Squared and the published 2 PM cutoff for next-business-day requests; it does not claim typical appointment availability. Live research uses OpenAI web search when demo mode is off and an OpenAI key is configured. Research never books inspections or changes dates automatically.

Existing live databases require `alembic upgrade head` for the workflow table. Demo databases are upgraded automatically. New routes are grouped under `/api/projects/{project_id}/ops` and enforce project access and write roles.

Run `node scripts/operations-check.cjs` with both servers running for browser validation of the new screens. Backend workflow tests cover dependency cycles, calendars, partial package receipts, scoped attachment access, distribution and stale/replayed mail approvals. The original API-key PDF predates these features; the Mail.Send instructions above supplement that read-only guide.
