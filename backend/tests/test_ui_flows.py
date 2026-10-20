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


def test_company_counts_as_named_after_saving_even_with_a_workspace_style_name(c):
    me = ok(c.get('/api/me'))
    assert me['organization_named'] is True  # signed up with an explicit company name
    ok(c.post('/api/organizations', json={'name': "Canaan's workspace"}))
    assert ok(c.get('/api/me'))['organization_named'] is True


def test_default_workspace_name_is_unnamed_until_saved(monkeypatch):
    _limits.clear()
    monkeypatch.setattr(settings, 'open_signup', True)
    with TestClient(app) as client:
        ok(client.post('/api/auth/signup', json={'email': f'canaan{os.urandom(3).hex()}@example.com', 'full_name': 'Canaan Test', 'password': PASSWORD, 'company': ''}))
        me = ok(client.get('/api/me'))
        assert me['organization_name'].endswith("'s workspace") and me['organization_named'] is False
        ok(client.post('/api/organizations', json={'name': me['organization_name']}))
        assert ok(client.get('/api/me'))['organization_named'] is True


def make_workbook(sheets):
    import io
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_history_from_excel(c):
    import datetime as dt
    pid = project(c)
    xlsx = make_workbook({
        'Look Ahead': [['Weekly lookahead - Harbor Tower'], [], ['Task Name', 'Planned Start', 'Planned Finish', '% Complete', 'Responsible'],
                       ['Hang drywall L2', dt.datetime(2023, 3, 1), dt.datetime(2023, 3, 9), 1.0, 'ABC Drywall'],
                       ['Paint L2', 'Mar 10, 2023', '03/15/2023', 0.5, 'Pro Paint'], ['', None, None, None, None]],
        'Material Log': [['Material', 'Supplier', 'Need By', 'Lead Time', 'Status'],
                         ['Switchgear', 'Eaton', 45000, '12 weeks', 'Received'], ['Rebar', 'CMC', '2023-02-01', 14, 'bogus-date-row']],
        'RFI Log': [['RFI #', 'Subject', 'Status', 'Due', 'Answer'], [7, 'Slab edge detail', 'Closed', '2023-01-10', 'See SK-4'], [8, None, None, None, None]],
        'Notes': [['random', 'stuff'], ['a', 'b']],
    })
    files = {'file': ('history.xlsx', xlsx, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    prev = ok(c.post(f'/api/projects/{pid}/import/preview', files=files))
    by = {s['sheet']: s for s in prev['sheets']}
    assert by['Look Ahead']['kind'] == 'schedule' and by['Look Ahead']['header_row'] == 3
    assert by['Material Log']['kind'] == 'procurement' and by['RFI Log']['kind'] == 'rfis'
    assert by['Notes']['kind'] is None
    assert by['Look Ahead']['importable'] == 2 and by['Look Ahead']['sample'][0]['percent_complete'] == 100.0
    assert by['Material Log']['sample'][0]['lead_time_days'] == 84 and by['Material Log']['sample'][0]['status'] == 'delivered'
    done = ok(c.post(f'/api/projects/{pid}/import', files=files))
    assert done['created'] == 2 + 2 + 2 and done['updated'] == 0
    again = ok(c.post(f'/api/projects/{pid}/import', files={'file': files['file']}))
    assert again['created'] == 0 and again['updated'] == 6


def test_import_rejects_bad_files(c):
    pid = project(c)
    r = c.post(f'/api/projects/{pid}/import/preview', files={'file': ('old.xls', b'x', 'application/vnd.ms-excel')})
    assert r.status_code == 422 and 'xlsx' in r.text
    r = c.post(f'/api/projects/{pid}/import', files={'file': ('a.csv', b'foo,bar\n1,2\n', 'text/csv')})
    assert r.status_code == 422
    csv_ok = b'Item,Vendor,Required On Site,Lead Time\nDoors,Acme,2023-05-01,30\n'
    assert ok(c.post(f'/api/projects/{pid}/import', files={'file': ('p.csv', csv_ok, 'text/csv')}))['created'] == 1


def test_history_agent_learns_from_imports(c):
    from datetime import date, timedelta
    pid = project(c)
    assert ok(c.get('/api/history/overview'))['total'] == 0
    empty = ok(c.post('/api/history/ask', json={'question': 'How long do switchgear deliveries take?'}))
    assert empty['confidence'] == 'low' and empty['recommended_actions'] and not empty['sources']
    past = c.post('/api/projects', json={'name': 'Harbor Tower 2023'})
    past_id = ok(past)['id']
    csv_text = ('Item,Vendor,Need By,Expected Delivery,Lead Time,Status\n'
                'Switchgear,Eaton,2023-03-01,2023-03-20,84,delivered\nSwitchgear,Eaton,2023-06-01,2023-06-12,84,delivered\nSwitchgear,Square D,2023-09-01,2023-08-28,70,delivered\n'
                'Door hardware,Allegion,2023-04-01,2023-04-01,21,delivered\n')
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('log.csv', csv_text.encode(), 'text/csv')}))
    sched = 'Task,Start,Finish,Trade\nDrywall L1,2023-02-01,2023-02-20,Drywall\nDrywall L2,2023-03-01,2023-03-22,Drywall\n'
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('s.csv', sched.encode(), 'text/csv')}))
    rfi = 'RFI #,Subject,Status,Due\n1,Switchgear clearance in electrical room,Closed,2023-01-10\n'
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('r.csv', rfi.encode(), 'text/csv')}))
    assert ok(c.get('/api/history/overview'))['total'] == 4 + 2 + 1
    lead = ok(c.post('/api/history/ask', json={'question': 'How long do switchgear deliveries take and are they late?'}))
    assert 'Switchgear' in lead['answer'] and 'about 79 days' in lead['answer'] and 'late 2 of 3' in lead['answer']
    assert lead['sources'] and all(s['project'] == 'Harbor Tower 2023' for s in lead['sources']) and lead['steps'][0]['tool'] == 'lead_times'
    assert 'Drywall' in ok(c.post('/api/history/ask', json={'question': 'How many days does drywall take?'}))['answer']
    assert 'clearance' in ok(c.post('/api/history/ask', json={'question': 'Any RFIs about switchgear?'}))['answer']
    # the new project: an open switchgear order with less lead time than history shows up as a warning
    ok(c.post(f'/api/projects/{pid}/uploads/procurement-log', files={'file': ('p.csv', (f'name,status,required_on_site_date,lead_time_days,vendor\nMain switchgear,ordered,{(date.today() + timedelta(days=40)).isoformat()},30,Eaton\n').encode(), 'text/csv')}))
    flag = ok(c.post('/api/history/ask', json={'question': 'What should I watch on this new project based on past projects?', 'project_id': pid}))
    assert any(s['tool'] == 'compare_to_current_project' for s in flag['steps']) and 'Main switchgear' in flag['answer'] and '30 days' in flag['answer']
    assert c.post('/api/history/ask', json={'question': 'hi'}).status_code == 422
    assert c.post('/api/history/ask', json={'question': 'anything here', 'project_id': 'nope'}).status_code == 404


