import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'signup.db').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.security import _limits

PASSWORD = 'a-long-test-password'


@pytest.fixture
def open_signup(monkeypatch):
    _limits.clear()
    monkeypatch.setattr(settings, 'open_signup', True)


def signup(c, email='new.user@example.com', name='New User', password=PASSWORD):
    return c.post('/api/auth/signup', json={'email': email, 'full_name': name, 'password': password})


def test_signup_is_closed_by_default():
    _limits.clear()
    with TestClient(app) as c:
        assert c.get('/api/health').json()['signup_open'] is False
        assert signup(c).status_code == 403


def test_signup_creates_private_seeded_workspace(open_signup):
    with TestClient(app) as c:
        assert c.get('/api/health').json()['signup_open'] is True
        r = signup(c)
        assert r.status_code == 200 and r.json()['role'] == 'owner'
        me = c.get('/api/me').json()
        assert me['email'] == 'new.user@example.com'
        names = sorted(p['name'] for p in c.get('/api/projects').json())
        assert names == ['Alo Yoga', 'Sage and Sound']
        assert c.get('/api/organizations/current').json()['name'] == "New's workspace"


def test_workspaces_are_isolated_and_login_works(open_signup):
    with TestClient(app) as a, TestClient(app) as b:
        signup(a, 'one@example.com', 'One Person')
        signup(b, 'two@example.com', 'Two Person')
        pa = {p['id'] for p in a.get('/api/projects').json()}
        pb = {p['id'] for p in b.get('/api/projects').json()}
        assert pa and pb and not pa & pb
        assert a.get(f'/api/projects/{next(iter(pb))}').status_code in (403, 404)
    with TestClient(app) as c:
        assert c.post('/api/auth/login', json={'email': 'one@example.com', 'password': PASSWORD}).status_code == 200
        assert c.post('/api/auth/login', json={'email': 'one@example.com', 'password': 'wrong-password-123'}).status_code == 401


def test_signup_validation_and_duplicates(open_signup):
    with TestClient(app) as c:
        assert signup(c, 'dupe@example.com').status_code == 200
        assert signup(c, 'dupe@example.com').status_code == 409
        assert signup(c, 'DUPE@example.com').status_code == 409
        assert signup(c, 'demo@example.com').status_code == 409
        assert signup(c, 'not-an-email').status_code == 422
        assert signup(c, 'short@example.com', password='short').status_code == 422
        assert signup(c, 'blank@example.com', name=' ').status_code == 422


def test_signup_throttle(open_signup, monkeypatch):
    from sqlalchemy import func, select
    from app.database import SessionLocal
    from app.models import Organization
    with SessionLocal() as db:
        existing = db.scalar(select(func.count()).select_from(Organization))
    monkeypatch.setattr(settings, 'signups_per_hour', existing + 1)
    with TestClient(app) as c:
        assert signup(c, 'first-throttle@example.com').status_code == 200
        assert signup(c, 'second-throttle@example.com').status_code == 429
