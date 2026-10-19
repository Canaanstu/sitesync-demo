from sqlalchemy import delete, or_, select
from .database import Base
from .models import Organization, Project, User


def delete_workspace(db, org_id):
    """Remove an organization and everything that belongs to it, children before parents."""
    project_ids = list(db.scalars(select(Project.id).where(Project.organization_id == org_id)))
    user_ids = list(db.scalars(select(User.id).where(User.organization_id == org_id)))
    for table in reversed(Base.metadata.sorted_tables):
        if table.name == 'organizations':
            continue
        c = table.c
        if table.name in ('projects', 'users'):
            conds = [c.organization_id == org_id]
        else:
            conds = []
            if 'project_id' in c and project_ids:
                conds.append(c.project_id.in_(project_ids))
            if 'organization_id' in c:
                conds.append(c.organization_id == org_id)
            if 'user_id' in c and user_ids:
                conds.append(c.user_id.in_(user_ids))
        if conds:
            db.execute(delete(table).where(or_(*conds)))
    db.execute(delete(Organization).where(Organization.id == org_id))