def test_history_agent_generic_questions(c):
    pid = project(c)
    past_id = ok(c.post('/api/projects', json={'name': 'Old Job'}))['id']
    log = 'Item,Vendor,Need By,Expected Delivery,Lead Time,Status\nSwitchgear,Eaton,2023-03-01,2023-03-20,84,delivered\nDoors,Acme,2023-04-01,2023-04-01,21,delivered\n'
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('log.csv', log.encode(), 'text/csv')}))
    for q in ('How long do deliveries usually take, and which ones run late?', 'which items arrive late most often?'):
        r = ok(c.post('/api/history/ask', json={'question': q}))
        assert 'Switchgear' in r['answer'] and 'Doors' in r['answer'], r['answer']
    miss = ok(c.post('/api/history/ask', json={'question': 'How long does asphalt take to arrive?'}))
    assert 'asphalt' in miss['answer'] and miss['confidence'] == 'low'


class FakeLLM:
    """Stands in for an OpenAI-compatible server (Groq, Ollama...). `replies` are returned in order."""
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, method, url, **kw):
        self.calls.append((url, kw))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        class R:
            def json(_):
                return {'choices': [{'message': {'content': reply}}]}
        return R()


def use_free_model(monkeypatch, replies):
    from app import ai
    for k, v in dict(ai_provider='compatible', llm_base_url='https://api.groq.com/openai/v1', llm_model='llama-3.3-70b-versatile', llm_api_key='free-key').items():
        monkeypatch.setattr(settings, k, v)
    fake = FakeLLM(replies)
    monkeypatch.setattr(ai, 'request', fake)
    return fake


