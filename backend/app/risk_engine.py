from datetime import date, timedelta
import re
from sqlalchemy import select
from .models import Procurement, Activity, RFI, Submittal, Email, Risk
from .progress import activity_progress


def day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def words(value):
    return set(re.findall(r'[a-z0-9]{3,}', (value or '').lower())) - {'the', 'and', 'for', 'with', 'this', 'that', 'work', 'installation', 'install'}


def related(a, b):
    return bool(words(a) & words(b))


def source(kind, item, label=None):
    return {'type': kind, 'id': item.id, 'label': label or getattr(item, 'name', None) or getattr(item, 'title', None) or getattr(item, 'subject', None)}


def run_rules(db, project_id, today=None):
    today = today or date.today()
    rows = lambda cls: list(db.scalars(select(cls).where(cls.project_id == project_id)))
    procurement, activities, rfis, submittals, emails = [rows(cls) for cls in (Procurement, Activity, RFI, Submittal, Email)]
    activities = [a for a in activities if not (a.raw_json or {}).get("superseded")]
    existing = {r.fingerprint: r for r in rows(Risk)}
    active = set()

    def add(rule, item, category, severity, title, description, action, sources, due=None, evidence=None):
        fingerprint = rule + ':' + item.id
        active.add(fingerprint)
        risk = existing.get(fingerprint)
        if not risk:
            risk = Risk(project_id=project_id, fingerprint=fingerprint)
            db.add(risk)
        # Preserve explicit dismiss/resolve decisions across reruns.
        for key, value in dict(category=category, severity=severity, title=title, description=description, recommended_action=action, source_records=sources, due_date=due, evidence=evidence or {}).items():
            setattr(risk, key, value)

    for p in procurement:
        required = day(p.required_on_site_date)
        latest = required - timedelta(days=p.lead_time_days) if required and p.lead_time_days is not None else None
        release_risk = latest and today > latest and (p.status or '').lower() not in ('released', 'ordered', 'delivered')
        if release_risk:
            add('release', p, 'procurement', 'high', f'{p.name} may miss the required date', f'Latest release was {latest}; status is {p.status or "unknown"}.', 'Confirm release and expedited delivery with the vendor.', [source('procurement', p)], p.required_on_site_date, {'latest_release_date': str(latest), 'lead_time_days': p.lead_time_days})
        for a in activities:
            start, delivery = day(a.start_date), day(p.expected_delivery_date)
            if start and delivery and delivery > start and activity_progress(db,a)[0] < 100 and related(p.name, a.name + ' ' + (a.trade or '')) and (p.status or '').lower() != 'delivered':
                add('delivery:' + a.id, p, 'schedule', 'high', f'{p.name} arrives after scheduled work', f'Expected {delivery}; {a.name} starts {start}.', 'Confirm the shipping date and coordinate the installation sequence.', [source('procurement', p), source('schedule', a)], str(start), {'days_late': (delivery - start).days})
        sub = next((s for s in submittals if s.id == p.submittal_id), None)
        if sub and release_risk and (sub.status or '').lower() not in ('approved', 'closed'):
            add('approval', p, 'submittal', 'high', f'{sub.title} blocks procurement', f'{p.name} has passed its release date and the linked submittal is {sub.status}.', 'Request the outstanding review before releasing procurement.', [source('submittals', sub), source('procurement', p)], sub.due_date)
    for r in rfis:
        if (r.status or '').lower() in ('closed', 'answered'):
            continue
        for a in activities:
            start = day(a.start_date)
            if start and today <= start <= today + timedelta(days=21) and activity_progress(db,a)[0] < 100 and related((r.subject or '') + ' ' + (r.question or ''), a.name + ' ' + (a.trade or '')):
                add('rfi:' + a.id, r, 'rfi', 'high' if (start - today).days <= 7 else 'medium', f'RFI {r.number} may affect {a.name}', f'An open RFI matches work starting {start}. The dependency needs confirmation.', 'Confirm the dependency and request an answer from the responsible reviewer.', [source('rfis', r), source('schedule', a)], r.due_date)
    for s in submittals:
        if day(s.due_date) and day(s.due_date) < today and (s.status or '').lower() not in ('approved', 'closed'):
            add('overdue', s, 'submittal', 'medium', f'{s.title} is past due', f'Review was due {s.due_date}; status is {s.status}.', 'Follow up with the reviewer and confirm the return date.', [source('submittals', s)], s.due_date)
    for e in emails:
        hits = [w for w in ('delay', 'lead time', 'backorder', 'late', 'expedited', 'missing', 'revised ship date', 'cannot install', 'awaiting approval') if re.search(r'\b' + re.escape(w) + r'\b', ((e.subject or '') + ' ' + (e.body_text or '')).lower())]
        if hits:
            add('email', e, 'email_followup', 'low', f'Review: {e.subject}', 'Communication contains a potential constraint; project impact is not yet confirmed.', 'Review the message and confirm whether the schedule is affected.', [source('emails', e)], evidence={'matched_terms': hits})
    for fingerprint, risk in existing.items():
        if fingerprint not in active and risk.status == 'open':
            risk.status = 'resolved'
    db.flush()
    return rows(Risk)
