#!/usr/bin/env python3
"""Print a strong random secret for CRON_SECRET (or JWT_SECRET, etc.).

    python3 deploy/gen-secret.py             # print one
    python3 deploy/gen-secret.py | pbcopy    # macOS: copy it without showing it

Paste it into Vercel as an environment variable (mark it Sensitive). Never commit it."""
import secrets

print(secrets.token_urlsafe(48))
