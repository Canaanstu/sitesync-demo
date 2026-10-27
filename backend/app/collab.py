"""Working together on a project: who does what, what changed, field notes and the daily digest.

The change feed is the main place to see updates. The email digest is a once-a-day summary of the same feed,
sent only when something changed, so a busy schedule never means a busy inbox."""
import hmac
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .mailer import mail_enabled, send_email
from .models import Activity, ChangeEvent, FeedRead, Project, ProjectMember, User, now
from .security import current_user, project_access, require_admin, require_write

router = APIRouter(tags=['Collaboration'])
Db, Auth = Depends(get_db), Depends(current_user)
ROLES = ('super', 'pm', 'member')
ROLE_LABELS = {'super': 'Superintendent', 'pm': 'Project manager', 'member': 'Team member'}
DIGEST_MIN_HOURS = 20


def person(u):
    return (u.full_name or u.email.split('@')[0]) if u else 'Former member'


def log_change(db, project_id, user_id, kind, summary, record_id=None):
    db.add(ChangeEvent(project_id=project_id, user_id=user_id, kind=kind, summary=summary[:600], record_id=record_id))


def project_role(db, project_id, user_id):
    m = db.get(ProjectMember, (project_id, user_id))
    return m.role if m else 'member'


def event_view(db, e, names, activities):
    return {'id': e.id, 'kind': e.kind, 'summary': e.summary, 'created_at': e.created_at, 'user_id': e.user_id,
            'author': names.get(e.user_id) or 'Former member', 'activity': activities.get(e.record_id) if e.kind == 'note' else None}


class RoleBody(BaseModel):
    role: Literal['super', 'pm', 'member']


@router.get('/api/projects/{project_id}/team')
def team(project_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    people = {u.id: u for u in db.scalars(select(User).where(User.organization_id == user.organization_id, User.role.in_(('owner', 'admin'))))}
    roles = {}
    for m in db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)):
        roles[m.user_id] = m.role
        if m.user_id not in people:
            people[m.user_id] = db.get(User, m.user_id)
    return [{'id': u.id, 'name': person(u), 'role': roles.get(u.id, 'member'), 'label': ROLE_LABELS[roles.get(u.id, 'member')]} for u in people.values() if u]


@router.put('/api/projects/{project_id}/members/{member_id}/role')
def set_role(project_id: str, member_id: str, body: RoleBody, db: Session = Db, user=Auth):
    require_admin(user)
    project_access(db, user, project_id)
    member = db.get(User, member_id)
    if not member or member.organization_id != user.organization_id:
        raise HTTPException(404, 'Member not found.')
    row = db.get(ProjectMember, (project_id, member_id))
    if not row:
        row = ProjectMember(project_id=project_id, user_id=member_id)
        db.add(row)
    row.role = body.role
    log_change(db, project_id, user.id, 'team', f'{person(member)} is now {ROLE_LABELS[body.role].lower()} on this project.')
    db.commit()
    return {'id': member_id, 'role': body.role}


