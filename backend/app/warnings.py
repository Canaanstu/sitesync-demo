"""Things that come due within a week: shown on the calendar, in crew chat and as notifications."""
from datetime import date, timedelta
from sqlalchemy import select
from .models import Risk, Workflow, Procurement
from .planning import workboard, local_today

HORIZON_DAYS = 7


def due_warnings(db, project, horizon=HORIZON_DAYS):
    today = local_today(project)
    limit = today + timedelta(days=horizon)
    out = []

    def add(kind, key, title, due, section):
        try:
            d = date.fromisoformat(str(due)[:10])
        except (TypeError, ValueError):
            return
        if d > limit:
            return
        days = (d - today).days
        out.append({'key': f'{kind}:{key}', 'kind': kind, 'title': title, 'due': d.isoformat(), 'days': days, 'overdue': days < 0,
                    'project_id': project.id, 'project_name': project.name.split('|')[0].strip(), 'section': section})

    board = workboard(db, project, today)
    for a in board['activities']:
        if a['work_status'] == 'complete':
            continue
        add('work', a['id'], a['name'], (a.get('raw_json') or {}).get('due_date') or a.get('finish_date'), 'schedule')
    for i in db.scalars(select(Workflow).where(Workflow.project_id == project.id, Workflow.kind == 'inspection')):
        if i.status not in ('passed', 'failed') and i.data.get('scheduled_date'):
            add('inspection', i.id, 'Inspection: ' + i.data['name'], i.data['scheduled_date'], 'schedule')
    for p in db.scalars(select(Procurement).where(Procurement.project_id == project.id)):
        if (p.status or '') != 'delivered' and p.expected_delivery_date:
            add('delivery', p.id, 'Delivery: ' + p.name, p.expected_delivery_date, 'procurement')
    for r in db.scalars(select(Risk).where(Risk.project_id == project.id, Risk.status.in_(('open', 'in_progress')))):
        if r.due_date:
            add('task', r.id, r.title, r.due_date, 'overview')
    return sorted(out, key=lambda w: (w['due'], w['title']))