def test_project_chat_with_free_model_and_fallback(c, monkeypatch):
    import json
    from fastapi import HTTPException
    pid = project(c)
    evidence_id = ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'What is blocking work today?'}))['sources'][0]['id']
    answer = json.dumps({'answer': 'The lighting controls order is late.', 'confidence': 'high', 'source_ids': [evidence_id], 'recommended_actions': ['Call the vendor']})
    fake = use_free_model(monkeypatch, ['Sure! Here you go:\n```json\n' + answer + '\n```', 'not json at all', HTTPException(502, 'busy')])
    r = ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'What is blocking work today?'}))
    assert r['mode'] == 'live' and r['answer'].startswith('The lighting controls') and r['sources'][0]['id'] == evidence_id
    url, kw = fake.calls[0]
    assert url == 'https://api.groq.com/openai/v1/chat/completions' and kw['headers']['Authorization'] == 'Bearer free-key' and kw['json']['model'] == 'llama-3.3-70b-versatile'
    # garbage from the model, then a provider outage: the chat still answers from the records
    for _ in range(2):
        r = ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'Which deliveries could delay turnover?'}))
        assert r['mode'] == 'fallback' and 'matching records' in r['answer'] and r['sources']


def test_followup_uses_previous_question(c):
    pid = project(c)
    ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'Tell me about the lighting controls order'}))
    r = ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'and the risks?'}))
    assert r['sources'] and 'ighting' in r['answer']


def test_history_agent_with_free_model(c, monkeypatch):
    import json
    from fastapi import HTTPException
    from app import ai
    past_id = ok(c.post('/api/projects', json={'name': 'Old Job'}))['id']
    log = 'Item,Vendor,Need By,Expected Delivery,Lead Time,Status\nSwitchgear,Eaton,2023-03-01,2023-03-20,84,delivered\n'
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('log.csv', log.encode(), 'text/csv')}))
    use_free_model(monkeypatch, [])
    calls = []

    def model(method, url, **kw):
        calls.append(kw)
        if len(calls) == 1:  # step 1: the model asks for the lead-time tool
            reply = json.dumps({'tool': 'lead_times', 'args': {'query': 'switchgear'}})
        else:  # step 2: it answers, citing a record id from the tool result plus one it made up
            seen = json.loads(kw['json']['messages'][1]['content'])['tool_results'][0]['record_ids'][0]
            reply = json.dumps({'final': {'answer': 'Switchgear took about 84 days (1 record).', 'confidence': 'medium', 'source_ids': [seen, 'made-up-id'], 'recommended_actions': []}})

        class R:
            def json(_):
                return {'choices': [{'message': {'content': reply}}]}
        return R()
    monkeypatch.setattr(ai, 'request', model)
    r = ok(c.post('/api/history/ask', json={'question': 'How long does switchgear take?'}))
    assert r['mode'] == 'live' and '84 days' in r['answer'] and r['steps'][0]['tool'] == 'lead_times'
    assert [s['label'] for s in r['sources']] == ['Switchgear']  # the invented id never reaches the person
    monkeypatch.setattr(ai, 'request', FakeLLM([HTTPException(502, 'busy')]))
    r = ok(c.post('/api/history/ask', json={'question': 'How long does switchgear take?'}))
    assert r['mode'] == 'fallback' and 'Switchgear' in r['answer'] and r['notice']


