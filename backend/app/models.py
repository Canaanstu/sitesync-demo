from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, JSON, ForeignKey, UniqueConstraint, LargeBinary, true
from pgvector.sqlalchemy import Vector
from .database import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Identity:
    id = Column(String(36), primary_key=True, default=uid)
    created_at = Column(String, default=now)


class Organization(Identity, Base):
    __tablename__ = 'organizations'
    name = Column(String, nullable=False)
    # Shared with teammates so they can join this company at sign-up. Only owners and admins can read it.
    invite_code = Column(String, unique=True)


class LaunchRequest(Identity, Base):
    __tablename__ = 'launch_requests'
    email_hash = Column(String(64),nullable=False)
    email_encrypted = Column(Text,nullable=False)
    company_encrypted = Column(Text,nullable=False)
    interest = Column(String,nullable=False)
    consent_version = Column(String,nullable=False)
    __table_args__ = (UniqueConstraint('email_hash','interest'),)


class User(Identity, Base):
    __tablename__ = 'users'
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=False)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    role = Column(String, default='member')
    password_hash = Column(String, nullable=False)
    # Existing accounts predate verification, so the column defaults to verified; sign-up sets it explicitly.
    email_verified = Column(Boolean, nullable=False, default=False, server_default=true())
    # 'daily' = one summary email per day, and only when something changed. 'off' = in-app feed only.
    digest = Column(String, nullable=False, default='daily', server_default='daily')
    digest_sent_at = Column(String)


class Project(Identity, Base):
    __tablename__ = 'projects'
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=False)
    name = Column(String, nullable=False)
    external_source = Column(String, default='manual')
    procore_company_id = Column(String)
    procore_project_id = Column(String)
    status = Column(String, default='active')
    start_date = Column(String)
    finish_date = Column(String)
    settings = Column(JSON, default=dict)
    __table_args__ = (UniqueConstraint('organization_id', 'procore_company_id', 'procore_project_id'),)


class ProjectMember(Base):
    __tablename__ = 'project_members'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    # What this person does on this project: 'super' runs the schedule from the field, 'pm' reviews it, 'member' is everyone else.
    role = Column(String, nullable=False, default='member', server_default='member')


class Connection(Identity, Base):
    __tablename__ = 'integration_connections'
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=False)
    provider = Column(String, nullable=False)
    provider_account_id = Column(String)
    access_token_encrypted = Column(Text)
    refresh_token_encrypted = Column(Text)
    expires_at = Column(Float)
    scopes = Column(JSON, default=list)
    status = Column(String, default='connected')
    __table_args__ = (UniqueConstraint('organization_id', 'provider'),)


class ProjectRecord(Identity):
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    source_external_id = Column(String)
    raw_json = Column(JSON, default=dict)


class RFI(ProjectRecord, Base):
    __tablename__ = 'rfis'
    number = Column(String)
    subject = Column(String)
    question = Column(Text)
    response = Column(Text)
    status = Column(String)
    due_date = Column(String)
    ball_in_court = Column(String)


class Submittal(ProjectRecord, Base):
    __tablename__ = 'submittals'
    number = Column(String)
    title = Column(String)
    description = Column(Text)
    status = Column(String)
    due_date = Column(String)
    required_on_site_date = Column(String)
    lead_time_days = Column(Integer)
    ball_in_court = Column(String)
    spec_section = Column(String)


class Procurement(ProjectRecord, Base):
    __tablename__ = 'procurement_items'
    name = Column(String, nullable=False)
    vendor = Column(String)
    status = Column(String)
    lead_time_days = Column(Integer)
    required_on_site_date = Column(String)
    expected_delivery_date = Column(String)
    release_date = Column(String)
    submittal_id = Column(String, ForeignKey('submittals.id'))
    notes = Column(Text)


