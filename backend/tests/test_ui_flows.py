"""Every action a signed-in person can take in the app, driven with the same payloads the frontend sends."""
import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'flows.db').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.security import _limits

PASSWORD = 'a-long-test-password'
SAMPLES = Path(__file__).resolve().parents[2] / 'samples'


@pytest.fixture
def c(monkeypatch):
    _limits.clear()
    monkeypatch.setattr(settings, 'open_signup', True)
    with TestClient(app) as client:
        r = client.post('/api/auth/signup', json={'email': f'flows{os.urandom(3).hex()}@example.com', 'full_name': 'Flow Tester', 'password': PASSWORD, 'company': 'Flow Co'})
        assert r.status_code == 200, r.text
        yield client


def ok(r, code=200):
    assert r.status_code == code, f'{r.request.method} {r.request.url.path} -> {r.status_code} {r.text[:300]}'
    return r.json()


def project(c, name='Alo Yoga'):
    return next(p['id'] for p in ok(c.get('/api/projects')) if p['name'] == name)


def test_risk_actions_round_trip(c):
    pid = project(c)
    risks = ok(c.get(f'/api/projects/{pid}/risks'))
    assert risks
    for action, status in [('resolve', 'resolved'), ('reopen', 'open'), ('dismiss', 'dismissed'), ('reopen', 'open')]:
        assert ok(c.post(f'/api/projects/{pid}/risks/{risks[0]["id"]}/{action}', json={}))['status'] == status
    assert c.post(f'/api/projects/{pid}/risks/{risks[0]["id"]}/bogus', json={}).status_code == 404
    ok(c.post(f'/api/projects/{pid}/risks/run', json={}))
    assert next(p for p in ok(c.get('/api/projects')) if p['id'] == pid)['risk_count'] >= 1


def test_drafts_and_mail(c):
    pid = project(c)
    ops = f'/api/projects/{pid}/ops'
    risk = ok(c.get(f'/api/projects/{pid}/risks'))[0]
    for task in ('draft-email', 'draft-rfi', 'explain-risk'):
        ok(c.post(f'/api/projects/{pid}/ai/{task}', json={'risk_id': risk['id']}))
    ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'What is late?'}))
    assert ok(c.get(f'/api/projects/{pid}/ai/history'))
    mail = ok(c.post(f'{ops}/mail/prepare', json={'risk_id': risk['id']}))
    reviewed = ok(c.post(f'{ops}/mail/{mail["id"]}/review', json={'to': mail['data']['to'] or ['pm@example.com'], 'cc': mail['data']['cc'], 'subject': mail['data']['subject'], 'body': mail['data']['body']}))
    sent = ok(c.post(f'{ops}/mail/{mail["id"]}/send', json={'approval_token': reviewed['data']['approval_token']}))
    assert sent['status'] == 'simulated'
    assert c.post(f'{ops}/mail/{mail["id"]}/send', json={'approval_token': reviewed['data']['approval_token']}).status_code == 409


def test_schedule_progress_and_inspections(c):
    pid = project(c)
    ops = f'/api/projects/{pid}/ops'
    board = ok(c.get(f'{ops}/board'))
    act = next(a for a in board['activities'] if a['work_status'] != 'complete')
    for value in (35, 100, 12.5, 0):
        assert ok(c.patch(f'{ops}/activities/{act["id"]}', json={'percent_complete': value}))['percent_complete'] == value
    ok(c.patch(f'{ops}/activities/{act["id"]}/plan', json={'start_date': '2026-11-02', 'finish_date': '2026-11-06', 'progress_kind': 'field', 'progress_id': None}))
    assert c.patch(f'{ops}/activities/{act["id"]}/plan', json={'start_date': '2026-11-09', 'finish_date': '2026-11-06', 'progress_kind': 'field'}).status_code == 422
    insp = ok(c.post(f'{ops}/inspections', json={'name': 'Electrical rough-in', 'scheduled_date': '2026-11-10', 'status': 'confirmed', 'notes': '', 'blocks_activity_ids': [act['id']]}))
    ok(c.patch(f'{ops}/inspections/{insp["id"]}', json={'name': 'Electrical rough-in', 'scheduled_date': '2026-11-11', 'status': 'passed', 'notes': 'ok', 'blocks_activity_ids': [act['id']]}))
    ok(c.patch(f'{ops}/profile', json={'city': 'Greenwich, Connecticut', 'job_type': 'Retail fit-out', 'start_date': '2026-10-01', 'turnover_date': '2026-12-20', 'workdays': [0, 1, 2, 3, 4]}))
    ok(c.post(f'{ops}/research', json={'inspection_type': 'Electrical rough-in inspection'}))
    ok(c.get(f'{ops}/agents'))


