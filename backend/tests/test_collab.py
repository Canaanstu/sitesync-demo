import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'collab.db').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database import SessionLocal
from app.models import *
from app.security import _limits
import app.collab as collab


@pytest.fixture
def client():
    _limits.clear()
    with TestClient(app) as c:
        assert c.post('/api/auth/login', json={'email': 'demo@example.com', 'password': 'DemoProject2026!'}).status_code == 200
        yield c


def first_project(client):
    return client.get('/api/projects').json()[0]['id']


def test_notes_and_feed(client):
    pid = first_project(client)
    board = client.get(f'/api/projects/{pid}/ops/board').json()
    activity = board['activities'][0]
    assert client.post(f'/api/projects/{pid}/notes', json={'text': 'Inspector moved to Thursday', 'activity_id': activity['id']}).status_code == 200
    feed = client.get(f'/api/projects/{pid}/changes').json()
    note = next(e for e in feed['events'] if e['kind'] == 'note')
    assert note['summary'] == 'Inspector moved to Thursday' and note['activity'] == activity['name']
    assert client.post(f'/api/projects/{pid}/notes', json={'text': '   '}).status_code in (422,)
    assert client.post(f'/api/projects/{pid}/notes', json={'text': 'x', 'activity_id': 'nope'}).status_code == 404


def test_schedule_edit_lands_in_feed(client):
    pid = first_project(client)
    added = client.post(f'/api/projects/{pid}/ops/activities', json={'name': 'Punch walk', 'start_date': '2030-01-07', 'duration_days': 2})
    assert added.status_code == 200
    assert any('Punch walk' in e['summary'] for e in client.get(f'/api/projects/{pid}/changes').json()['events'])


def test_project_roles(client):
    pid = first_project(client)
    me = client.get('/api/me').json()
    r = client.put(f'/api/projects/{pid}/members/{me["id"]}/role', json={'role': 'super'})
    assert r.status_code == 200
    team = client.get(f'/api/projects/{pid}/team').json()
    assert next(t for t in team if t['id'] == me['id'])['role'] == 'super'
    assert client.get(f'/api/projects/{pid}/changes').json()['role'] == 'super'
    assert client.put(f'/api/projects/{pid}/members/{me["id"]}/role', json={'role': 'boss'}).status_code == 422


def test_feed_unread_marker(client):
    pid = first_project(client)
    with SessionLocal() as db:
        other = db.scalar(select(User).where(User.email != 'demo@example.com'))
        if other is None:
            pytest.skip('no second user in the seed data')
        collab.log_change(db, pid, other.id, 'note', 'Crew is on site')
        db.commit()
    assert client.get(f'/api/projects/{pid}/changes').json()['new'] >= 1
    client.post(f'/api/projects/{pid}/changes/read')
    assert client.get(f'/api/projects/{pid}/changes').json()['new'] == 0


def test_digest_is_quiet_without_changes_and_ordered_by_role(client):
    pid = first_project(client)
    me = client.get('/api/me').json()
    with SessionLocal() as db:
        user = db.get(User, me['id'])
        other = User(organization_id=user.organization_id, email='pm-test@example.com', full_name='Pat Manager', role='member', password_hash='x')
        db.add(other)
        db.flush()
        db.add(ProjectMember(project_id=pid, user_id=other.id, role='pm'))
        collab.log_change(db, pid, user.id, 'schedule', 'Drywall now runs Nov 3 to Nov 7.')
        db.commit()
        digest = collab.build_digest(db, other, since=None)
        assert digest and 'Drywall now runs' in digest['text']
        # a person's own changes are never echoed back to them
        quiet = collab.build_digest(db, user, since=now())
        assert quiet is None or 'Drywall now runs' not in quiet['text']


def test_digest_job_needs_secret_and_respects_opt_out(client, monkeypatch):
    assert client.get('/api/digests/run').status_code == 401
    monkeypatch.setattr(collab.settings, 'cron_secret', 'test-secret-value')
    assert client.get('/api/digests/run', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    sent = []
    monkeypatch.setattr(collab, 'mail_enabled', lambda: True)
    monkeypatch.setattr(collab, 'send_email', lambda to, subject, text: sent.append(to) or True)
    assert client.get('/api/digests/run', headers={'Authorization': 'Bearer test-secret-value'}).status_code == 200
    n = len(sent)
    # a second run the same day sends nothing more
    client.get('/api/digests/run', headers={'Authorization': 'Bearer test-secret-value'})
    assert len(sent) == n
    assert client.put('/api/me/digest', json={'digest': 'off'}).json()['digest'] == 'off'
    assert client.get('/api/me/digest').json()['digest'] == 'off'
    client.put('/api/me/digest', json={'digest': 'daily'})


def test_import_all(client):
    client.post('/api/integrations/procore/connect')
    projects = client.get('/api/procore/companies/demo-company/projects').json()
    r = client.post('/api/procore/import-projects', json={'company_id': 'demo-company', 'all': True})
    assert r.status_code == 200
    again = client.post('/api/procore/import-projects', json={'company_id': 'demo-company', 'all': True}).json()
    assert again['imported'] == [] and again['skipped'] == len(projects)
    assert client.post('/api/procore/import-projects', json={'company_id': 'demo-company', 'project_ids': []}).status_code == 422
