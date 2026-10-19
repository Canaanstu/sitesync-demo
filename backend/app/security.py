import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from redis import Redis
from .config import settings, fernet
from .database import get_db
from .models import User, Project, ProjectMember

_states = {}
_limits = {}


def hash_password(value):
    if not 12 <= len(value.encode()) <= 72:
        raise HTTPException(422, 'Use a password between 12 and 72 bytes.')
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


def verify_password(value, hashed):
    return len(value.encode()) <= 72 and bcrypt.checkpw(value.encode(), hashed.encode())


def encrypt_token(value):
    return fernet.encrypt(value.encode()).decode()


def decrypt_token(value):
    return fernet.decrypt(value.encode()).decode()


def password_fingerprint(user):
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def token_for(user, hours=8):
    # 'pw' ties a session to the current password, so a reset signs out older sessions.
    return jwt.encode({'sub': user.id, 'pw': password_fingerprint(user), 'exp': datetime.now(timezone.utc) + timedelta(hours=hours), 'iat': datetime.now(timezone.utc)}, settings.jwt_secret, algorithm='HS256')


def _mail_key():
    return hashlib.sha256((settings.jwt_secret + ':mail-links').encode()).hexdigest()


def mail_token(purpose, user, hours, **extra):
    """Signed, expiring link token. Uses a separate key and a purpose claim, so it can never act as a session."""
    return jwt.encode({'sub': user.id, 'purpose': purpose, 'exp': datetime.now(timezone.utc) + timedelta(hours=hours), **extra}, _mail_key(), algorithm='HS256')


def read_mail_token(token, purpose):
    try:
        payload = jwt.decode(token, _mail_key(), algorithms=['HS256'], options={'require': ['sub', 'exp', 'purpose']})
        if payload['purpose'] != purpose:
            raise ValueError()
        return payload
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(400, 'This link is invalid or has expired. Request a new one.')


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get('session', '')
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'], options={'require': ['sub', 'exp']})
        user = db.get(User, payload['sub'])
        if not user or payload.get('purpose') or ('pw' in payload and payload['pw'] != password_fingerprint(user)):
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, 'Please sign in to continue.')


def require_write(user):
    if user.role == 'viewer':
        raise HTTPException(403, 'Your viewer role cannot make changes.')


def require_admin(user):
    if user.role not in ('owner', 'admin'):
        raise HTTPException(403, 'An organization administrator is required.')


def project_access(db, user, project_id):
    project = db.get(Project, project_id)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(404, 'Project not found.')
    if user.role not in ('owner', 'admin') and not db.get(ProjectMember, (project_id, user.id)):
        raise HTTPException(404, 'Project not found.')
    return project


def create_state(user_id, provider):
    state = secrets.token_urlsafe(32)
    value = f'{user_id}:{provider}'
    if settings.demo_mode:
        _states[state] = (value, time.time() + 600)
    else:
        Redis.from_url(settings.redis_url).setex('oauth:' + state, 600, value)
    return state


def consume_state(state, user_id, provider):
    if settings.demo_mode:
        value, expiry = _states.pop(state, ('', 0))
        value = value if expiry > time.time() else ''
    else:
        raw = Redis.from_url(settings.redis_url).getdel('oauth:' + state)
        value = raw.decode() if raw else ''
    if not secrets.compare_digest(value, f'{user_id}:{provider}'):
        raise HTTPException(400, 'This connection link expired or was already used. Please reconnect.')


def rate_limit(key, limit=30, period=60):
    bucket = f'{hashlib.sha256(key.encode()).hexdigest()}:{int(time.time()) // period}'
    if settings.demo_mode:
        current = int(time.time()) // period
        for old in list(_limits):
            if not old.endswith(':' + str(current)):
                _limits.pop(old, None)
        _limits[bucket] = _limits.get(bucket, 0) + 1
        count = _limits[bucket]
    else:
        r = Redis.from_url(settings.redis_url)
        with r.pipeline() as pipe:
            count, _ = pipe.incr(bucket).expire(bucket, period * 2).execute()
    if count > limit:
        raise HTTPException(429, 'Too many requests. Please wait a minute and try again.')
