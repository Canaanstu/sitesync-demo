# SiteSync demo

SiteSync helps commercial construction teams review schedule blockers, procurement, submittals, inspections, and RFI drafts. This repository contains the complete Next.js frontend and FastAPI backend.

## Free hosted demo

Deploy the repository root as a Render Blueprint using `render.yaml`. The configuration runs both servers in one Docker service and stores fictional demo data temporarily. The service uses Render’s Free plan with no persistent disk. Data resets on sleep, restart, or deployment.

Read [the hosting guide](deploy/PRIVATE-HOSTING.md) for setup and credentials. The landing page is at `/`; the app is at `/login`. Render creates the HTTPS address during deployment.

The hosted demo uses fresh fictional Schimenti projects for Alo Yoga and Sage and Sound. Provider connections and email sending are simulated. Project data requires sign-in; the owner password is generated in Render. The published local development password does not work in hosted mode.

## Vercel deployment (frontend + backend + Postgres)

Live: https://sitesync-demo.vercel.app (sign in at `/login`). Two Vercel projects, deployed with the CLI from each folder (`vercel deploy --prod`):

- `sitesync-api` (root `backend/`): FastAPI served by `index.py`, with Neon Postgres from the Vercel Marketplace. Tables and demo data are created on the first request, guarded by a Postgres advisory lock so concurrent cold starts cannot seed twice.
- `sitesync-demo` (root `frontend/`): Next.js. `API_INTERNAL_URL` points at the API project; `/api/*` is proxied so the session cookie stays same-origin.

Visitors create their own account at `/signup` (`OPEN_SIGNUP=true`). Sign-up asks for a company name and creates that company's organization, seeded with the fictional sample projects, so different companies cannot see or change each other's data. Everyone in a company shares its projects and tasks: an owner or admin finds the company invite code in Settings, and a teammate enters it at sign-up (or via `/signup?invite=CODE`), or in Settings if they already have an account and are alone in their own workspace. New members are granted every company project, and an admin can still revoke one in project settings. Existing databases gain the `organizations.invite_code` column automatically on the next request (and via Alembic revision 005). Sign-ups are rate limited and capped (`SIGNUPS_PER_HOUR`, `MAX_ORGANIZATIONS`). Email verification, password reset and account deletion are built in. Email delivery needs a provider: set `RESEND_API_KEY` + `MAIL_FROM` (a sender on a domain verified in Resend), or `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD` + `MAIL_FROM`. Without one, new accounts are marked verified and the forgot-password link is hidden. Keep the site to fictional or test data. Deploy both projects with `bash deploy/deploy-vercel.sh` (after `npx vercel@latest login`).

Production env vars on `sitesync-api`: `APP_ENV=hosted-demo`, `DEMO_MODE=true`, `PRIVATE_DEMO=true`, `ENABLE_EMAIL_SEND=false`, `APP_URL`, `API_URL`, plus `PRIVATE_DEMO_PASSWORD` (20-72 bytes), `JWT_SECRET` and `TOKEN_ENCRYPTION_KEY`. Neon supplies `DATABASE_URL`/`POSTGRES_URL`. Vercel request bodies are capped near 4.5 MB, so large uploads are limited. There is no background scheduler on Vercel; use Vercel Cron if scheduled sync is needed.

## Static demo on GitHub Pages

https://canaanstu.github.io/sitesync-demo/ is a static build with no backend. It uses recorded fictional data (`frontend/lib/demo-data.json`) and an in-browser mock API (`frontend/lib/mock-api.ts`). Tasks, schedule progress and deliveries work and reset on reload; uploads, new projects and AI answers are disabled. `.github/workflows/pages.yml` deploys it on pushes to `main` (Settings → Pages → Source must be "GitHub Actions"). To refresh the data, run a freshly seeded local backend and `python deploy/record-demo-fixtures.py`. Build locally with `SITESYNC_STATIC=true NEXT_PUBLIC_STATIC_DEMO=true NEXT_PUBLIC_BASE_PATH=/sitesync-demo npx next build` in `frontend`.

## Local development

From the cloned repository root, start the backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000/login. Local-only demo credentials: `demo@example.com` / `DemoProject2026!`. On macOS/Linux use `.venv/bin/python`.

## Validation

Backend: run `python -m pytest -q` from `backend` using the virtual environment. Frontend: run `npm run typecheck` and `npm run build` from `frontend`.

See [validation notes](VALIDATION.md) and [landing-page behavior](deploy/LANDING-PAGE.md). Local tests do not verify live Procore/Microsoft authorization or cloud deployment.

## Data and approvals