def test_schedule_builder(c):
    pid = project(c, 'Sage and Sound')
    ops = f'/api/projects/{pid}/ops'
    plan = ok(c.post(f'{ops}/schedule/propose', json={'description': 'Retail fit-out with rough-in and finishes.', 'start_date': '2026-11-02', 'turnover_date': '2027-01-29'}))
    data = plan['data']
    body = {'tasks': data['tasks'], 'assumptions': data['assumptions'], 'start_date': data['start_date'], 'turnover_date': data['turnover_date'], 'replace_existing': True}
    ok(c.post(f'{ops}/schedule/{plan["id"]}/apply', json=body))
    assert c.post(f'{ops}/schedule/{plan["id"]}/apply', json=body).status_code == 409


def test_procurement_and_packages(c):
    pid = project(c)
    ops = f'/api/projects/{pid}/ops'
    ok(c.get(f'{ops}/procurement'))
    item = ok(c.post(f'{ops}/procurement', json={'name': 'Door hardware', 'vendor': 'Acme', 'vendor_email': 'sales@acme.example.com', 'status': 'ordered', 'expected_delivery_date': '2026-11-20', 'required_on_site_date': '2026-11-25', 'lead_time_days': 21, 'submittal_id': None, 'activity_ids': [], 'notes': ''}))
    ok(c.patch(f'{ops}/procurement/{item["id"]}', json={'name': 'Door hardware', 'vendor': 'Acme', 'vendor_email': '', 'status': 'in transit', 'expected_delivery_date': None, 'required_on_site_date': '2026-11-25', 'lead_time_days': None, 'activity_ids': [], 'notes': 'x'}))
    pkg = ok(c.post(f'{ops}/packages', json={'procurement_id': item['id'], 'label': 'Box 1', 'carrier': 'UPS', 'tracking_number': '1Z999', 'eta': '2026-11-19', 'status': 'ordered'}))
    received = ok(c.patch(f'{ops}/packages/{pkg["id"]}', json={'procurement_id': item['id'], 'label': 'Box 1', 'carrier': 'UPS', 'tracking_number': '1Z999', 'eta': '2026-11-19', 'status': 'received'}))
    assert received['status'] == 'received'
    assert next(i for i in ok(c.get(f'{ops}/procurement'))['items'] if i['id'] == item['id'])['status'] == 'delivered'
    ok(c.patch(f'{ops}/packages/{pkg["id"]}', json={'procurement_id': item['id'], 'label': 'Box 1', 'carrier': 'UPS', 'tracking_number': '1Z999', 'eta': '2026-11-19', 'status': 'ordered'}))


