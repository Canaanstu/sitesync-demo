from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


_sqlite = settings.database_url.startswith('sqlite')
# Serverless instances open few connections each; recycle quickly so pooled Postgres (Neon) can drop idle ones.
engine = create_engine(settings.database_url, connect_args={'check_same_thread': False} if _sqlite else {}, pool_pre_ping=True,
                       **({} if _sqlite else {'pool_size': 3, 'max_overflow': 2, 'pool_recycle': 240}))
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_fk(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
