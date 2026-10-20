# Bluebeam Studio demo

In Tools, open **Bluebeam Studio → Explore sample connection**. A company administrator can connect sample data, choose a Studio sample project and a SiteSync project, then import or refresh three fictional drawing records. Open Project documents to review revision, discipline, source identifier and refresh time. Refresh is idempotent; disconnect retains imported metadata.

This is a simulated, read-only metadata connector. It makes no Bluebeam calls, stores no OAuth credentials, downloads no PDFs and cannot create sessions, upload files or change markups. Sample records contain no drawing text for AI retrieval. Browser-only builds reset sample state on reload; backend deployments retain metadata in their configured database.

Implementation: `backend/app/bluebeam.py`, `frontend/components/bluebeam-integration.tsx`, and `frontend/lib/bluebeam-demo.ts`. Live deployments with DEMO_MODE=false refuse sample connection/import requests. Tenant/project access and connection ownership are enforced by the backend.

Before real integration: obtain authorized Bluebeam developer access, register the correct regional OAuth callback, implement single-use state and encrypted server-side token storage/refresh, select minimum read-only scopes, validate company/project permissions, implement pagination/retries and incremental synchronization, and expose verified Studio source links. Do not substitute demo source identifiers for real links.

Official authentication documentation: https://support.bluebeam.com/developer/authentication-guide.html