def test_rfi_flow_and_contacts(c):
    pid = project(c)
    ops = f'/api/projects/{pid}/ops'
    rfi = ok(c.post(f'{ops}/rfis/generate', data={'description': 'Electrical panel conflicts with the millwork at the sauna wall. Please confirm the clearance.'}, files=[('files', ('note.txt', b'panel clearance note', 'text/plain'))]))
    saved = ok(c.patch(f'{ops}/rfis/{rfi["id"]}', json={'subject': rfi['subject'], 'question': rfi['question'], 'to': ['architect@example.com'], 'cc': ['pm@example.com']}))
    assert saved['raw_json']['distribution']['to'] == ['architect@example.com']
    assert any(r['id'] == rfi['id'] for r in ok(c.get(f'{ops}/rfis')))
    att = rfi['raw_json']['attachments'][0]
    assert c.get(f'{ops}/attachments/{att["id"]}').status_code == 200
    mail = ok(c.post(f'{ops}/mail/prepare', json={'rfi_id': rfi['id']}))
    assert mail['data']['to']
    contact = ok(c.post(f'{ops}/contacts', json={'name': 'Casey Engineer', 'email': 'casey@example.com', 'role': 'engineer', 'trades': ['Electrical']}))
    ok(c.delete(f'{ops}/contacts/{contact["id"]}'))


def test_uploads_sync_settings_and_records(c):
    pid = project(c)
    for kind, name in [('procurement-log', 'procurement.csv'), ('schedule', 'schedule.csv'), ('document', 'coordination-notes.txt')]:
        ok(c.post(f'/api/projects/{pid}/uploads/{kind}', files={'file': (name, (SAMPLES / name).read_bytes())}))
    assert c.post(f'/api/projects/{pid}/uploads/bogus', files={'file': ('a.csv', b'x')}).status_code == 404
    assert c.post(f'/api/projects/{pid}/uploads/schedule', files={'file': ('a.csv', b'not,a,schedule\n')}).status_code == 422
    ok(c.post(f'/api/projects/{pid}/sync'))
    assert ok(c.get(f'/api/projects/{pid}/sync-status'))['status'] in ('complete', 'queued', 'running')
    for kind in ('rfis', 'submittals', 'procurement', 'schedule', 'emails', 'documents'):
        rows = ok(c.get(f'/api/projects/{pid}/{kind}'))
        if rows:
            ok(c.get(f'/api/projects/{pid}/sources/{kind}/{rows[0]["id"]}'))
    ok(c.patch(f'/api/projects/{pid}/settings', json={'aliases': ['Alo'], 'email_keywords': ['Greenwich'], 'sync_enabled': True, 'sync_minutes': 15, 'workbooks': []}))
    assert ok(c.get(f'/api/projects/{pid}'))['counts']


def test_organization_projects_and_integrations(c):
    ok(c.post('/api/organizations', json={'name': 'Renamed Co'}))
    assert ok(c.get('/api/me'))['organization_name'] == 'Renamed Co'
    ok(c.get('/api/organizations/usage'))
    new = ok(c.post('/api/projects', json={'name': 'Harbor House'}))
    ok(c.get(f'/api/projects/{new["id"]}'))
    ok(c.post('/api/projects/demo'))
    ints = ok(c.get('/api/integrations'))
    assert {i['provider'] for i in ints} == {'procore', 'microsoft', 'openai', 'anthropic'}
    ok(c.post('/api/integrations/procore/connect'))
    company = ok(c.get('/api/procore/companies'))[0]
    ok(c.post('/api/procore/import-project', json={'company_id': company['id'], 'project_id': ok(c.get(f'/api/procore/companies/{company["id"]}/projects'))[0]['id']}))
    conn = next(i for i in ok(c.get('/api/integrations')) if i['provider'] == 'procore')
    ok(c.delete(f'/api/integrations/{conn["id"]}'))
    ok(c.post('/api/auth/logout', json={}))
    assert c.get('/api/me').status_code == 401


