from contextlib import asynccontextmanager
import hashlib
import secrets
import threading
import json
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from .config import settings
from .database import Base, engine, SessionLocal, get_db
from .models import *
from .security import *
from .seed import initialize, seed_project, seed_workspace
from .mailer import mail_enabled, send_email
from .accounts import delete_workspace
from .risk_engine import run_rules
from .connectors import OAuthConnector, save_tokens, valid_token, Procore, Microsoft
from .parsing import parse_table, parse_document
from .sync import sync_project, ingest_rows, generate_embeddings
from .ai import answer
from .operations import router as operations_router
from .launch import router as launch_router


def add_missing_columns():
    """create_all never alters existing tables, so add columns introduced after a database was first created."""
    from sqlalchemy import inspect
    if 'email_verified' not in {c['name'] for c in inspect(engine).get_columns('users')}:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT TRUE'))
    if 'invite_code' not in {c['name'] for c in inspect(engine).get_columns('organizations')}:
        with engine.begin() as conn:
            conn.execute(text('ALTER TABLE organizations ADD COLUMN invite_code VARCHAR'))
            conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_organizations_invite_code ON organizations (invite_code)'))


_ready = False
_ready_lock = threading.Lock()
_INIT_LOCK_KEY = 7302026


def ensure_ready():
    """Create tables and seed once per process. Serverless hosts may skip ASGI lifespan, so the first request also calls this.
    A Postgres advisory lock stops simultaneous cold starts from seeding the same database twice."""
    global _ready
    if _ready:
        return
    with _ready_lock:
        if _ready:
            return
        postgres = engine.dialect.name == 'postgresql'
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as lock:
            if postgres:
                lock.execute(text('SELECT pg_advisory_lock(:k)'), {'k': _INIT_LOCK_KEY})
            try:
                if settings.demo_mode:
                    if postgres:
                        lock.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                    Base.metadata.create_all(engine)
                    add_missing_columns()
                with SessionLocal() as db:
                    if not settings.demo_mode:
                        demo_user = db.scalar(select(User).where(User.email == 'demo@example.com'))
                        if demo_user and verify_password('DemoProject2026!', demo_user.password_hash):
                            raise RuntimeError('Use a fresh live database; the known demo account must not be enabled in live mode.')
                    initialize(db)
            finally:
                if postgres:
                    lock.execute(text('SELECT pg_advisory_unlock(:k)'), {'k': _INIT_LOCK_KEY})
        _ready = True


@asynccontextmanager
async def lifespan(app):
    ensure_ready()
    yield


