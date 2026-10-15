from test_app import client
from sqlalchemy import select
from app.models import LaunchRequest
from app.database import SessionLocal
from app.security import decrypt_token

def test_launch_capture_validation_deduplication_and_private_storage(client):
    client.post('/api/auth/logout')
    data={'email':'BETA@EXAMPLE.COM','company':'Example GC','interest':'demo','consent':True}
    assert client.post('/api/launch/requests',json=data).status_code==202
    assert client.post('/api/launch/requests',json=data).status_code==202
    with SessionLocal() as db:
        rows=list(db.scalars(select(LaunchRequest)))
        assert len(rows)==1
        assert rows[0].email_encrypted!='beta@example.com'
        assert decrypt_token(rows[0].email_encrypted)=='beta@example.com'
        assert decrypt_token(rows[0].company_encrypted)=='Example GC'
    assert client.get('/api/launch/requests').status_code==405
    assert client.post('/api/launch/requests',json={**data,'consent':False}).status_code==422
    assert client.post('/api/launch/requests',json={**data,'email':'bad-email'}).status_code==422
    assert client.post('/api/launch/requests',json={**data,'email':'bot@example.com','website':'spam'}).status_code==202
    with SessionLocal() as db:
        assert len(list(db.scalars(select(LaunchRequest))))==1
