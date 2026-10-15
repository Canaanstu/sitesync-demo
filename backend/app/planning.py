"""Scheduling calculations are deterministic. AI proposes durations; people approve baselines."""
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .models import Activity, Procurement, Workflow, public
from .progress import activity_progress


def local_today(project):
    try:
        return datetime.now(ZoneInfo(project.settings.get('timezone', 'America/New_York'))).date()
    except Exception:
        return date.today()


def business_day(day, weekdays=(0, 1, 2, 3, 4), holidays=()):
    for _ in range(3700):
        if day.weekday() in weekdays and day.isoformat() not in holidays:
            return day
        day += timedelta(days=1)
    raise ValueError('No available working dates in the calendar.')


def finish_on(start, duration, weekdays=(0, 1, 2, 3, 4), holidays=()):
    finish = business_day(start, weekdays, holidays)
    for _ in range(max(1, duration) - 1):
        finish = business_day(finish + timedelta(days=1), weekdays, holidays)
    return finish


def schedule_tasks(tasks, start, weekdays=(0, 1, 2, 3, 4), holidays=()):
    if not weekdays or any(d not in range(7) for d in weekdays):
        raise ValueError('Select at least one valid working day.')
    if not tasks or len(tasks) > 150:
        raise ValueError('A schedule must contain 1-150 activities.')
    ids = [t['task_id'] for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError('Task IDs must be unique.')
    finished, result, pending = {}, [], list(tasks)
    while pending:
        ready = [t for t in pending if all(p in finished for p in t.get('predecessors', []))]
        if not ready:
            raise ValueError('Dependencies contain a cycle or an unknown activity.')
        for task in ready:
            duration = task['duration_days']
            if not isinstance(duration, int) or isinstance(duration, bool) or not 1 <= duration <= 365:
                raise ValueError('Durations must be 1-365 working days.')
            earliest = start
            if task.get('predecessors'):
                earliest = max([start] + [finished[p] + timedelta(days=1) for p in task['predecessors']])
            if task.get('not_before'):
                earliest = max(earliest, date.fromisoformat(task['not_before']))
            begins = business_day(earliest, weekdays, holidays)
            ends = finish_on(begins, duration, weekdays, holidays)
            finished[task['task_id']] = ends
            result.append({**task, 'start_date': begins.isoformat(), 'finish_date': ends.isoformat(), 'percent_complete': task.get('percent_complete', 0)})
            pending.remove(task)
    return result


def template_tasks(job_type, description):
    wellness = 'wellness' in (job_type + ' ' + description).lower() or 'spa' in description.lower()
    return [
        {'task_id': 'T01', 'name': 'Mobilization and field verification', 'trade': 'General', 'duration_days': 2, 'predecessors': []},
        {'task_id': 'T02', 'name': 'Selective demolition and layout', 'trade': 'Demolition', 'duration_days': 5, 'predecessors': ['T01']},
        {'task_id': 'T03', 'name': 'Framing and backing', 'trade': 'Carpentry', 'duration_days': 5, 'predecessors': ['T02']},
        {'task_id': 'T04', 'name': 'Electrical rough-in', 'trade': 'Electrical', 'duration_days': 5, 'predecessors': ['T03']},
        {'task_id': 'T05', 'name': 'Plumbing and mechanical rough-in', 'trade': 'Plumbing', 'duration_days': 7 if wellness else 5, 'predecessors': ['T03']},
        {'task_id': 'T06', 'name': 'Rough-in inspection hold point', 'trade': 'Inspection', 'duration_days': 1, 'predecessors': ['T04', 'T05']},
        {'task_id': 'T07', 'name': 'Drywall, ceiling close and finishes', 'trade': 'Drywall', 'duration_days': 8, 'predecessors': ['T06']},
        {'task_id': 'T08', 'name': 'Flooring and tile', 'trade': 'Flooring', 'duration_days': 5, 'predecessors': ['T07']},
        {'task_id': 'T09', 'name': 'Millwork and fixture installation', 'trade': 'Millwork', 'duration_days': 5, 'predecessors': ['T08']},
        {'task_id': 'T10', 'name': 'MEP trim and commissioning', 'trade': 'Electrical', 'duration_days': 4, 'predecessors': ['T08']},
        {'task_id': 'T11', 'name': 'Final inspections and punch list', 'trade': 'Inspection', 'duration_days': 3, 'predecessors': ['T09', 'T10']},
        {'task_id': 'T12', 'name': 'Owner walk-through and turnover', 'trade': 'General', 'duration_days': 1, 'predecessors': ['T11']},
    ]


def workboard(db, project, today=None):
    today = today or local_today(project)
    weekdays = tuple(project.settings.get('workdays', [0, 1, 2, 3, 4]))
    holidays = project.settings.get('holidays', [])
    activities = [a for a in db.scalars(select(Activity).where(Activity.project_id == project.id)) if not (a.raw_json or {}).get('superseded')]
    inspections = list(db.scalars(select(Workflow).where(Workflow.project_id == project.id, Workflow.kind == 'inspection')))
    items = list(db.scalars(select(Procurement).where(Procurement.project_id == project.id)))
    progress_values = {a.id: activity_progress(db,a) for a in activities}
    by_id = {a.id: a for a in activities}
    aliases = {a.activity_id: a.id for a in activities if a.activity_id}
    result, projected = [], {}
    pending = list(activities)
    for _ in range(len(activities) + 1):
        if not pending:
            break
        progressed = False
        for a in list(pending):
            preds = [aliases.get(p, p) for p in (a.predecessor_ids or [])]
            if any(p in by_id and p not in projected for p in preds):
                continue
            data = a.raw_json or {}
            complete = progress_values[a.id][0] >= 100
            actual = data.get('actual_finish')
            blockers = []
            earliest = max(today, date.fromisoformat(a.start_date)) if a.start_date else today
            for pred in preds:
                if pred not in by_id:
                    blockers.append('Unknown predecessor: ' + pred)
                elif progress_values[pred][0] < 100:
                    blockers.append('Finish ' + by_id[pred].name)
                if pred in projected:
                    earliest = max(earliest, projected[pred] + timedelta(days=1))
            for i in inspections:
                if a.id in i.data.get('blocks_activity_ids', []) and i.status != 'passed':
                    blockers.append(f"Inspection: {i.data['name']} ({i.status})")
                    if i.data.get('scheduled_date'):
                        earliest = max(earliest, date.fromisoformat(i.data['scheduled_date']) + timedelta(days=1))
            for item in items:
                if a.id in (item.raw_json or {}).get('activity_ids', []) and item.status != 'delivered':
                    blockers.append('Delivery: ' + item.name)
                    if item.expected_delivery_date:
                        earliest = max(earliest, date.fromisoformat(item.expected_delivery_date))
            baseline_days = 1
            if a.start_date and a.finish_date:
                first, last = date.fromisoformat(a.start_date), date.fromisoformat(a.finish_date)
                baseline_days = max(1, sum((first + timedelta(days=n)).weekday() in weekdays and (first + timedelta(days=n)).isoformat() not in holidays for n in range(max(0, (last-first).days + 1))))
            duration = data.get('duration_days', baseline_days)
            remaining = max(1, math.ceil(duration * (1 - progress_values[a.id][0] / 100)))
            projected[a.id] = date.fromisoformat(actual or a.finish_date or today.isoformat()) if complete else finish_on(earliest, remaining, weekdays, holidays)
            if complete:
                status = 'complete'
            elif blockers:
                status = 'blocked'
            elif a.finish_date and a.finish_date < today.isoformat():
                status = 'overdue'
            elif not a.start_date or a.start_date <= today.isoformat():
                status = 'today'
            else:
                status = 'upcoming'
            result.append({**public(a), 'percent_complete':progress_values[a.id][0], 'progress_note':progress_values[a.id][1], 'work_status': status, 'blockers': blockers, 'remaining_workdays': 0 if complete else remaining, 'forecast_start': earliest.isoformat(), 'forecast_finish': projected[a.id].isoformat()})
            pending.remove(a)
            progressed = True
        if not progressed:
            break
    for a in pending:
        result.append({**public(a), 'percent_complete':progress_values[a.id][0], 'progress_note':progress_values[a.id][1], 'work_status': 'blocked', 'blockers': ['Dependency cycle - review schedule'], 'forecast_finish': None, 'remaining_workdays': None})
    forecast = max(projected.values()).isoformat() if projected else None
    variance = (date.fromisoformat(forecast) - date.fromisoformat(project.finish_date)).days if forecast and project.finish_date else None
    unknown_constraints = [i for i in inspections if i.status != 'passed' and (not i.data.get('scheduled_date') or any(k not in by_id for k in i.data.get('blocks_activity_ids', [])))]
    unknown_constraints += [i for i in items if i.status != 'delivered' and any(k not in by_id for k in (i.raw_json or {}).get('activity_ids', []))]
    return {'as_of': today.isoformat(), 'turnover_date': project.finish_date, 'forecast_finish': forecast, 'variance_days': variance, 'forecast_is_conditional': bool(unknown_constraints or pending or any(r['blockers'] for r in result)), 'activities': sorted(result, key=lambda a: (a.get('start_date') or '', a['name'])), 'inspections': [public(i) for i in inspections], 'today': [r for r in result if r['work_status'] in ('today', 'overdue')], 'blocked': [r for r in result if r['work_status'] == 'blocked'], 'complete': sum(r['work_status'] == 'complete' for r in result)}
