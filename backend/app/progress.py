"""Completion comes from explicitly linked evidence, never elapsed calendar time."""
from sqlalchemy import select
from .models import Activity, Workflow, Procurement


def activity_progress(db, activity):
    rule=(activity.raw_json or {}).get('progress_source') or {}
    kind, identity=rule.get('kind'),rule.get('id')
    if kind=='inspection':
        row=db.scalar(select(Workflow).where(Workflow.id==identity,Workflow.project_id==activity.project_id,Workflow.kind=='inspection'))
        return (100 if row and row.status=='passed' else 0), ('Automatic: inspection passed' if row and row.status=='passed' else 'Automatic: awaiting passed inspection')
    if kind=='delivery':
        row=db.scalar(select(Procurement).where(Procurement.id==identity,Procurement.project_id==activity.project_id))
        return (100 if row and row.status=='delivered' else 0), ('Automatic: delivery received' if row and row.status=='delivered' else 'Automatic: awaiting full delivery')
    return activity.percent_complete or 0, 'Recorded field / imported progress'


def completion_summary(db, project_id):
    rows=[a for a in db.scalars(select(Activity).where(Activity.project_id==project_id)) if not (a.raw_json or {}).get('superseded')]
    return {'completion_percent':round(sum(activity_progress(db,a)[0] for a in rows)/len(rows)) if rows else None,'activity_count':len(rows)}