Keep `.env`, `.local`, credentials, databases, and contact exports out of Git. AI drafts require human review. Procurement lead times and carrier updates depend on recorded source information. Received materials do not prove installation complete. Use approved integrations and separate production infrastructure before handling real contractor records.

## Working together

- **Schedule first.** Every project opens on its Schedule: a "Next 7 days" card, a quick note box (type or tap the mic to dictate; saved with the time, optionally tied to an activity), and "What changed".
- **Project roles.** An admin sets each person to Superintendent, Project manager or Team member in Project settings → Access. Roles do not limit editing; they decide what the daily summary leads with (the super sees what is due, the PM sees what changed).
- **Bulk import.** Projects → Import → tick several projects or press "Import all". Projects already imported are skipped.
- **Daily summary, not a flood.** People get at most one email a day, only when something changed, and can turn it off in Settings. Syncs only add a feed entry when their result differs from the last one. Sending needs mail configured (see above) and `CRON_SECRET` set on the API project: `backend/vercel.json` calls `/api/digests/run` daily at 13:00 UTC, and the endpoint answers only to that secret. Without mail, the summary preview in Settings still shows what would be sent.

## Procore integration

SiteSync talks to Procore through OAuth (`backend/app/connectors.py`): Connect → pick company → import project → sync RFIs and submittals.

**Free: Procore Developer Sandbox.** Any developer can use it, no Procore customer account needed.

1. Sign up at [developers.procore.com](https://developers.procore.com), create an app, and wait a few minutes. A sandbox with a "1234 – Sandbox Test Project" (one RFI, one submittal, eight schedule tasks) is created automatically, and you get an email to set its password.
2. On the app's Credentials tab, copy the **Sandbox** Client ID and Secret. Add `<API_URL>/api/integrations/procore/callback` as a redirect URI (for local development: `http://localhost:8000/api/integrations/procore/callback`).
3. Set on the backend:
   ```
   PROCORE_ENV=sandbox            # uses login-sandbox.procore.com and sandbox.procore.com
   PROCORE_CLIENT_ID=...
   PROCORE_CLIENT_SECRET=...
   PROCORE_GRANT=authorization_code   # or client_credentials: no sign-in page, uses the app's service account
   ```
4. In SiteSync open Tools → Connect, then Projects → Import. Procore calls are real even with `DEMO_MODE=true`; email and Microsoft stay simulated.

**Adding teammates to the sandbox.** Only the app creator exists in a Developer Sandbox. A teammate who tries to connect sees "email address or password is not valid" and gets no reset email, because Procore sends nothing for unknown accounts. Add them once in the sandbox: sign in at `sandbox.procore.com`, open Company Tools → **Directory** → add their email, then they use the emailed link to set a sandbox password (one time only). The version must also be installed in the sandbox company once (Company Tools → Admin → **App Management** → Install App → Install Custom App, paste the Sandbox Installation Key from the app's page). Real customers never see this: they sign in with their normal Procore account.

Sandbox data is test data and cannot be refreshed. Register another app to get a clean sandbox (it has a new company id).

**For a Procore customer.** A Company Admin has two options, both testing against the customer's own data:

- **On-Demand Sandbox**: self-enabled in Procore Explore, with several allowed in parallel. Procore recommends it for most testing. Install the app with the *Production* installation key; the integration then uses the *Production* Client ID/Secret.
- **Monthly Sandbox**: enabled in company General Settings and refreshed monthly from production, one per company.

Keep `PROCORE_ENV=sandbox` while testing; the customer's sandbox uses the same sandbox hosts. For production use, set `PROCORE_ENV=production` (or leave it empty) with `DEMO_MODE=false`. That requires Procore's verification and production access, or a private install into the customer's own account. Check the Procore Marketplace and API terms before storing customer records.

## Free AI model

SiteSync's chat and History agent work with any OpenAI-compatible endpoint, so no paid key is needed.

Quickest: create a free key at [console.groq.com/keys](https://console.groq.com/keys) and set one variable on the backend:

```
GROQ_API_KEY=...
```

That selects Groq's `llama-3.3-70b-versatile`. For anything else (OpenRouter `:free` models, Google's OpenAI-compatible endpoint, or a local Ollama), set:

```
AI_PROVIDER=compatible
LLM_BASE_URL=https://openrouter.ai/api/v1      # or http://localhost:11434/v1 for Ollama
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
LLM_API_KEY=...                                 # not needed for a local Ollama
```

Free tiers are rate limited and may use your prompts to improve their models, so check each provider's terms before sending real client data. A local Ollama keeps everything on your machine. If the model is busy or answers badly, SiteSync falls back to a plain lookup of your records instead of failing.
