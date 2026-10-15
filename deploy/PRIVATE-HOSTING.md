# Share SiteSync with your team

This package deploys the complete demo, with a sign-in-protected HTTPS URL and a persistent SQLite disk. The website address itself is reachable from the internet; project records require a valid account. It is not a VPN-only service.

## Publish

1. Create a **private GitHub repository**. Upload the contents of `construction-ai` at the repository root. Exclude `.env`, `.local`, `.venv`, `node_modules`, `.next`, `tmp`, and local databases. Keep the included `.gitignore` and `.dockerignore`.
2. Sign in at https://dashboard.render.com. Choose **New → Blueprint**, connect that private repository, and use `render.yaml`.
3. Review Render's quoted service and disk costs before confirming. The configuration uses one 0.5 CPU / 512 MB web service (`0.5c-512mb`) and a 1 GB persistent disk. No paid service has been created by preparing these files.
4. Wait for the deployment to become healthy. Render supplies the `https://...onrender.com` URL; no domain purchase is required.
5. In the Render service's Environment settings, reveal the generated `PRIVATE_DEMO_PASSWORD`. Sign in with `demo@example.com` and that password. Do not put the password in source code or a public message.
6. In SiteSync's organization Settings, create an individual account for each teammate. Use `member` for editing or `viewer` for read-only access. Grant each account project access in the project's Settings tab. Share the URL and each person's credentials through your usual private channel. Keep the owner password to yourself.

## What remains simulated

The hosted demo seeds fresh fictional Schimenti projects. It does not upload your local database, attachments, real mailbox or credentials. AI uses demo templates; interface email sends are simulated. Inspection references are advisory, and carrier updates are manual.

The known local password `DemoProject2026!` is disabled for private hosting, the login screen does not prefill it, and authentication cookies require HTTPS. API records enforce organization/project access. Secrets are generated in Render and persist across deployments. Changing the private owner password updates that account on restart; to invalidate existing sessions, rotate `JWT_SECRET` too.

Only one replica should use this SQLite disk. Back up the disk before destructive changes. For a real production rollout, use the app's separate live configuration, PostgreSQL, approved provider connections and a deployment/security review.

## Verification status

Local authentication tests and frontend type checks can be run before upload. The Docker image and Render deployment must still be built and verified in the hosting account; a prepared configuration is not a published link.

References: https://render.com/docs/blueprint-spec and https://render.com/docs/disks
