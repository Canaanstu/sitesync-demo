import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'signup.db').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import SessionLocal
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


# ---- email verification, password reset, account deletion ----
from app import main as app_main
from app.models import User
from app.security import mail_token, token_for


@pytest.fixture
def outbox(monkeypatch):
    _limits.clear()
    monkeypatch.setattr(settings, 'open_signup', True)
    monkeypatch.setattr(settings, 'resend_api_key', 'test-key')
    monkeypatch.setattr(settings, 'mail_from', 'SiteSync <no-reply@example.com>')
    sent = []
    monkeypatch.setattr(app_main, 'send_email', lambda to, subject, text: sent.append((to, subject, text)) or True)
    return sent


def token_from(text):
    return text.split('token=')[1].split()[0]


def test_email_features_off_without_a_mail_provider(open_signup):
    with TestClient(app) as c:
        assert c.get('/api/health').json()['email_enabled'] is False
        r = signup(c, 'nomail@example.com')
        assert r.json()['email_verified'] is True and r.json()['verification_sent'] is False
        assert c.post('/api/auth/forgot', json={'email': 'nomail@example.com'}).status_code == 503


def test_signup_sends_verification_and_link_verifies(outbox):
    with TestClient(app) as c:
        assert c.get('/api/health').json()['email_enabled'] is True
        r = signup(c, 'verify.me@example.com')
        assert r.json()['email_verified'] is False and r.json()['verification_sent'] is True
        assert c.get('/api/me').json()['email_verified'] is False
        to, subject, text = outbox[-1]
        assert to == 'verify.me@example.com' and '/verify/?token=' in text
        assert c.post('/api/auth/verify', json={'token': token_from(text)}).status_code == 200
        assert c.get('/api/me').json()['email_verified'] is True
        assert c.post('/api/auth/verify', json={'token': 'garbage'}).status_code == 400


def test_resend_verification(outbox):
    with TestClient(app) as c:
        signup(c, 'resend.me@example.com')
        before = len(outbox)
        assert c.post('/api/auth/resend-verification').status_code == 200
        assert len(outbox) == before + 1


def test_password_reset_flow(outbox):
    with TestClient(app) as old, TestClient(app) as c:
        signup(old, 'forgetful@example.com')
        outbox.clear()
        assert c.post('/api/auth/forgot', json={'email': 'forgetful@example.com'}).status_code == 200
        assert c.post('/api/auth/forgot', json={'email': 'nobody-here@example.com'}).status_code == 200
        assert len(outbox) == 1
        token = token_from(outbox[0][2])
        assert c.post('/api/auth/reset', json={'token': token, 'password': 'short'}).status_code == 422
        new = 'a-brand-new-password-1'
        assert c.post('/api/auth/reset', json={'token': token, 'password': new}).status_code == 200
        # one-time use, and older sessions stop working
        assert c.post('/api/auth/reset', json={'token': token, 'password': 'another-password-123'}).status_code == 400
        assert old.get('/api/me').status_code == 401
        assert c.post('/api/auth/login', json={'email': 'forgetful@example.com', 'password': PASSWORD}).status_code == 401
        assert c.post('/api/auth/login', json={'email': 'forgetful@example.com', 'password': new}).status_code == 200


def test_mail_tokens_cannot_be_used_as_sessions(outbox):
    with TestClient(app) as c:
        signup(c, 'tokens@example.com')
        with SessionLocal() as db:
            user = db.scalar(__import__('sqlalchemy').select(User).where(User.email == 'tokens@example.com'))
            forged = mail_token('verify', user, 1, email=user.email)
        with TestClient(app) as other:
            other.cookies.set('session', forged)
            assert other.get('/api/me').status_code == 401


def test_delete_account_removes_workspace(open_signup):
    with TestClient(app) as c:
        signup(c, 'bye@example.com')
        assert c.request('DELETE', '/api/me', json={'password': 'wrong-password-123'}).status_code == 403
        assert c.request('DELETE', '/api/me', json={'password': PASSWORD}).status_code == 200
        assert c.get('/api/me').status_code == 401
    with SessionLocal() as db:
        from sqlalchemy import select
        assert db.scalar(select(User).where(User.email == 'bye@example.com')) is None
    with TestClient(app) as c:
        assert c.post('/api/auth/login', json={'email': 'bye@example.com', 'password': PASSWORD}).status_code == 401


def test_demo_owner_cannot_delete_itself():
    _limits.clear()
    with TestClient(app) as c:
        assert c.post('/api/auth/login', json={'email': 'demo@example.com', 'password': 'DemoProject2026!'}).status_code == 200
        assert c.request('DELETE', '/api/me', json={'password': 'DemoProject2026!'}).status_code == 403