class Activity(ProjectRecord, Base):
    __tablename__ = 'schedule_activities'
    activity_id = Column(String)
    name = Column(String, nullable=False)
    trade = Column(String)
    start_date = Column(String)
    finish_date = Column(String)
    percent_complete = Column(Float, default=0)
    predecessor_ids = Column(JSON, default=list)
    successor_ids = Column(JSON, default=list)


class Email(ProjectRecord, Base):
    __tablename__ = 'emails'
    subject = Column(String)
    sender_email = Column(String)
    sender_name = Column(String)
    received_at = Column(String)
    body_text = Column(Text)
    recipients = Column(JSON, default=list)


class Document(ProjectRecord, Base):
    __tablename__ = 'documents'
    filename = Column(String, nullable=False)
    file_type = Column(String)
    revision = Column(String)
    is_current = Column(Boolean, default=True)
    raw_text = Column(Text)


class Chunk(Identity, Base):
    __tablename__ = 'document_chunks'
    document_id = Column(String, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    chunk_index = Column(Integer)
    text = Column(Text)
    page_number = Column(Integer)
    embedding = Column(JSON().with_variant(Vector(1536), 'postgresql'))


class Risk(ProjectRecord, Base):
    __tablename__ = 'risk_items'
    fingerprint = Column(String, nullable=False)
    title = Column(String)
    category = Column(String)
    severity = Column(String)
    status = Column(String, default='open')
    description = Column(Text)
    evidence = Column(JSON, default=dict)
    recommended_action = Column(Text)
    due_date = Column(String)
    source_records = Column(JSON, default=list)
    __table_args__ = (UniqueConstraint('project_id', 'fingerprint'),)


class Message(Identity, Base):
    __tablename__ = 'ai_messages'
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    role = Column(String)
    content = Column(Text)
    sources = Column(JSON, default=list)


class ChatMessage(Identity, Base):
    """Crew chat: messages between the people who share a project, separate from the private AI assistant history."""
    __tablename__ = 'chat_messages'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    body = Column(Text, nullable=False, default='')
    mentions = Column(JSON, default=list)
    edited_at = Column(String)


class ChatFile(Identity, Base):
    __tablename__ = 'chat_files'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    message_id = Column(String, ForeignKey('chat_messages.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)


class ChatRead(Base):
    """When each person last opened a project's chat, so unread counts are per person."""
    __tablename__ = 'chat_reads'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    last_read_at = Column(String, nullable=False)


class ChangeEvent(Identity, Base):
    """What changed on a project and who changed it: the team's change feed, field notes and the source of the daily digest."""
    __tablename__ = 'change_events'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='SET NULL'))
    kind = Column(String, nullable=False)  # schedule | note | import | sync
    summary = Column(Text, nullable=False)
    record_id = Column(String)


class FeedRead(Base):
    """When each person last opened a project's change feed, so 'new since you looked' is per person."""
    __tablename__ = 'feed_reads'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    last_read_at = Column(String, nullable=False)


class SyncJob(Identity, Base):
    __tablename__ = 'sync_jobs'
    project_id = Column(String, ForeignKey('projects.id'), nullable=False)
    status = Column(String, default='queued')
    detail = Column(Text)
    finished_at = Column(String)


class Audit(Identity, Base):
    __tablename__ = 'audit_logs'
    organization_id = Column(String, ForeignKey('organizations.id'), nullable=False)
    user_id = Column(String)
    action = Column(String)
    detail = Column(JSON, default=dict)


class Workflow(Identity, Base):
    __tablename__ = 'workflows'
    project_id = Column(String, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    status = Column(String, default='draft')
    data = Column(JSON, default=dict)
    updated_at = Column(String, default=now)
    __table_args__ = (UniqueConstraint('project_id', 'kind', 'key'),)


RECORDS = {'rfis': RFI, 'submittals': Submittal, 'procurement': Procurement, 'schedule': Activity, 'emails': Email, 'documents': Document}


def public(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in ('password_hash', 'access_token_encrypted', 'refresh_token_encrypted', 'invite_code')}