app = FastAPI(title='SiteSync - Construction Intelligence', lifespan=lifespan)
app.include_router(operations_router)
app.include_router(launch_router)
app.add_middleware(CORSMiddleware, allow_origins=[settings.app_url], allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type'])


@app.middleware('http')
async def protect_origin(request, call_next):
    if not _ready:
        await run_in_threadpool(ensure_ready)
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin != settings.app_url:
        return JSONResponse({'detail': 'Request origin is not allowed.'}, status_code=403)
    try:
        length = int(request.headers.get('content-length', '0') or 0)
    except ValueError:
        return JSONResponse({'detail': 'Invalid content length.'}, status_code=400)
    if length > 11_000_000:
        return JSONResponse({'detail': 'Request exceeds the 10 MB file limit.'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response


Db = Depends(get_db)
Auth = Depends(current_user)


def audit(db, user, action, detail=None):
    db.add(Audit(organization_id=user.organization_id, user_id=user.id, action=action, detail=detail or {}))


def new_invite_code():
    raw = secrets.token_hex(5).upper()
    return raw[:5] + '-' + raw[5:]


def clean_code(value):
    return ''.join(value.split()).upper()


def invite_code_for(db, org):
    """Organizations created before invite codes existed get one the first time an admin asks."""
    if not org.invite_code:
        org.invite_code = new_invite_code()
        db.flush()
    return org.invite_code


def grant_projects(db, org_id, member_id=None, project_id=None):
    """Members only see projects they are granted. Everyone in a company shares its projects, so grant them automatically
    (an admin can still revoke one in project settings)."""
    member_ids = [member_id] if member_id else list(db.scalars(select(User.id).where(User.organization_id == org_id, User.role.not_in(['owner', 'admin']))))
    project_ids = [project_id] if project_id else list(db.scalars(select(Project.id).where(Project.organization_id == org_id)))
    for m in member_ids:
        for p in project_ids:
            if not db.get(ProjectMember, (p, m)):
                db.add(ProjectMember(project_id=p, user_id=m))


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=72)


class Name(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class ImportProject(BaseModel):
    company_id: str = Field(pattern=r'^[0-9a-zA-Z_-]{1,80}$')
    project_id: str = Field(pattern=r'^[0-9a-zA-Z_-]{1,80}$')


class Workbook(BaseModel):
    drive_id: str = Field(min_length=1, max_length=200)
    item_id: str = Field(min_length=1, max_length=200)
    kind: Literal['procurement-log', 'schedule']


class ProjectSettings(BaseModel):
    aliases: list[str] = Field(default_factory=list, max_length=30)
    email_keywords: list[str] = Field(default_factory=list, max_length=30)
    sync_enabled: bool = True
    sync_minutes: int = Field(default=15, ge=10, le=1440)
    workbooks: list[Workbook] = Field(default_factory=list, max_length=10)


class Signup(BaseModel):
    email: str = Field(max_length=254, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=72)
    company: str = Field(default='', max_length=160)
    invite_code: str = Field(default='', max_length=40)


class JoinRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=40)
    password: str = Field(max_length=72)


class EmailOnly(BaseModel):
    email: str = Field(max_length=254)


class TokenOnly(BaseModel):
    token: str = Field(max_length=2000)


class ResetBody(BaseModel):
    token: str = Field(max_length=2000)
    password: str = Field(min_length=12, max_length=72)


class PasswordConfirm(BaseModel):
    password: str = Field(max_length=72)


class AIRequest(BaseModel):
    question: str = Field(default='', max_length=4000)
    risk_id: str | None = None


class MemberRequest(BaseModel):
    email: str = Field(max_length=254)
    full_name: str = Field(max_length=120)
    password: str = Field(min_length=12, max_length=72)
    role: Literal['admin', 'member', 'viewer'] = 'member'


@app.get('/api/health')
def health():
    return {'status': 'ok', 'demo_mode': settings.demo_mode, 'ephemeral_demo': settings.ephemeral_demo, 'local_auto_login': settings.demo_mode and not settings.private_demo, 'signup_open': settings.open_signup, 'email_enabled': mail_enabled()}


@app.post('/api/auth/login')
def login(body: Login, request: Request, response: Response, db: Session = Db):
    rate_limit('login:' + (request.client.host if request.client else 'unknown'), 10)
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, 'Email or password is incorrect.')
    start_session(response, user)
    return public(user)


def start_session(response, user):
    response.set_cookie('session', token_for(user), httponly=True, secure=settings.app_env == 'production' or settings.private_demo, samesite='lax', max_age=28800, path='/')


@app.post('/api/auth/signup')
def signup(body: Signup, request: Request, response: Response, db: Session = Db):
    """Create a private workspace for a new user. Demo deployments seed it with the fictional sample projects."""
    if not settings.open_signup:
        raise HTTPException(403, 'Sign-up is not open on this deployment.')
    rate_limit('signup:' + (request.client.host if request.client else 'unknown'), 5)
    email = body.email.lower().strip()
    if email == 'demo@example.com' or db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'An account with this email already exists. Sign in instead.')
    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    name = body.full_name.strip()
    code = clean_code(body.invite_code)
    joined = db.scalar(select(Organization).where(Organization.invite_code == code)) if code else None
    if code and not joined:
        raise HTTPException(404, 'That invite code was not found. Ask your administrator for a current one.')
    if joined:
        org = joined
    else:
        recent = db.scalar(select(func.count()).select_from(Organization).where(Organization.created_at > hour_ago))
        total = db.scalar(select(func.count()).select_from(Organization))
        if recent >= settings.signups_per_hour or total >= settings.max_organizations:
            raise HTTPException(429, 'Sign-ups are busy right now. Please try again later.')
        org = Organization(name=body.company.strip() or f"{name.split()[0]}'s workspace", invite_code=new_invite_code())
        db.add(org)
        db.flush()
    user = User(organization_id=org.id, email=email, full_name=name, role='member' if joined else 'owner', password_hash=hash_password(body.password), email_verified=not mail_enabled())
    db.add(user)
    try:
        db.flush()
        if joined:
            grant_projects(db, org.id, member_id=user.id)
        elif settings.demo_mode:
            seed_workspace(db, org)
        audit(db, user, 'user.join_organization' if joined else 'user.signup')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this email already exists. Sign in instead.')
    start_session(response, user)
    return {**public(user), 'verification_sent': (not user.email_verified) and send_verification(user)}


