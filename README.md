# SiteSync demo

SiteSync helps commercial construction teams review schedule blockers, procurement, submittals, inspections, and RFI drafts. This repository contains the complete Next.js frontend and FastAPI backend.

## Hosted demo

Deploy the repository root as a Render Blueprint using `render.yaml`. The configuration runs both servers in one Docker service and stores demo data on a persistent disk. Review the service and disk charges before confirming deployment.

Read [the hosting guide](deploy/PRIVATE-HOSTING.md) for setup and credentials. The landing page is at `/`; the app is at `/login`. Render creates the HTTPS address during deployment.

The hosted demo uses fresh fictional Schimenti projects for Alo Yoga and Sage and Sound. Provider connections and email sending are simulated. Project data requires sign-in; the owner password is generated in Render. The published local development password does not work in hosted mode.

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