def test_history_uses_actual_dates_when_present(c):
    past_id = ok(c.post('/api/projects', json={'name': 'Actuals Job'}))['id']
    log = ('Item,Vendor,Need By,Expected Delivery,Actual Delivery,Lead Time,Status\n'
           'Chillers,Trane,2023-03-01,2023-03-01,2023-03-29,70,delivered\nChillers,Trane,2023-08-01,2023-08-01,2023-08-15,70,delivered\n')
    sched = 'Task,Planned Start,Planned Finish,Actual Start,Actual Finish\nSet chillers,2023-04-01,2023-04-10,2023-04-05,2023-04-24\n'
    prev = ok(c.post(f'/api/projects/{past_id}/import/preview', files={'file': ('l.csv', log.encode(), 'text/csv')}))
    assert prev['sheets'][0]['mapping']['actual_delivery'] == 4 and prev['sheets'][0]['mapping']['expected_delivery_date'] == 3
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('l.csv', log.encode(), 'text/csv')}))
    prev = ok(c.post(f'/api/projects/{past_id}/import/preview', files={'file': ('s.csv', sched.encode(), 'text/csv')}))['sheets'][0]
    assert prev['mapping']['finish_date'] == 2 and prev['mapping']['actual_finish'] == 4  # "Actual Finish" is not mistaken for the planned finish
    ok(c.post(f'/api/projects/{past_id}/import', files={'file': ('s.csv', sched.encode(), 'text/csv')}))
    late = ok(c.post('/api/history/ask', json={'question': 'Are chiller deliveries late?'}))
    assert 'late 2 of 2' in late['answer'] and 'from actual dates' in late['answer'] and 'about 21 days' in late['answer']  # (28 + 14) / 2
    dur = ok(c.post('/api/history/ask', json={'question': 'How many days does setting chillers take?'}))
    assert 'about 20 days' in dur['answer'] and '14 days after plan' in dur['answer'] and 'from actual dates' in dur['answer']


def test_actual_dates_are_stamped_in_app_and_chat_can_be_cleared(c):
    pid = project(c)
    ok(c.post(f'/api/projects/{pid}/uploads/procurement-log', files={'file': ('p.csv', b'name,status,required_on_site_date,lead_time_days\nStamp test unit,ordered,2026-12-01,20\n', 'text/csv')}))
    item = next(i for i in ok(c.get(f'/api/projects/{pid}/ops/procurement'))['items'] if i['name'] == 'Stamp test unit')
    body = {k: item[k] for k in ('name', 'vendor', 'status', 'lead_time_days', 'required_on_site_date', 'expected_delivery_date', 'submittal_id') if item.get(k) is not None}
    body.update(status='delivered', activity_ids=item.get('activity_ids') or [], vendor_email=item.get('vendor_email') or '')
    stamped = ok(c.patch(f'/api/projects/{pid}/ops/procurement/{item["id"]}', json=body))
    assert stamped['raw_json']['actual_delivery']
    body['status'] = 'ordered'
    assert 'actual_delivery' not in ok(c.patch(f'/api/projects/{pid}/ops/procurement/{item["id"]}', json=body))['raw_json']
    ok(c.post(f'/api/projects/{pid}/ai/chat', json={'question': 'What is blocking work today?'}))
    assert len(ok(c.get(f'/api/projects/{pid}/ai/history'))) == 2
    assert ok(c.delete(f'/api/projects/{pid}/ai/history'))['removed'] == 2
    assert ok(c.get(f'/api/projects/{pid}/ai/history')) == []
    assert c.delete('/api/projects/nope/ai/history').status_code == 404


def test_sample_projects_are_internally_consistent(c):
    """A construction reader should not find contradictions in the sample data."""
    from datetime import date
    today = date.today().isoformat()
    names = {}
    for proj in ok(c.get('/api/projects')):
        board = ok(c.get(f'/api/projects/{proj["id"]}/ops/procurement'))
        sched = ok(c.get(f'/api/projects/{proj["id"]}/ops/board'))
        names[proj['name']] = [i['name'] for i in board['items']]
        for a in sched['activities']:
            assert not (a['start_date'] > today and (a['percent_complete'] or 0) > 0), f'{proj["name"]}: {a["name"]} is in progress but starts in the future'
        for i in board['items']:
            if i['status'] == 'delivered':
                assert (i['expected_delivery_date'] or today) <= today, f'{i["name"]} is delivered but its date is in the future'
            if i['status'] in ('ordered', 'in transit', 'delivered') and i.get('submittal'):
                assert i['submittal']['status'] in ('approved', 'approved as noted'), f'{i["name"]} ordered before its submittal was approved'
            need = i['schedule_need_date']
            for link in i['linked_activities']:
                starts = [a['start_date'] for a in sched['activities'] if a['name'] == link]
                assert not starts or (i['required_on_site_date'] or need) <= min(starts), f'{i["name"]} is required on site after {link} starts'
    assert 'Lighting controls' in names['Alo Yoga'] and 'Lighting controls' not in names['Sage and Sound']
    assert any('sauna' in n.lower() for n in names['Sage and Sound'])
    sage = next(p['id'] for p in ok(c.get('/api/projects')) if p['name'] == 'Sage and Sound')
    assert 'Alo' not in str(ok(c.get(f'/api/projects/{sage}/emails')))