def send_verification(user):
    link = f"{settings.app_url}/verify/?token={mail_token('verify', user, 72, email=user.email)}"
    return send_email(user.email, 'Confirm your SiteSync email', f"Hi {user.full_name or ''},\n\nConfirm your email to finish setting up SiteSync:\n{link}\n\nThis link expires in 3 days. If you did not create an account, ignore this message.")


@app.post('/api/auth/verify')
def verify_email(body: TokenOnly, request: Request, db: Session = Db):
    rate_limit('verify:' + (request.client.host if request.client else 'unknown'), 20)
    payload = read_mail_token(body.token, 'verify')
    user = db.get(User, payload['sub'])
    if not user or user.email != payload.get('email'):
        raise HTTPException(400, 'This link is invalid or has expired. Request a new one.')
    user.email_verified = True
    audit(db, user, 'user.verify_email')
    db.commit()
    return {'ok': True}


@app.post('/api/auth/resend-verification')
def resend_verification(user=Auth):
    rate_limit('resend:' + user.id, 3)
    if user.email_verified:
        return {'ok': True, 'already_verified': True}
    if not mail_enabled():
        raise HTTPException(503, 'Email is not set up on this deployment.')
    if not send_verification(user):
        raise HTTPException(502, 'The email could not be sent. Try again in a moment.')
    return {'ok': True}


@app.post('/api/auth/forgot')
def forgot_password(body: EmailOnly, request: Request, db: Session = Db):
    """Always answers the same way, so it cannot be used to discover which emails have accounts."""
    rate_limit('forgot:' + (request.client.host if request.client else 'unknown'), 5)
    if not mail_enabled():
        raise HTTPException(503, 'Password reset by email is not set up on this deployment.')
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if user:
        link = f"{settings.app_url}/reset/?token={mail_token('reset', user, 1, pw=password_fingerprint(user))}"
        send_email(user.email, 'Reset your SiteSync password', f"Hi {user.full_name or ''},\n\nUse this link to choose a new password:\n{link}\n\nIt works once and expires in 1 hour. If you did not ask for this, ignore this message; your password has not changed.")
    return {'ok': True}


@app.post('/api/auth/reset')
def reset_password(body: ResetBody, request: Request, db: Session = Db):
    rate_limit('reset:' + (request.client.host if request.client else 'unknown'), 10)
    payload = read_mail_token(body.token, 'reset')
    user = db.get(User, payload['sub'])
    if not user or payload.get('pw') != password_fingerprint(user):
        raise HTTPException(400, 'This link is invalid or has expired. Request a new one.')
    user.password_hash = hash_password(body.password)
    user.email_verified = True  # they just proved they control the inbox
    audit(db, user, 'user.reset_password')
    db.commit()
    return {'ok': True}


@app.delete('/api/me')
def delete_account(body: PasswordConfirm, request: Request, response: Response, db: Session = Db, user=Auth):
    """Delete the signed-in user's private workspace and everything in it."""
    rate_limit('delete:' + user.id, 5)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, 'Password is incorrect.')
    if user.email == 'demo@example.com' or db.scalar(select(func.count()).select_from(User).where(User.organization_id == user.organization_id)) > 1:
        raise HTTPException(403, 'Shared workspaces cannot be deleted here. Ask the workspace owner.')
    delete_workspace(db, user.organization_id)
    db.commit()
    response.delete_cookie('session', path='/')
    return {'ok': True}