def test_delete_draft_rfi_mail_and_uploaded_document(c):
    pid = project(c)
    ops = f'/api/projects/{pid}/ops'
    rfi = ok(c.post(f'{ops}/rfis/generate', data={'description': 'Please confirm the required installation location for the item shown.'}))
    mail = ok(c.post(f'{ops}/mail/prepare', json={'rfi_id': rfi['id']}))
    ok(c.delete(f'{ops}/mail/{mail["id"]}'))
    assert c.delete(f'{ops}/mail/{mail["id"]}').status_code == 404
    ok(c.delete(f'/api/projects/{pid}/records/rfis/{rfi["id"]}'))
    assert not any(r['id'] == rfi['id'] for r in ok(c.get(f'{ops}/rfis')))
    ok(c.post(f'/api/projects/{pid}/uploads/document', files={'file': ('coordination-notes.txt', (SAMPLES / 'coordination-notes.txt').read_bytes())}))
    doc = next(d for d in ok(c.get(f'/api/projects/{pid}/documents')) if d['filename'] == 'coordination-notes.txt')
    ok(c.delete(f'/api/projects/{pid}/records/documents/{doc["id"]}'))
    assert not any(d['id'] == doc['id'] for d in ok(c.get(f'/api/projects/{pid}/documents')))
    assert c.delete(f'/api/projects/{pid}/records/emails/anything').status_code == 404


def test_remember_me_keeps_the_session_for_thirty_days(monkeypatch):
    _limits.clear()
    monkeypatch.setattr(settings, 'open_signup', True)
    email = f'remember{os.urandom(3).hex()}@example.com'
    with TestClient(app) as client:
        ok(client.post('/api/auth/signup', json={'email': email, 'full_name': 'Remember Me', 'password': PASSWORD, 'company': 'Remember Co'}))
        short = client.post('/api/auth/login', json={'email': email, 'password': PASSWORD})
        long = client.post('/api/auth/login', json={'email': email, 'password': PASSWORD, 'remember': True})
        assert 'Max-Age=28800' in short.headers['set-cookie']
        assert f'Max-Age={30 * 24 * 3600}' in long.headers['set-cookie']


def test_start_working_is_shared_and_survives_a_rescan(c):
    pid = project(c)
    risk = ok(c.get(f'/api/projects/{pid}/risks'))[0]
    started = ok(c.post(f'/api/projects/{pid}/risks/{risk["id"]}/start'))
    assert started['status'] == 'in_progress' and started['evidence']['in_progress_by'] == 'Flow Tester'
    ok(c.post(f'/api/projects/{pid}/risks/run'))
    again = next(r for r in ok(c.get(f'/api/projects/{pid}/risks')) if r['id'] == risk['id'])
    assert again['status'] == 'in_progress' and again['evidence']['in_progress_by'] == 'Flow Tester'
    stopped = ok(c.post(f'/api/projects/{pid}/risks/{risk["id"]}/reopen'))
    assert stopped['status'] == 'open' and 'in_progress_by' not in stopped['evidence']


def test_new_task_has_duration_due_date_and_a_one_week_warning(c):
    from datetime import date, timedelta
    pid = project(c)
    soon = (date.today() + timedelta(days=3)).isoformat()
    made = ok(c.post(f'/api/projects/{pid}/ops/activities', json={'name': 'Hang drywall', 'trade': 'Drywall', 'start_date': date.today().isoformat(), 'duration_days': 5, 'due_date': soon}))
    assert made['raw_json']['due_date'] == soon and made['finish_date'] >= made['start_date']
    warned = ok(c.get(f'/api/projects/{pid}/warnings'))
    assert any(w['key'] == f'work:{made["id"]}' and w['days'] == 3 for w in warned)
    assert any(w['key'] == f'work:{made["id"]}' for w in ok(c.get('/api/notifications')))
    edited = ok(c.patch(f'/api/projects/{pid}/ops/activities/{made["id"]}/plan', json={'name': 'Paint walls', 'trade': 'Paint', 'start_date': date.today().isoformat(), 'duration_days': 2}))
    assert edited['name'] == 'Paint walls' and 'due_date' not in edited['raw_json']
    far = ok(c.post(f'/api/projects/{pid}/ops/activities', json={'name': 'Punch list', 'start_date': (date.today() + timedelta(days=60)).isoformat(), 'duration_days': 2}))
    assert not any(w['key'] == f'work:{far["id"]}' for w in ok(c.get(f'/api/projects/{pid}/warnings')))
