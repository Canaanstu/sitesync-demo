# Share the free SiteSync demo

The repository's render.yaml deploys one free Docker web service. The landing page is public; project records require sign-in. It uses fictional project data and temporary SQLite storage. No persistent disk or paid instance is requested.

## Deploy

1. In Render, create a Blueprint from the private Canaanstu/sitesync-demo repository, branch main, using render.yaml at the repository root.
2. Name the Blueprint sitesync-demo. Confirm the service uses the Free plan and has no disk or paid resources before creating it.
3. Wait for the Docker build and health check. Render supplies the public HTTPS URL.
4. In the service Environment settings, copy the generated PRIVATE_DEMO_PASSWORD privately. Sign in at /login with demo@example.com and that password. The published local-development password is disabled.
5. Create member or viewer accounts for teammates and grant project access. All account changes and project edits are temporary on this free deployment.

## Resettable data and startup

Render free services sleep after 15 minutes without traffic and can take about one minute to wake. Local database changes are lost on sleep, restart, or redeployment. SiteSync seeds fresh fictional Alo Yoga and Sage and Sound projects when the database is recreated. Share /login rather than a project deep link, since project IDs can change. Generated service secrets remain in Render's environment.

The app displays a resettable-demo notice. Launch-form entries are also temporary: use fictional addresses when testing. This deployment must not be authoritative storage for launch requests or contractor data.

Provider integrations and AI are simulated. Carrier updates are manual. Email sending is simulated. Public visitors cannot access project records without a valid account.

## Optional persistent hosting later

To retain edits, use a paid compute plan and a persistent disk mounted at /var/data, set SITESYNC_DATA_DIR=/var/data, DATABASE_URL=sqlite:////var/data/construction.db, and EPHEMERAL_DEMO=false. Review and approve charges first. Real production use requires separate production infrastructure and authorized integrations.

References: https://render.com/docs/free and https://render.com/docs/blueprint-spec