@app.post('/api/auth/logout')
def logout(response: Response):
    response.delete_cookie('session', path='/')
    return {'ok': True}


@app.get('/api/me')
def me(db: Session = Db, user=Auth):
    org = db.get(Organization, user.organization_id)
    return {**public(user), 'organization_name': org.name if org else '', 'demo_mode': settings.demo_mode, 'ephemeral_demo': settings.ephemeral_demo}


@app.get('/api/organizations/current')
def organization(db: Session = Db, user=Auth):
    org = db.get(Organization, user.organization_id)
    result = public(org)
    if user.role in ('owner', 'admin'):
        result['invite_code'] = invite_code_for(db, org)
        db.commit()
    return result


@app.post('/api/organizations/invite-code')
def rotate_invite_code(db: Session = Db, user=Auth):
    """Replace the company invite code, so a code that was shared too widely stops working."""
    require_admin(user)
    org = db.get(Organization, user.organization_id)
    org.invite_code = new_invite_code()
    audit(db, user, 'organization.rotate_invite')
    db.commit()
    return {**public(org), 'invite_code': org.invite_code}


@app.post('/api/organizations/join')
def join_organization(body: JoinRequest, request: Request, db: Session = Db, user=Auth):
    """Move a signed-in person who is alone in their own workspace into their company's workspace."""
    rate_limit('join:' + (request.client.host if request.client else 'unknown'), 10)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, 'Password is incorrect.')
    target = db.scalar(select(Organization).where(Organization.invite_code == clean_code(body.invite_code)))
    if not target:
        raise HTTPException(404, 'That invite code was not found. Ask your administrator for a current one.')
    if target.id == user.organization_id:
        raise HTTPException(409, 'You are already in this company.')
    if user.email == 'demo@example.com' or db.scalar(select(func.count()).select_from(User).where(User.organization_id == user.organization_id)) > 1:
        raise HTTPException(403, 'Only a person working alone in their own workspace can switch companies.')
    old_org_id = user.organization_id
    user.organization_id, user.role = target.id, 'member'
    db.flush()
    # The personal workspace they leave behind (sample projects only) is removed so nothing is orphaned.
    delete_workspace(db, old_org_id)
    grant_projects(db, target.id, member_id=user.id)
    audit(db, user, 'user.join_organization')
    db.commit()
    return {'ok': True, 'organization_name': target.name}


@app.post('/api/organizations')
def organization_setup(body: Name, db: Session = Db, user=Auth):
    require_admin(user)
    org = db.get(Organization, user.organization_id)
    org.name = body.name.strip()
    audit(db, user, 'organization.rename')
    db.commit()
    return public(org)


@app.get('/api/organizations/members')
def members(db: Session = Db, user=Auth):
    require_admin(user)
    return [public(u) for u in db.scalars(select(User).where(User.organization_id == user.organization_id))]


@app.post('/api/organizations/members')
def create_member(body: MemberRequest, db: Session = Db, user=Auth):
    require_admin(user)
    if user.role != 'owner' and body.role == 'admin':
        raise HTTPException(403, 'Only an owner can add administrators.')
    if db.scalar(select(User).where(User.email == body.email.lower().strip())):
        raise HTTPException(409, 'This email is already registered.')
    member = User(organization_id=user.organization_id, email=body.email.lower().strip(), full_name=body.full_name, role=body.role, password_hash=hash_password(body.password))
    db.add(member)
    db.flush()
    grant_projects(db, user.organization_id, member_id=member.id)
    audit(db, user, 'member.create', {'email': body.email, 'role': body.role})
    db.commit()
    return public(member)


