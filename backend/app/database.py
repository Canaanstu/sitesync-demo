import os
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


_sqlite = settings.database_url.startswith('sqlite')
# Serverless instances open few connections each; recycle quickly so pooled Postgres (Neon) can drop idle ones.
# A connection that silently died (a frozen serverless instance, a database that scaled to zero) must fail within seconds
# rather than hang a request until the platform kills it after 60 seconds.
_pg_args = {'connect_timeout': 10, 'keepalives': 1, 'keepalives_idle': 15, 'keepalives_interval': 5, 'keepalives_count': 3, 'tcp_user_timeout': 15000}
if _sqlite:
    engine = create_engine(settings.database_url, connect_args={'check_same_thread': False}, pool_pre_ping=True)
elif os.getenv('VERCEL'):
    # Serverless instances freeze between requests, which leaves pooled connections stale. Let the host's pooler do the pooling.
    engine = create_engine(settings.database_url, connect_args=_pg_args, poolclass=NullPool)
else:
    engine = create_engine(settings.database_url, connect_args=_pg_args, pool_pre_ping=True, pool_size=3, max_overflow=2, pool_recycle=240)
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_fk(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