@router.get('/api/projects/{project_id}/changes')
def changes(project_id: str, limit: int = 50, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    rows = list(db.scalars(select(ChangeEvent).where(ChangeEvent.project_id == project_id).order_by(ChangeEvent.created_at.desc()).limit(max(1, min(limit, 200)))))
    names = {u.id: person(u) for u in db.scalars(select(User).where(User.organization_id == user.organization_id))}
    activities = {a.id: a.name for a in db.scalars(select(Activity).where(Activity.id.in_([r.record_id for r in rows if r.kind == 'note' and r.record_id])))}
    seen = db.get(FeedRead, (project_id, user.id))
    since = seen.last_read_at if seen else user.created_at
    out = [event_view(db, e, names, activities) for e in rows]
    for e in out:
        e['new'] = e['created_at'] > since and e['user_id'] != user.id
    return {'events': out, 'new': sum(1 for e in out if e['new']), 'role': project_role(db, project_id, user.id)}


@router.post('/api/projects/{project_id}/changes/read')
def changes_read(project_id: str, db: Session = Db, user=Auth):
    project_access(db, user, project_id)
    seen = db.get(FeedRead, (project_id, user.id))
    if seen:
        seen.last_read_at = now()
    else:
        db.add(FeedRead(project_id=project_id, user_id=user.id, last_read_at=now()))
    db.commit()
    return {'ok': True}


class NoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    activity_id: str | None = Field(default=None, max_length=36)


@router.post('/api/projects/{project_id}/notes')
def add_note(project_id: str, body: NoteBody, db: Session = Db, user=Auth):
    """A quick field note, stamped with the time it was written, optionally tied to a schedule activity."""
    project_access(db, user, project_id)
    require_write(user)
    text = body.text.strip()
    if not text:
        raise HTTPException(422, 'Write something to note.')
    activity = None
    if body.activity_id:
        activity = db.get(Activity, body.activity_id)
        if not activity or activity.project_id != project_id:
            raise HTTPException(404, 'Activity not found in this project.')
    log_change(db, project_id, user.id, 'note', text, activity.id if activity else None)
    db.commit()
    return {'ok': True}


class DigestBody(BaseModel):
    digest: Literal['daily', 'off']


@router.get('/api/me/digest')
def my_digest(db: Session = Db, user=Auth):
    content = build_digest(db, user, since=None)
    return {'digest': user.digest, 'email_enabled': mail_enabled(), 'preview': content['text'] if content else None}


@router.put('/api/me/digest')
def set_digest(body: DigestBody, db: Session = Db, user=Auth):
    user.digest = body.digest
    db.add(user)
    db.commit()
    return {'digest': user.digest}


def build_digest(db, user, since):
    """What this person should know since `since`, in their role's order. Returns None when there is nothing to say."""
    from .warnings import due_warnings
    since = since or (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    query = select(Project).where(Project.organization_id == user.organization_id, Project.status != 'archived')
    if user.role not in ('owner', 'admin'):
        query = query.join(ProjectMember).where(ProjectMember.user_id == user.id)
    sections, any_content = [], False
    for p in db.scalars(query):
        role = project_role(db, p.id, user.id)
        events = list(db.scalars(select(ChangeEvent).where(ChangeEvent.project_id == p.id, ChangeEvent.created_at > since, ChangeEvent.user_id != user.id).order_by(ChangeEvent.created_at)))
        names = {u.id: person(u) for u in db.scalars(select(User).where(User.organization_id == user.organization_id))}
        due = [w for w in due_warnings(db, p) if w['overdue'] or w['days'] <= 2]
        lines = []
        changed = [f'  - {names.get(e.user_id) or "Someone"}: {e.summary}' for e in events]
        # The super runs the work, so what is due leads. The PM reviews, so what changed leads.
        if role == 'pm':
            blocks = [('What changed', changed), ('Due or overdue', [f'  - {w["title"]} ({"overdue" if w["overdue"] else "due " + w["due"]})' for w in due])]
        else:
            blocks = [('Due or overdue', [f'  - {w["title"]} ({"overdue" if w["overdue"] else "due " + w["due"]})' for w in due]), ('What changed', changed)]
        for title, items in blocks:
            if items:
                lines += [f'{title}:'] + items[:8] + ([f'  ...and {len(items) - 8} more'] if len(items) > 8 else [])
        if lines:
            any_content = True
            sections.append(f'{p.name.split("|")[0].strip()} ({ROLE_LABELS[role].lower()})\n' + '\n'.join(lines))
    if not any_content:
        return None
    text = f'Good morning {person(user).split()[0]}. Here is what needs your attention.\n\n' + '\n\n'.join(sections) + f'\n\nOpen SiteSync: {settings.app_url}\nOne summary a day, only when something changed. Turn it off in Settings.'
    return {'text': text}


def run_digests(db):
    """Send at most one digest per person per day. Safe to call as often as you like."""
    sent = 0
    if not mail_enabled():
        return {'sent': 0, 'reason': 'Email is not configured.'}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DIGEST_MIN_HOURS)
    for u in db.scalars(select(User).where(User.digest == 'daily', User.email_verified == True)):  # noqa: E712
        if u.digest_sent_at and datetime.fromisoformat(u.digest_sent_at) > cutoff:
            continue
        content = build_digest(db, u, since=u.digest_sent_at)
        if content and send_email(u.email, 'SiteSync: your daily project summary', content['text']):
            u.digest_sent_at = now()
            sent += 1
    db.commit()
    return {'sent': sent}


@router.api_route('/api/digests/run', methods=['GET', 'POST'])
def digests_run(authorization: str = Header(default=''), db: Session = Db):
    """Called once a day by a scheduler (Vercel Cron sends CRON_SECRET as a bearer token)."""
    secret = settings.cron_secret
    if not secret or not hmac.compare_digest(authorization, 'Bearer ' + secret):
        raise HTTPException(401, 'Not authorized.')
    return run_digests(db)