@app.get('/api/projects')
def projects(db: Session = Db, user=Auth):
    query = select(Project).where(Project.organization_id == user.organization_id, Project.status != 'archived')
    if user.role not in ('owner', 'admin'):
        query = query.join(ProjectMember).where(ProjectMember.user_id == user.id)
    output = []
    for p in db.scalars(query):
        risks = list(db.scalars(select(Risk).where(Risk.project_id == p.id, Risk.status == 'open')))
        has_records = any(db.scalar(select(cls.id).where(cls.project_id == p.id).limit(1)) for cls in RECORDS.values())
        from .progress import completion_summary
        output.append({**public(p), **completion_summary(db,p.id), 'risk_count': len(risks), 'high_risks': sum(r.severity in ('critical', 'high') for r in risks), 'health_score': max(0, 100 - sum({'critical': 20, 'high': 10, 'medium': 5, 'low': 2}[r.severity] for r in risks)) if has_records else None})
    return output


@app.post('/api/projects')
def create_project(body: Name, db: Session = Db, user=Auth):
    require_admin(user)
    p = Project(organization_id=user.organization_id, name=body.name, settings={})
    db.add(p)
    db.flush()
    grant_projects(db, user.organization_id, project_id=p.id)
    db.commit()
    return public(p)


@app.post('/api/projects/demo')
def demo_project(db: Session = Db, user=Auth):
    require_admin(user)
    if not settings.demo_mode:
        raise HTTPException(403, 'Demo project creation is disabled in live mode.')
    p = seed_project(db, user.organization_id)
    grant_projects(db, user.organization_id, project_id=p.id)
    db.commit()
    return public(p)


@app.get('/api/projects/{project_id}')
def project_detail(project_id: str, db: Session = Db, user=Auth):
    p = project_access(db, user, project_id)
    open_rfis = db.scalar(select(func.count()).select_from(RFI).where(RFI.project_id == project_id, RFI.status.not_in(['closed', 'answered'])))
    return {**public(p), 'open_rfi_count': open_rfis, 'counts': {k: db.scalar(select(func.count()).select_from(cls).where(cls.project_id == project_id)) for k, cls in RECORDS.items()}}


@app.patch('/api/projects/{project_id}/settings')
def project_settings(project_id: str, body: ProjectSettings, db: Session = Db, user=Auth):
    require_admin(user)
    p = project_access(db, user, project_id)
    if any(len(s) > 160 for s in body.aliases + body.email_keywords):
        raise HTTPException(422, 'Matching phrases must be under 160 characters.')
    p.settings = {**p.settings, **body.model_dump()}
    audit(db, user, 'project.settings', {'project_id': project_id})
    db.commit()
    return public(p)


@app.get('/api/projects/{project_id}/members')
def project_members(project_id: str, db: Session = Db, user=Auth):
    require_admin(user)
    project_access(db, user, project_id)
    return list(db.scalars(select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)))


@app.post('/api/projects/{project_id}/members/{member_id}')
def grant_member(project_id: str, member_id: str, db: Session = Db, user=Auth):
    require_admin(user)
    project_access(db, user, project_id)
    member = db.get(User, member_id)
    if not member or member.organization_id != user.organization_id:
        raise HTTPException(404, 'Member not found.')
    if not db.get(ProjectMember, (project_id, member_id)):
        db.add(ProjectMember(project_id=project_id, user_id=member_id))
    audit(db, user, 'project.grant', {'project_id': project_id, 'member_id': member_id})
    db.commit()
    return {'ok': True}


@app.delete('/api/projects/{project_id}/members/{member_id}')
def revoke_member(project_id: str, member_id: str, db: Session = Db, user=Auth):
    require_admin(user)
    project_access(db, user, project_id)
    membership = db.get(ProjectMember, (project_id, member_id))
    if membership:
        db.delete(membership)
    audit(db, user, 'project.revoke', {'project_id': project_id, 'member_id': member_id})
    db.commit()
    return {'ok': True}


@app.get('/api/integrations')
def integrations(db: Session = Db, user=Auth):
    rows = {c.provider: public(c) for c in db.scalars(select(Connection).where(Connection.organization_id == user.organization_id))}
    return [rows.get(provider, {'provider': provider, 'status': ('demo' if settings.demo_mode else 'configured' if getattr(settings, provider + '_api_key', '') else 'not connected') if provider in ('openai', 'anthropic') else 'not connected'}) for provider in ('procore', 'microsoft', 'openai', 'anthropic')]


