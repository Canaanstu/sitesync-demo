"""Vercel entrypoint: Vercel's FastAPI support serves the `app` exported here with original request paths."""
from app.main import app  # noqa: F401
