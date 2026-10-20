from test_app import client, project_id
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Connection
from app.config import settings


def test_bluebeam_metadata_flow(client):
    base='/api/integrations/bluebeam'
    assert client.post(base+'/connect',json={}).status_code==200
    assert client.get(base+'/status').json()['status']=='sample connected'
    projects=client.get(base+'/projects').json()
    pid=project_id(client)
    payload={'project_id':pid,'studio_project_id':projects[0]['id']}
    first=client.post(base+'/sync',json=payload)
    assert first.status_code==200,first.text
    records=first.json()['records']
    assert len(records)==3
    second=client.post(base+'/sync',json=payload).json()['records']
    assert [r['id'] for r in records]==[r['id'] for r in second]
    doc=client.get(f"/api/projects/{pid}/sources/documents/{records[0]['id']}").json()
    assert doc['raw_text']=='' and doc['raw_json']['metadata_only'] is True
    assert client.post(base+'/sync',json={**payload,'project_id':'other-company-project'}).status_code==404
    with SessionLocal() as db:
        connection=db.scalar(select(Connection).where(Connection.provider=='bluebeam'))
        assert not connection.access_token_encrypted and not connection.refresh_token_encrypted
    assert client.delete(base+'/connection').status_code==200
    assert client.post(base+'/sync',json=payload).status_code==409
    assert client.get(f"/api/projects/{pid}/sources/documents/{records[0]['id']}").status_code==200


def test_bluebeam_live_mode_refuses_sample(client,monkeypatch):
    monkeypatch.setattr(settings,'demo_mode',False)
    response=client.post('/api/integrations/bluebeam/connect',json={})
    assert response.status_code==409
    assert 'Live Studio OAuth is not configured' in response.text
