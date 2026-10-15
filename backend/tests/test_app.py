import os
from pathlib import Path
import tempfile
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(tempfile.mkdtemp()) / 'test.db').replace('\\', '/')
os.environ['DEMO_MODE'] = 'true'
import io
import json
from datetime import date, timedelta
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from app.main import app
from app.database import SessionLocal
from app.models import *
from app.security import encrypt_token, decrypt_token, create_state, consume_state, hash_password, _limits
from app.parsing import parse_table
from app.risk_engine import run_rules
from app.ai import parse_answer
from app.sync import match_email
from app.connectors import Procore, Microsoft, OAuthConnector


@pytest.fixture
def client():
    _limits.clear()
    with TestClient(app) as c:
        assert c.post('/api/auth/login', json={'email': 'demo@example.com', 'password': 'DemoProject2026!'}).status_code == 200
        yield c


def project_id(client):
    return client.get('/api/projects').json()[0]['id']


def test_auth_and_csrf():
    with TestClient(app) as c:
        assert c.get('/api/projects').status_code == 401
        assert c.post('/api/auth/login', json={'email': 'demo@example.com', 'password': 'wrong'}).status_code == 401
        assert c.post('/api/auth/login', headers={'Origin': 'https://evil.example'}, json={'email': 'demo@example.com', 'password': 'DemoProject2026!'}).status_code == 403


def test_encryption_and_oauth_replay():
    raw = 'sensitive-provider-token'
    encrypted = encrypt_token(raw)
    assert raw not in encrypted and decrypt_token(encrypted) == raw
    state = create_state('user1', 'microsoft')
    with pytest.raises(HTTPException):
        consume_state(state, 'user2', 'microsoft')
    state = create_state('user1', 'microsoft')
    consume_state(state, 'user1', 'microsoft')
    with pytest.raises(HTTPException):
        consume_state(state, 'user1', 'microsoft')


def test_six_rules_idempotency_and_decisions(client):
    pid = project_id(client)
    risks = client.post(f'/api/projects/{pid}/risks/run').json()
    fingerprints = {r['fingerprint'].split(':')[0] for r in risks}
    assert {'release', 'delivery', 'approval', 'rfi', 'overdue', 'email'} <= fingerprints
    count = len(risks)
    rid = risks[0]['id']
    assert client.post(f'/api/projects/{pid}/risks/{rid}/dismiss').status_code == 200
    rerun = client.post(f'/api/projects/{pid}/risks/run').json()
    assert len(rerun) == count
    assert next(r for r in rerun if r['id'] == rid)['status'] == 'dismissed'
    assert all(r['severity'] == 'low' for r in rerun if r['category'] == 'email_followup')
    client.post(f'/api/projects/{pid}/risks/{rid}/reopen')


def test_excel_mapping_and_errors():
    w = Workbook()
    w.active.append(['Item Name', 'Status', 'Lead Time Days', 'Required On Site'])
    w.active.append(['Controls', 'not released', 42, '10/15/2026'])
    stream = io.BytesIO(); w.save(stream)
    assert parse_table(stream.getvalue(), 'log.xlsx', 'procurement-log')[0]['required_on_site_date'] == '2026-10-15'
    with pytest.raises(ValueError, match='Missing columns'):
        parse_table(b'Wrong,Headers\na,b', 'bad.csv', 'procurement-log')
    with pytest.raises(ValueError, match='Row 2'):
        parse_table(b'Item,Status,Lead Time,Required On Site\nLamp,open,-2,2026-10-10', 'bad.csv', 'procurement-log')


def test_upload_idempotence_and_document_sources(client):
    pid = project_id(client)
    csv = b'Item,Status,Lead Time,Required On Site\nTest switchboard,not released,45,2026-10-15'
    for _ in range(2):
        r = client.post(f'/api/projects/{pid}/uploads/procurement-log', files={'file': ('test.csv', csv, 'text/csv')})
        assert r.status_code == 200, r.text
    rows = client.get(f'/api/projects/{pid}/procurement').json()
    assert sum(r['name'] == 'Test switchboard' for r in rows) == 1
    doc = client.post(f'/api/projects/{pid}/uploads/document', files={'file': ('notes.txt', b'Acoustic wall panels require submittal review before procurement.', 'text/plain')})
    assert doc.status_code == 200
    answer = client.post(f'/api/projects/{pid}/ai/chat', json={'question': 'What do we know about acoustic wall panels?'}).json()
    assert answer['sources'] and 'Acoustic' in answer['answer']
    for source in answer['sources']:
        assert client.get(f'/api/projects/{pid}/sources/{source["type"]}/{source["id"]}').status_code == 200


def test_demo_flow_and_drafts(client):
    assert client.post('/api/integrations/procore/connect').json()['demo']
    assert client.post('/api/integrations/microsoft/connect').json()['demo']
    companies = client.get('/api/procore/companies').json()
    choices = client.get(f'/api/procore/companies/{companies[0]["id"]}/projects').json()
    p = client.post('/api/procore/import-project', json={'company_id': companies[0]['id'], 'project_id': choices[0]['id']}).json()
    pid = p['id']
    job = client.post(f'/api/projects/{pid}/sync')
    assert job.status_code == 200
    assert client.get(f'/api/projects/{pid}/sync-status').json()['status'] == 'complete'
    risks = client.get(f'/api/projects/{pid}/risks').json()
    for task in ('draft-email', 'draft-rfi', 'explain-risk'):
        r = client.post(f'/api/projects/{pid}/ai/{task}', json={'risk_id': risks[0]['id']})
        assert r.status_code == 200 and r.json()['sources']
    result = client.post(f'/api/projects/{pid}/ai/chat', json={'question': 'Tell me the quantum elephant warranty'}).json()
    assert not result['sources'] and 'could not verify' in result['answer']