@app.post('/api/integrations/{provider}/connect')
def connect(provider: str, db: Session = Db, user=Auth):
    require_admin(user)
    connector = OAuthConnector(provider)
    if settings.demo_mode:
        c = db.scalar(select(Connection).where(Connection.organization_id == user.organization_id, Connection.provider == provider))
        if not c:
            c = Connection(organization_id=user.organization_id, provider=provider)
            db.add(c)
        c.status = 'demo'
        c.access_token_encrypted = encrypt_token('placeholder-token-not-valid')
        audit(db, user, 'integration.demo_connect', {'provider': provider})
        db.commit()
        return {'demo': True, 'message': 'Simulated connection enabled. No external account was contacted.'}
    state = create_state(user.id, provider)
    return {'url': connector.get_authorization_url(state)}


@app.get('/api/integrations/{provider}/callback')
def callback(provider: str, state: str, code: str = '', error: str = '', db: Session = Db, user=Auth):
    require_admin(user)
    consume_state(state, user.id, provider)
    if error or not code:
        return RedirectResponse(settings.app_url + '/integrations?error=connection_cancelled')
    tokens = OAuthConnector(provider).exchange_code_for_token(code)
    c = db.scalar(select(Connection).where(Connection.organization_id == user.organization_id, Connection.provider == provider))
    if not c:
        c = Connection(organization_id=user.organization_id, provider=provider)
        db.add(c)
    save_tokens(c, tokens)
    audit(db, user, 'integration.connected', {'provider': provider})
    db.commit()
    return RedirectResponse(settings.app_url + '/integrations?connected=' + provider)


def connection_for(db, user, provider):
    c = db.scalar(select(Connection).where(Connection.organization_id == user.organization_id, Connection.provider == provider))
    if not c:
        raise HTTPException(409, 'Connect ' + provider + ' first.')
    return c


@app.post('/api/integrations/{provider}/test')
def test_connection(provider: str, db: Session = Db, user=Auth):
    require_admin(user)
    c = connection_for(db, user, provider)
    if settings.demo_mode:
        return {'message': 'Demo connection is ready; no live API call was made.'}
    token = valid_token(db, c)
    Procore(token).get('me') if provider == 'procore' else Microsoft(token).get('me')
    return {'message': 'Connection verified.'}


@app.delete('/api/integrations/{connection_id}')
def disconnect(connection_id: str, db: Session = Db, user=Auth):
    require_admin(user)
    c = db.get(Connection, connection_id)
    if not c or c.organization_id != user.organization_id:
        raise HTTPException(404, 'Connection not found.')
    audit(db, user, 'integration.disconnected', {'provider': c.provider})
    db.delete(c)
    db.commit()
    return {'message': 'Stored tokens deleted. Revoke the app in your provider portal to revoke the external grant.'}


@app.get('/api/procore/companies')
def companies(db: Session = Db, user=Auth):
    require_admin(user)
    c = connection_for(db, user, 'procore')
    return [{'id': 'demo-company', 'name': 'Schimenti Construction Company (demo)'}] if settings.demo_mode else Procore(valid_token(db, c)).companies()


@app.get('/api/procore/companies/{company_id}/projects')
def provider_projects(company_id: str, db: Session = Db, user=Auth):
    require_admin(user)
    c = connection_for(db, user, 'procore')
    return [{'id': 'demo-procore-project', 'name': 'Harbor House | Procore Demo'}] if settings.demo_mode else Procore(valid_token(db, c), company_id).projects(company_id)


