# SiteSync launch page

The public landing page is at `/` (also `/launch`). Existing application routes and `/login` remain available. No account is required to submit interest. Copy explicitly identifies the beta and integrations as in development.

`POST /api/launch/requests` accepts company email, optional company name, demo/launch interest, and explicit contact consent. Email and company name are encrypted using the existing backend encryption key. Duplicate requests with the same normalized email and interest are ignored. No confirmation email or outbound notification is sent. Requests persist in the configured database; preserve its storage and encryption key.

There is intentionally no public or shared-demo-account listing of leads. An operator with backend access can export them locally:

```
python export_launch_requests.py --output .local/launch-requests.csv
```

Run from `backend`; the output must not already exist. Keep exports private. The CSV escapes spreadsheet formula prefixes. Do not put contact lists in public assets or Git.

Demo startup creates the new table. Live deployments must run `alembic upgrade head`, including migration 003. Hosting must keep the database and encryption key persistent. Localhost is only accessible on the host machine. The existing password-protected demo tunnel remains password-protected; creating this page does not remove that gate or publish a permanent public website.

Validation: backend tests cover real encrypted persistence in an isolated database, validation, consent, duplicates, honeypot handling, and absence of public reads. `scripts/landing-check.cjs` checks responsive layout and both signup flows using mocked submissions so QA contacts are not added to the actual launch list.
