import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'orgs.db').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.security import _limits

PASSWORD = 'a-long-test-password'


@pytest.fixture(autouse=True)
def open_signup(monkeypatch):
    _limits.clear()
    monkeypatch.setattr(settings, 'open_signup', True)


def signup(c, email, name='Some Person', **extra):
    return c.post('/api/auth/signup', json={'email': email, 'full_name': name, 'password': PASSWORD, **extra})


def test_company_name_at_signup_and_invite_code_is_admin_only():
    with TestClient(app) as owner:
        r = signup(owner, 'boss@acme.test', 'Boss Person', company='Acme Builders')
        assert r.status_code == 200
        assert owner.get('/api/me').json()['organization_name'] == 'Acme Builders'
        org = owner.get('/api/organizations/current').json()
        assert org['name'] == 'Acme Builders' and len(org['invite_code']) == 11
        with TestClient(app) as mate:
            signup(mate, 'mate@acme.test', 'Mate Person', invite_code=org['invite_code'])
            assert 'invite_code' not in mate.get('/api/organizations/current').json()


def test_teammates_share_projects_and_tasks_across_the_company():
    with TestClient(app) as owner, TestClient(app) as mate:
        signup(owner, 'o@shared.test', 'Owner Person', company='Shared Co')
        code = owner.get('/api/organizations/current').json()['invite_code']
        r = signup(mate, 'm@shared.test', 'Mate Person', invite_code=code.lower())
        assert r.status_code == 200 and r.json()['role'] == 'member'
        assert mate.get('/api/me').json()['organization_name'] == 'Shared Co'
        owner_projects = {p['id'] for p in owner.get('/api/projects').json()}
        assert owner_projects and {p['id'] for p in mate.get('/api/projects').json()} == owner_projects
        # the joiner did not get a second copy of the sample projects
        assert len(owner_projects) == 2
        pid = next(iter(owner_projects))
        risk = next(x for x in owner.get(f'/api/projects/{pid}/risks').json() if x['status'] == 'open')
        # a teammate clears a task; the owner sees it cleared
        assert mate.post(f'/api/projects/{pid}/risks/{risk["id"]}/resolve', json={}).status_code == 200
        seen = {x['id']: x['status'] for x in owner.get(f'/api/projects/{pid}/risks').json()}
        assert seen[risk['id']] == 'resolved'
        # and new projects reach existing members
        new = owner.post('/api/projects', json={'name': 'Fresh Job'}).json()
        assert new['id'] in {p['id'] for p in mate.get('/api/projects').json()}


def test_bad_invite_code_is_rejected_without_creating_an_account():
    with TestClient(app) as c:
        assert signup(c, 'nope@x.test', invite_code='NOPE0-NOPE0').status_code == 404
        assert c.post('/api/auth/login', json={'email': 'nope@x.test', 'password': PASSWORD}).status_code == 401


def test_rotating_the_invite_code_invalidates_the_old_one():
    with TestClient(app) as owner:
        signup(owner, 'rot@x.test', company='Rotate Co')
        old = owner.get('/api/organizations/current').json()['invite_code']
        new = owner.post('/api/organizations/invite-code').json()['invite_code']
        assert new != old
        with TestClient(app) as c:
            assert signup(c, 'late@x.test', invite_code=old).status_code == 404
            assert signup(c, 'late@x.test', invite_code=new).status_code == 200


def test_existing_account_can_join_a_company_and_leave_its_solo_workspace():
    with TestClient(app) as owner, TestClient(app) as solo:
        signup(owner, 'own@join.test', company='Join Co')
        code = owner.get('/api/organizations/current').json()['invite_code']
        signup(solo, 'solo@join.test', 'Solo Person')
        assert solo.post('/api/organizations/join', json={'invite_code': code, 'password': 'wrong-password-123'}).status_code == 403
        assert solo.post('/api/organizations/join', json={'invite_code': 'AAAAA-AAAAA', 'password': PASSWORD}).status_code == 404
        r = solo.post('/api/organizations/join', json={'invite_code': code, 'password': PASSWORD})
        assert r.status_code == 200 and r.json()['organization_name'] == 'Join Co'
        me = solo.get('/api/me').json()
        assert me['role'] == 'member' and me['organization_name'] == 'Join Co'
        assert {p['id'] for p in solo.get('/api/projects').json()} == {p['id'] for p in owner.get('/api/projects').json()}
        # a company with several people cannot be abandoned this way
        assert solo.post('/api/organizations/join', json={'invite_code': code, 'password': PASSWORD}).status_code == 409
        with TestClient(app) as other_owner:
            signup(other_owner, 'other@join.test', company='Other Co')
            assert solo.post('/api/organizations/join', json={'invite_code': other_owner.get('/api/organizations/current').json()['invite_code'], 'password': PASSWORD}).status_code == 403


def test_viewers_cannot_clear_tasks_and_members_added_by_admin_see_projects():
    with TestClient(app) as owner:
        signup(owner, 'adm@v.test', company='View Co')
        pid = owner.get('/api/projects').json()[0]['id']
        owner.post('/api/organizations/members', json={'email': 'view@v.test', 'full_name': 'View Only', 'password': PASSWORD, 'role': 'viewer'})
        with TestClient(app) as v:
            assert v.post('/api/auth/login', json={'email': 'view@v.test', 'password': PASSWORD}).status_code == 200
            assert pid in {p['id'] for p in v.get('/api/projects').json()}
            risk = v.get(f'/api/projects/{pid}/risks').json()[0]
            assert v.post(f'/api/projects/{pid}/risks/{risk["id"]}/resolve', json={}).status_code == 403