@app.post('/api/procore/import-project')
def import_project(body: ImportProject, db: Session = Db, user=Auth):
    require_admin(user)
    candidates = provider_projects(body.company_id, db, user)
    candidate = next((p for p in candidates if str(p['id']) == body.project_id), None)
    if not candidate:
        raise HTTPException(404, 'Project is not available through this connection.')
    p = db.scalar(select(Project).where(Project.organization_id == user.organization_id, Project.procore_company_id == body.company_id, Project.procore_project_id == body.project_id))
    if not p:
        p = seed_project(db, user.organization_id, candidate['name']) if settings.demo_mode else Project(organization_id=user.organization_id, name=candidate['name'], settings={'aliases': [candidate['name']], 'sync_enabled': True, 'sync_minutes': 15})
        p.external_source = 'demo' if settings.demo_mode else 'procore'
        p.procore_company_id, p.procore_project_id = body.company_id, body.project_id
        db.add(p)
        db.flush()
        grant_projects(db, user.organization_id, project_id=p.id)
        db.commit()
    return public(p)


@app.post('/api/projects/{project_id}/sync')
def sync(project_id: str, tasks: BackgroundTasks, db: Session = Db, user=Auth):
    require_write(user)
    project_access(db, user, project_id)
    rate_limit('sync:' + project_id, 3)
    active = db.scalar(select(SyncJob).where(SyncJob.project_id == project_id, SyncJob.status.in_(['queued', 'running'])))
    if active:
        return public(active)
    job = SyncJob(project_id=project_id)
    db.add(job)
    db.commit()
    if settings.demo_mode:
        tasks.add_task(sync_project, job.id)
    else:
        try:
            from redis import Redis
            from rq import Queue
            Queue(connection=Redis.from_url(settings.redis_url)).enqueue(sync_project, job.id, job_timeout=1200)
        except Exception:
            job.status, job.detail = 'failed', 'The sync queue is unavailable. Please retry.'
            db.commit()
            raise HTTPException(503, job.detail)
    return public(job)


