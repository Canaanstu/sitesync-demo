import os
from pathlib import Path
import subprocess
import sys
from cryptography.fernet import Fernet


def test_private_demo_disables_public_password_and_requires_secure_cookie(tmp_path):
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(tmp_path/'private.db').replace('\\','/'),'DEMO_MODE':'true','EPHEMERAL_DEMO':'true','PRIVATE_DEMO':'true','PRIVATE_DEMO_PASSWORD':'Only-for-isolated-hosting-test-2026','JWT_SECRET':'isolated-test-signing-key-longer-than-32-characters','TOKEN_ENCRYPTION_KEY':Fernet.generate_key().decode(),'APP_URL':'https://private.example.test','API_URL':'https://private.example.test','ENABLE_EMAIL_SEND':'false'}
    code='''
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app,base_url='https://private.example.test') as c:
    assert c.get('/api/health').json()['local_auto_login'] is False
    assert c.get('/api/health').json()['ephemeral_demo'] is True
    assert c.get('/api/projects').status_code==401
    assert c.post('/api/auth/login',json={'email':'demo@example.com','password':'DemoProject2026!'}).status_code==401
    r=c.post('/api/auth/login',json={'email':'demo@example.com','password':'Only-for-isolated-hosting-test-2026'})
    assert r.status_code==200
    assert 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
    assert len(c.get('/api/projects').json())==2
    assert c.get('/api/me').json()['ephemeral_demo'] is True
'''
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr


def test_private_hosting_refuses_missing_secrets(tmp_path):
    env={**os.environ,'PRIVATE_DEMO':'true','DEMO_MODE':'true','PRIVATE_DEMO_PASSWORD':'','JWT_SECRET':'','TOKEN_ENCRYPTION_KEY':''}
    result=subprocess.run([sys.executable,'-c','import app.config'],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
    assert 'PRIVATE_DEMO_PASSWORD' in result.stderr
