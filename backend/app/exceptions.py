"""Exceptions, traced from the headline down to the work they put at risk.

Layer 1: what SiteSync flagged and why (the rule, in plain words, and how to clear it).
Layer 2: the records that triggered it, with the facts that matter.
Layer 3: what it affects downstream: activities and inspections, and how soon.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db
from .models import Project, ProjectMember, Risk, Procurement, Activity, RFI, Submittal, Email, Workflow, public
from .planning import local_today
from .risk_engine import day, related
from .rules import GUIDE, rule_config
from .security import current_user, project_access

router = APIRouter()
Db, Auth = Depends(get_db), Depends(current_user)

MODELS = {'procurement': Procurement, 'schedule': Activity, 'rfis': RFI, 'submittals': Submittal, 'emails': Email}
FACTS = {
    'procurement': [('vendor', 'Vendor'), ('status', 'Status'), ('lead_time_days', 'Lead time (days)'), ('release_date', 'Released'), ('expected_delivery_date', 'Expected delivery'), ('required_on_site_date', 'Required on site')],
    'schedule': [('trade', 'Trade'), ('start_date', 'Starts'), ('finish_date', 'Finishes'), ('percent_complete', '% complete')],
    'rfis': [('number', 'RFI #'), ('status', 'Status'), ('due_date', 'Response due'), ('ball_in_court', 'With')],
    'submittals': [('number', 'Submittal #'), ('status', 'Status'), ('due_date', 'Review due'), ('ball_in_court', 'With'), ('spec_section', 'Spec section')],
    'emails': [('sender_name', 'From'), ('received_at', 'Received')],
}
SEVERITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def rule_of(risk):
    return (risk.fingerprint or '').split(':')[0]


def resolve(db, project_id, src):
    cls = MODELS.get(src.get('type'))
    row = db.get(cls, src.get('id')) if cls else None
    if not row or row.project_id != project_id:
        return {'type': src.get('type'), 'id': src.get('id'), 'label': src.get('label') or 'Removed record', 'facts': [], 'missing': True}
    facts = [{'label': label, 'value': getattr(row, key)} for key, label in FACTS[src['type']] if getattr(row, key, None) not in (None, '')]
    return {'type': src['type'], 'id': row.id, 'label': src.get('label'), 'facts': facts, 'missing': False}


def affected(db, project, risk, today):
    """Activities (and inspections) this exception puts at risk, soonest first."""
    activities = [a for a in db.scalars(select(Activity).where(Activity.project_id == project.id)) if not (a.raw_json or {}).get('superseded')]
    chosen = {}
    for src in risk.source_records or []:
        if src.get('type') == 'schedule':
            chosen[src['id']] = 'named in the exception'
    for src in risk.source_records or []:
        if src.get('type') == 'procurement':
            item = db.get(Procurement, src['id'])
            if not item:
                continue
            linked = (item.raw_json or {}).get('activity_ids') or []
            for a in activities:
                if a.id in linked:
                    chosen.setdefault(a.id, 'linked to this item')
                elif not linked and related(item.name, a.name + ' ' + (a.trade or '')):
                    chosen.setdefault(a.id, 'name matches')
        elif src.get('type') in ('rfis', 'submittals'):
            rec = db.get(RFI if src['type'] == 'rfis' else Submittal, src['id'])
            text = ((getattr(rec, 'subject', None) or getattr(rec, 'title', None) or '') + ' ' + (getattr(rec, 'question', None) or getattr(rec, 'description', None) or '')) if rec else ''
            for a in activities:
                if related(text, a.name + ' ' + (a.trade or '')):
                    chosen.setdefault(a.id, 'name matches')
    out = []
    for a in activities:
        if a.id not in chosen or (a.percent_complete or 0) >= 100:
            continue
        start = day(a.start_date)
        out.append({'id': a.id, 'name': a.name, 'trade': a.trade, 'start_date': a.start_date, 'finish_date': a.finish_date, 'percent_complete': a.percent_complete or 0,
                    'days_until_start': (start - today).days if start else None, 'why': chosen[a.id]})
    out.sort(key=lambda x: (x['days_until_start'] is None, x['days_until_start'] or 0))
    ids = {a['id'] for a in out}
    inspections = [{'id': i.id, 'name': i.data.get('name'), 'scheduled_date': i.data.get('scheduled_date'), 'status': i.status}
                   for i in db.scalars(select(Workflow).where(Workflow.project_id == project.id, Workflow.kind == 'inspection'))
                   if ids & set(i.data.get('blocks_activity_ids') or []) and i.status not in ('passed',)]
    return out, inspections


def consequences(risk, work, inspections):
    lines = []
    late = (risk.evidence or {}).get('days_late')
    for a in work[:3]:
        d = a['days_until_start']
        when = 'is already due to start' if d is not None and d < 0 else 'starts today' if d == 0 else f'starts in {d} day{"" if d == 1 else "s"}' if d is not None else 'has no start date'
        start = day(a['start_date'])
        lines.append(f"{a['name']} {when}" + (f" ({start.strftime('%b')} {start.day})" if start else '') + '.')
    if late:
        lines.append(f'The material is expected {late} days after that work is meant to begin.')
    for i in inspections[:2]:
        lines.append(f"The inspection \"{i['name']}\" depends on this work, so it moves too.")
    return lines or ['Nothing in the schedule is linked to this yet. Link the item to an activity on the Materials tab so its impact shows up here.']


def trace(db, project, risk, today=None):
    today = today or local_today(project)
    rule = rule_of(risk)
    guide = GUIDE.get(rule)
    work, inspections = affected(db, project, risk, today)
    cfg = rule_config(project)
    return {
        'rule': rule,
        'why': {'label': guide['label'], 'what': guide['what'], 'clears_when': guide['clears_when'], 'steps': guide['steps']} if guide else None,
        'rule_settings': {k: v for k, v in (cfg.get(rule) or {}).items() if k != 'enabled'} if rule in cfg else {},
        'evidence': [resolve(db, project.id, s) for s in (risk.source_records or [])],
        'affects': {'activities': work, 'inspections': inspections, 'summary': consequences(risk, work, inspections)},
    }


def accessible_projects(db, user):
    projects = list(db.scalars(select(Project).where(Project.organization_id == user.organization_id, Project.status != 'archived')))
    if user.role not in ('owner', 'admin'):
        member = {m.project_id for m in db.scalars(select(ProjectMember).where(ProjectMember.user_id == user.id))}
        projects = [p for p in projects if p.id in member]
    return projects


@router.get('/api/projects/{project_id}/risks/{risk_id}/trace')
def risk_trace(project_id: str, risk_id: str, db: Session = Db, user=Auth):
    project = project_access(db, user, project_id)
    risk = db.get(Risk, risk_id)
    if not risk or risk.project_id != project_id:
        raise HTTPException(404, 'Risk not found.')
    return trace(db, project, risk)


@router.get('/api/exceptions')
def exceptions(project_id: str | None = None, db: Session = Db, user=Auth):
    """Every open exception across the projects this person can open, most urgent first, each with its full trace."""
    if project_id:
        projects = [project_access(db, user, project_id)]
    else:
        projects = accessible_projects(db, user)
    items = []
    for project in projects:
        today = local_today(project)
        for risk in db.scalars(select(Risk).where(Risk.project_id == project.id, Risk.status.in_(('open', 'in_progress')))):
            items.append({**public(risk), 'project_name': project.name.split('|')[0].strip(), 'rule': rule_of(risk), 'trace': trace(db, project, risk, today)})
    items.sort(key=lambda r: (SEVERITY_ORDER.get(r['severity'], 3), r['due_date'] or '9999', r['title']))
    counts = {'high': 0, 'medium': 0, 'low': 0}
    for r in items:
        counts[r['severity']] = counts.get(r['severity'], 0) + 1
    return {'items': items, 'counts': counts, 'total': len(items)}