@app.get('/api/projects/{project_id}/sync-status')
def sync_status(project_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    job = db.scalar(select(SyncJob).where(SyncJob.project_id == project_id).order_by(SyncJob.created_at.desc()))
    return public(job) if job else {'status': 'idle', 'detail': 'Ready to sync.'}


@app.post('/api/projects/{project_id}/uploads/{kind}')
async def upload(project_id: str, kind: str, tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Db, user=Auth):
    require_write(user)
    project_access(db, user, project_id)
    if kind not in ('procurement-log', 'schedule', 'document'):
        raise HTTPException(404, 'Unknown upload type.')
    content = await file.read(10_000_001)
    if len(content) > 10_000_000:
        raise HTTPException(413, 'Please upload a file smaller than 10 MB.')
    filename = Path(file.filename or 'upload').name[:200]
    try:
        if kind == 'document':
            pages = parse_document(content, filename)
            fingerprint = hashlib.sha256(content).hexdigest()
            existing = db.scalar(select(Document).where(Document.project_id == project_id, Document.source_external_id == fingerprint))
            if existing:
                return {'count': 0, 'message': 'This document is already indexed.'}
            document = Document(project_id=project_id, source_external_id=fingerprint, filename=filename, file_type=filename.rsplit('.', 1)[-1], raw_text='\n'.join(t for _, t in pages))
            db.add(document)
            db.flush()
            count = 0
            for page, text in pages:
                for start in range(0, len(text), 1000):
                    db.add(Chunk(project_id=project_id, document_id=document.id, chunk_index=count, page_number=page, text=text[start:start + 1200]))
                    count += 1
        else:
            rows = parse_table(content, filename, kind)
            ingest_rows(db, project_id, rows, kind, 'upload:' + hashlib.sha256(content).hexdigest())
            count = len(rows)
        db.flush()
        run_rules(db, project_id)
        audit(db, user, 'upload.' + kind, {'project_id': project_id, 'filename': filename, 'count': count})
        db.commit()
        if kind == 'document' and not settings.demo_mode and settings.openai_api_key:
            from redis import Redis
            from rq import Queue
            try:
                Queue(connection=Redis.from_url(settings.redis_url)).enqueue(generate_embeddings, project_id)
            except Exception:
                return {'count': count, 'message': 'Document indexed for keyword search. Embedding queue unavailable; retry through project settings after restoring Redis.'}
        return {'count': count, 'message': f'Imported {count} ' + ('document chunks.' if kind == 'document' else 'rows; risks updated.')}
    except (ValueError, UnicodeError, KeyError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(422, 'The file could not be read. Check its format and try again.')


@app.get('/api/projects/{project_id}/risks')
def risks(project_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    return [public(r) for r in db.scalars(select(Risk).where(Risk.project_id == project_id))]


@app.post('/api/projects/{project_id}/risks/run')
def evaluate(project_id: str, db: Session = Db, user=Auth):
    require_write(user)
    project_access(db, user, project_id)
    result = run_rules(db, project_id)
    audit(db, user, 'risks.run', {'project_id': project_id})
    db.commit()
    return [public(r) for r in result]


@app.get('/api/projects/{project_id}/risks/{risk_id}')
def risk_detail(project_id: str, risk_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    risk = db.get(Risk, risk_id)
    if not risk or risk.project_id != project_id:
        raise HTTPException(404, 'Risk not found.')
    return public(risk)


@app.post('/api/projects/{project_id}/risks/{risk_id}/{action}')
def change_risk(project_id: str, risk_id: str, action: str, db: Session = Db, user=Auth):
    require_write(user)
    risk_detail(project_id, risk_id, db, user)
    if action not in ('resolve', 'dismiss', 'reopen'):
        raise HTTPException(404, 'Unknown action.')
    risk = db.get(Risk, risk_id)
    risk.status = {'resolve': 'resolved', 'dismiss': 'dismissed', 'reopen': 'open'}[action]
    audit(db, user, 'risk.' + action, {'risk_id': risk_id})
    db.commit()
    return public(risk)


@app.get('/api/projects/{project_id}/ai/history')
def history(project_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    return [public(m) for m in db.scalars(select(Message).where(Message.project_id == project_id, Message.user_id == user.id).order_by(Message.created_at).limit(100))]


@app.post('/api/projects/{project_id}/ai/{task}')
def ai_request(project_id: str, task: str, body: AIRequest, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    if task not in ('chat', 'draft-email', 'draft-rfi', 'explain-risk'):
        raise HTTPException(404, 'Unknown AI operation.')
    rate_limit('ai:' + user.organization_id, 30)
    risk = None
    if task != 'chat':
        require_write(user)
        if not body.risk_id:
            raise HTTPException(422, 'Select a risk for this action.')
        risk_detail(project_id, body.risk_id, db, user)
        risk = db.get(Risk, body.risk_id)
    elif not body.question.strip():
        raise HTTPException(422, 'Enter a project question.')
    result = answer(db, project_id, body.question or risk.title, task, risk)
    db.add_all([Message(project_id=project_id, user_id=user.id, role='user', content=body.question or f'{task}: {risk.title}'), Message(project_id=project_id, user_id=user.id, role='assistant', content=result['answer'], sources=result['sources'])])
    audit(db, user, 'ai.' + task, {'project_id': project_id, 'mode': result['mode']})
    db.commit()
    return result


@app.get('/api/organizations/usage')
def usage(db: Session = Db, user=Auth):
    require_admin(user)
    count = db.scalar(select(func.count()).select_from(Audit).where(Audit.organization_id == user.organization_id, Audit.action.like('ai.%')))
    return {'ai_requests': count, 'mode': 'demo' if settings.demo_mode else 'live'}


@app.get('/api/projects/{project_id}/sources/{kind}/{record_id}')
def source_record(project_id: str, kind: str, record_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    cls = {**RECORDS, 'risks': Risk, 'chunks': Chunk}.get(kind)
    row = db.get(cls, record_id) if cls else None
    if not row or row.project_id != project_id:
        raise HTTPException(404, 'Source not found.')
    result = public(row)
    result.pop('embedding', None)
    return result


@app.get('/api/projects/{project_id}/{kind}')
def records(project_id: str, kind: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    cls = RECORDS.get(kind)
    if not cls:
        raise HTTPException(404, 'Record type not found.')
    return [public(r) for r in db.scalars(select(cls).where(cls.project_id == project_id).limit(10000))]