def test_tenant_and_project_isolation(client):
    pid = project_id(client)
    with SessionLocal() as db:
        org = Organization(name='Other organization'); db.add(org); db.flush()
        other = User(organization_id=org.id, email='other@example.com', role='owner', password_hash=hash_password('OtherTenant2026!'))
        p = Project(organization_id=org.id, name='Private Project', settings={})
        db.add_all([other, p]); db.commit(); other_pid = p.id
    assert client.get(f'/api/projects/{other_pid}').status_code == 404
    assert client.post(f'/api/projects/{other_pid}/sync').status_code == 404
    assert client.post(f'/api/projects/{other_pid}/ai/chat', json={'question': 'risks'}).status_code == 404
    member = client.post('/api/organizations/members', json={'email':'viewer@example.com','full_name':'Viewer','password':'ViewerAccess2026!','role':'viewer'}).json()
    with TestClient(app) as viewer:
        viewer.post('/api/auth/login', json={'email':'viewer@example.com','password':'ViewerAccess2026!'})
        assert viewer.get(f'/api/projects/{pid}').status_code == 404
        client.post(f'/api/projects/{pid}/members/{member["id"]}')
        assert viewer.get(f'/api/projects/{pid}').status_code == 200
        assert viewer.post(f'/api/projects/{pid}/risks/run').status_code == 403
        assert viewer.post('/api/integrations/procore/connect').status_code == 403
        client.delete(f'/api/projects/{pid}/members/{member["id"]}')
        assert viewer.get(f'/api/projects/{pid}').status_code == 404


def test_answer_citation_validation():
    evidence = [{'id':'one','type':'rfis','label':'RFI 1','data':{}}]
    with pytest.raises(HTTPException):
        parse_answer(json.dumps({'answer':'Unsupported','confidence':'high','source_ids':['invented']}), evidence)
    with pytest.raises(HTTPException):
        parse_answer('bad json', evidence)
    assert not parse_answer(json.dumps({'answer':'An unsupported claim','confidence':'high','source_ids':[]}), evidence)['sources']


def test_email_matching():
    p = Project(name='Alo Greenwich', settings={'aliases':['Project 24017']})
    assert match_email({'subject':'Project 24017 revised delivery'}, p)
    assert not match_email({'subject':'Unrelated development'}, p)


def test_mock_providers(monkeypatch):
    calls = []
    class Result:
        def __init__(self, value): self.value = value
        def json(self): return self.value
    def mock(method, url, **kwargs):
        calls.append((method,url,kwargs))
        if '/oauth/token' in url: return Result({'access_token':'example','refresh_token':'refresh','expires_in':3600})
        if 'graph.microsoft.com' in url: return Result({'value':[{'id':'mail1','subject':'Test'}]})
        return Result([{'id':1,'subject':'Test RFI'}])
    monkeypatch.setattr('app.connectors.request', mock)
    assert Procore('token','123').rfis('456')[0]['id'] == 1
    assert calls[-1][2]['headers']['Procore-Company-Id'] == '123'
    assert Microsoft('token').messages()[0]['id'] == 'mail1'
    assert OAuthConnector('procore').exchange_code_for_token('code')['access_token'] == 'example'


def test_mock_llm_gateways(monkeypatch):
    from app.ai import OpenAIProvider, AnthropicProvider
    class Result:
        def __init__(self, value): self.value=value
        def json(self): return self.value
    def mock(method,url,**kwargs):
        if 'openai' in url: return Result({'choices':[{'message':{'content':'{"answer":"ok"}'}}]})
        return Result({'content':[{'type':'text','text':'{"answer":"ok"}'}]})
    monkeypatch.setattr('app.ai.request',mock)
    messages=[{'role':'system','content':'Only sources'},{'role':'user','content':'Question'}]
    assert 'ok' in OpenAIProvider().complete(messages)
    assert 'ok' in AnthropicProvider().complete(messages)


def test_empty_project_health_is_unknown(client):
    p = client.post('/api/projects', json={'name':'No records yet'}).json()
    listing = client.get('/api/projects').json()
    assert next(row for row in listing if row['id'] == p['id'])['health_score'] is None


def test_expired_state_and_token_refresh(monkeypatch, client):
    from app.security import _states
    from app.connectors import valid_token
    _states['expired'] = ('u:procore', 0)
    with pytest.raises(HTTPException):
        consume_state('expired','u','procore')
    with SessionLocal() as db:
        org_id = db.scalar(select(User).where(User.email == 'demo@example.com')).organization_id
        c = db.scalar(select(Connection).where(Connection.organization_id == org_id, Connection.provider == 'procore'))
        c.access_token_encrypted = encrypt_token('expired')
        c.refresh_token_encrypted = encrypt_token('refresh')
        c.expires_at = 0
        monkeypatch.setattr(OAuthConnector, 'refresh_token', lambda self, value: {'access_token':'new-access','refresh_token':'rotated-refresh','expires_in':3600})
        assert valid_token(db,c) == 'new-access'
        assert decrypt_token(c.refresh_token_encrypted) == 'rotated-refresh'


def test_postgres_vector_query_compiles():
    from sqlalchemy import cast
    from sqlalchemy.dialects import postgresql
    from pgvector.sqlalchemy import Vector
    distance = cast(Chunk.embedding, Vector(1536)).cosine_distance([0.1] * 1536)
    sql = str(select(Chunk).where(Chunk.project_id == 'authorized-project', distance < 0.4).order_by(distance).compile(dialect=postgresql.dialect()))
    assert '<=>' in sql and 'project_id' in sql