def test_exceptions_trace_three_layers(c):
    data = ok(c.get('/api/exceptions'))
    assert data['total'] == sum(data['counts'].values()) and data['total'] >= 3
    sev = [i['severity'] for i in data['items']]
    assert sev == sorted(sev, key=['high', 'medium', 'low'].index)
    late = next(i for i in data['items'] if i['rule'] == 'delivery' and i['project_name'] == 'Alo Yoga' and 'Lighting' in i['title'])
    t = late['trace']
    assert t['why']['label'] and t['why']['steps'] and t['why']['clears_when']                                   # layer 1: why it was flagged, how to clear it
    assert {e['type'] for e in t['evidence']} >= {'procurement', 'schedule'} and any(f['label'] == 'Expected delivery' for e in t['evidence'] for f in e['facts'])  # layer 2
    assert t['affects']['activities'][0]['name'].startswith('Ceiling close') and 'starts in' in t['affects']['summary'][0] and any('21 days' in s for s in t['affects']['summary'])  # layer 3
    pid = late['project_id']
    assert ok(c.get(f'/api/projects/{pid}/risks/{late["id"]}/trace'))['rule'] == 'delivery'
    only = ok(c.get(f'/api/exceptions?project_id={pid}'))
    assert {i['project_id'] for i in only['items']} == {pid}
    assert c.get('/api/exceptions?project_id=nope').status_code == 404


def test_rules_are_configurable_per_project(c):
    pid = project(c)
    assert ok(c.get(f'/api/projects/{pid}/rules'))['config']['rfi']['window_days'] == 21
    assert 'release' in ok(c.get('/api/rules/guide'))['rules']
    before = {r['fingerprint'].split(':')[0] for r in ok(c.get(f'/api/projects/{pid}/risks')) if r['status'] == 'open'}
    assert {'release', 'delivery', 'rfi'} <= before
    ok(c.put(f'/api/projects/{pid}/rules', json={'rfi': {'enabled': False}, 'delivery': {'severity': 'low'}, 'warn_days': 14}))
    after = ok(c.get(f'/api/projects/{pid}/risks'))
    assert not any(r['fingerprint'].startswith('rfi') and r['status'] == 'open' for r in after)             # switched off: cleared from the list
    assert all(r['severity'] == 'low' for r in after if r['fingerprint'].startswith('delivery') and r['status'] == 'open')
    assert ok(c.get(f'/api/projects/{pid}/warnings'))                                                         # horizon is configurable
    # a wider window brings it back, and early warning flags an item before its latest release date
    ok(c.put(f'/api/projects/{pid}/rules', json={'rfi': {'enabled': True, 'window_days': 60, 'urgent_days': 20}}))
    assert any(r['fingerprint'].startswith('rfi') and r['status'] == 'open' and r['severity'] == 'high' for r in ok(c.get(f'/api/projects/{pid}/risks')))
    assert c.put(f'/api/projects/{pid}/rules', json={'rfi': {'severity': 'urgent'}}).status_code == 422
    assert c.put(f'/api/projects/{pid}/rules', json={'rfi': {'window_days': 0}}).status_code == 422


def test_model_answer_prose_is_cleaned():
    from app.ai import clean_text
    raw = 'Lighting (expected 2026\u201111\u201123) \u301038663e39-df7c-4aa2-bdb8-d51485351362\u3011. Then [d3895a09-605b-481f-b4d2-d6ef80065d2e] millwork .'
    out = clean_text(raw)
    assert '38663e39' not in out and 'd3895a09' not in out and '\u2011' not in out
    assert '2026-11-23' in out
