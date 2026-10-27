from sqlalchemy import select
from fastapi import HTTPException
from .database import SessionLocal
from .models import *
from .config import settings, procore_sandbox_live
from .connectors import valid_token, Procore, Microsoft
from .risk_engine import run_rules
from .parsing import parse_table
from .ai import embed


def match_email(email, project):
    text = ((email.get('subject') or '') + ' ' + (email.get('body', {}).get('content') or '')).lower()
    aliases = [project.name] + project.settings.get('aliases', []) + project.settings.get('email_keywords', [])
    return any(len(alias.strip()) >= 3 and alias.lower().strip() in text for alias in aliases)


def plain_text(value):
    """Procore sends rich text as HTML; keep the words, drop the tags."""
    import html
    import re
    text = re.sub(r'<(br|/p|/div|/li)\s*/?>', '\n', str(value or ''), flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', '', text)).strip()


def normalize_status(value):
    if isinstance(value, dict):
        value = value.get('name') or value.get('status') or 'unknown'
    return str(value or 'unknown').lower()


def upsert(db, cls, project_id, external_id, values):
    row = db.scalar(select(cls).where(cls.project_id == project_id, cls.source_external_id == str(external_id)))
    if row is None:
        row = cls(project_id=project_id, source_external_id=str(external_id))
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    return row


def ingest_rows(db, project_id, rows, kind, source_key):
    cls = Activity if kind == 'schedule' else Procurement
    allowed = set(cls.__table__.columns.keys()) - {'id', 'project_id', 'created_at', 'source_external_id', 'raw_json'}
    for index, row in enumerate(rows):
        values = {k: v for k, v in row.items() if k in allowed}
        if kind != 'schedule' and row.get('submittal'):
            sub = db.scalar(select(Submittal).where(Submittal.project_id == project_id, Submittal.number == row['submittal']))
            if not sub:
                raise ValueError(f'Submittal {row["submittal"]} was not found in this project.')
            values['submittal_id'] = sub.id
        upsert(db, cls, project_id, source_key + ':' + str(index), dict(values, raw_json=row))


def generate_embeddings(project_id):
    with SessionLocal() as db:
        rows = list(db.scalars(select(Chunk).where(Chunk.project_id == project_id, Chunk.embedding.is_(None))))
        for start in range(0, len(rows), 32):
            batch = rows[start:start + 32]
            vectors = embed([c.text for c in batch])
            if vectors:
                for chunk, vector in zip(batch, vectors):
                    chunk.embedding = vector
                db.commit()


def sync_project(job_id):
    with SessionLocal() as db:
        job = db.get(SyncJob, job_id)
        if not job:
            return
        job.status = 'running'
        db.commit()
        try:
            project = db.get(Project, job.project_id)
            counts = []
            if not settings.demo_mode or procore_sandbox_live:
                connections = {c.provider: c for c in db.scalars(select(Connection).where(Connection.organization_id == project.organization_id))}
                if project.procore_project_id and project.external_source != 'demo':
                    connection = connections.get('procore')
                    if not connection:
                        raise HTTPException(409, 'Connect Procore to sync this project.')
                    client = Procore(valid_token(db, connection), project.procore_company_id)
                    for kind, cls, records in [('RFIs', RFI, client.rfis(project.procore_project_id)), ('submittals', Submittal, client.submittals(project.procore_project_id))]:
                        for r in records:
                            values = {'number': '' if r.get('number') is None else str(r['number']), 'status': normalize_status(r.get('status')), 'due_date': (r.get('due_date') or '')[:10] or None, 'raw_json': r}
                            if cls == RFI:
                                values.update(subject=r.get('subject'), question=plain_text(r.get('question') or ((r.get('questions') or [{}])[0].get('plain_text_body') or (r.get('questions') or [{}])[0].get('body') or '')), response=str(r.get('response') or ''))
                            else:
                                values.update(title=r.get('title'), description=r.get('description'))
                            upsert(db, cls, project.id, r['id'], values)
                        counts.append(f'{len(records)} {kind}')
                if 'microsoft' in connections and not settings.demo_mode:
                    graph = Microsoft(valid_token(db, connections['microsoft']))
                    matching = [e for e in graph.messages() if match_email(e, project)]
                    for e in matching:
                        sender = e.get('from', {}).get('emailAddress', {})
                        upsert(db, Email, project.id, e['id'], {'subject': e.get('subject'), 'sender_email': sender.get('address'), 'sender_name': sender.get('name'), 'received_at': e.get('receivedDateTime'), 'body_text': e.get('body', {}).get('content', ''), 'recipients': e.get('toRecipients', []), 'raw_json': e})
                    counts.append(f'{len(matching)} matched emails')
                    for workbook in project.settings.get('workbooks', []):
                        data, name = graph.download_file(workbook['drive_id'], workbook['item_id'])
                        ingest_rows(db, project.id, parse_table(data, name, workbook['kind']), workbook['kind'], 'graph:' + workbook['item_id'])
                if not counts and not project.settings.get('workbooks') and not settings.demo_mode:
                    counts.append('No connected sources; local records evaluated')
            if counts:
                # Log a sync only when it found something different, so syncing five times a day adds no noise to the feed.
                from .collab import log_change
                summary = 'Procore sync: ' + ', '.join(counts)
                last = db.scalar(select(ChangeEvent).where(ChangeEvent.project_id == project.id, ChangeEvent.kind == 'sync').order_by(ChangeEvent.created_at.desc()))
                if not last or last.summary != summary:
                    log_change(db, project.id, None, 'sync', summary)
            db.flush()
            run_rules(db, project.id)
            job.status = 'complete'
            job.detail = 'Demo records evaluated; no provider contacted.' if settings.demo_mode and not counts else 'Synced: ' + ', '.join(counts)
            job.finished_at = now()
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(SyncJob, job_id)
            job.status = 'failed'
            job.detail = exc.detail if isinstance(exc, HTTPException) else 'Sync failed. Check the connection and file mapping, then retry.'
            job.finished_at = now()
            db.commit()


def enqueue_due():
    """Invoke every minute with the included scheduler; intervals come from project settings."""
    import datetime
    from redis import Redis
    from rq import Queue
    queue = Queue(connection=Redis.from_url(settings.redis_url))
    with SessionLocal() as db:
        for p in db.scalars(select(Project)):
            if not p.settings.get('sync_enabled'):
                continue
            last = db.scalar(select(SyncJob).where(SyncJob.project_id == p.id).order_by(SyncJob.created_at.desc()))
            if last and last.status in ('queued', 'running'):
                if (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(last.created_at)).total_seconds() < 1800:
                    continue
                last.status, last.detail = 'failed', 'Worker timed out; a new sync will be queued.'
            if last and (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(last.created_at)).total_seconds() < p.settings.get('sync_minutes', 15) * 60:
                continue
            job = SyncJob(project_id=p.id)
            db.add(job)
            db.commit()
            queue.enqueue(sync_project, job.id, job_timeout=1200)
