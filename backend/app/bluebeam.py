"""Read-only Bluebeam demo. No external calls, OAuth tokens, or drawing downloads."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Connection, Document, Project, User, now
from .security import current_user, project_access, require_write

router=APIRouter(prefix='/api/integrations/bluebeam',tags=['Bluebeam demo'])
CATALOG=[
    {'id':'sample-studio-sage','name':'Sage and Sound','files':[
        {'id':'A101','name':'A101 - Lower Level Plan.pdf','revision':'C','discipline':'Architectural'},
        {'id':'E201','name':'E201 - Sauna Electrical Coordination.pdf','revision':'B','discipline':'Electrical'},
        {'id':'M101','name':'M101 - Mechanical Plan.pdf','revision':'A','discipline':'Mechanical'}]},
    {'id':'sample-studio-alo','name':'Alo Yoga','files':[
        {'id':'A101','name':'A101 - Retail Floor Plan.pdf','revision':'D','discipline':'Architectural'},
        {'id':'E101','name':'E101 - Lighting Control Plan.pdf','revision':'C','discipline':'Electrical'},
        {'id':'A501','name':'A501 - Millwork Details.pdf','revision':'B','discipline':'Architectural'}]}
]

def connection(db,user,required=False):
    row=db.scalar(select(Connection).where(Connection.organization_id==user.organization_id,Connection.provider=='bluebeam'))
    if required and (not row or row.status!='demo'):
        raise HTTPException(409,'Connect the Bluebeam sample before importing.')
    return row

def demo_only():
    if not settings.demo_mode:
        raise HTTPException(409,'Bluebeam is a demo preview. Live Studio OAuth is not configured on this deployment.')

@router.get('/status')
def status(db:Session=Depends(get_db),user=Depends(current_user)):
    row=connection(db,user)
    owner=db.get(User,row.provider_account_id) if row else None
    stamps=[(r.raw_json or {}).get('last_synced_at') for r in db.scalars(select(Document).join(Project).where(Project.organization_id==user.organization_id)) if (r.raw_json or {}).get('provider')=='bluebeam']
    return {'status':'sample connected' if row and row.status=='demo' else 'disconnected','demo_mode':settings.demo_mode,
        'connection_owner':owner.full_name if owner else None,'can_manage':user.role!='viewer','can_disconnect':user.role!='viewer' and (not row or row.provider_account_id==user.id or user.role in ('owner','admin')),
        'scopes':['read_prime (simulated)'],'region':'US (sample)','last_synced_at':max(filter(None,stamps),default=None)}

@router.post('/connect')
def connect(db:Session=Depends(get_db),user=Depends(current_user)):
    require_write(user);demo_only()
    row=connection(db,user)
    if row and row.status!='demo':
        raise HTTPException(409,'This preview cannot modify a live Bluebeam connection.')
    if not row:
        row=Connection(organization_id=user.organization_id,provider='bluebeam',provider_account_id=user.id,status='demo',scopes=['read_prime'])
        db.add(row)
    db.commit()
    return {'message':'Sample connected. No Bluebeam account was contacted.'}

@router.get('/projects')
def projects(db:Session=Depends(get_db),user=Depends(current_user)):
    demo_only();connection(db,user,True)
    return [{'id':p['id'],'name':p['name'],'file_count':len(p['files']),'demo':True} for p in CATALOG]

class Sync(BaseModel):
    project_id:str
    studio_project_id:str

@router.post('/sync')
def sync(body:Sync,db:Session=Depends(get_db),user=Depends(current_user)):
    require_write(user);demo_only();row=connection(db,user,True)
    project_access(db,user,body.project_id)
    studio=next((p for p in CATALOG if p['id']==body.studio_project_id),None)
    if not studio:raise HTTPException(404,'Studio sample project not found.')
    stamp=now();records=[]
    for file in studio['files']:
        external=f"bluebeam:{studio['id']}:{file['id']}"
        doc=db.scalar(select(Document).where(Document.project_id==body.project_id,Document.source_external_id==external))
        if not doc:
            doc=Document(project_id=body.project_id,source_external_id=external)
            db.add(doc)
        doc.filename=file['name'];doc.file_type='pdf';doc.revision=file['revision']
        doc.raw_text='' # Metadata is not drawing evidence and must not be used as drawing contents.
        doc.raw_json={'provider':'bluebeam','studio_project_id':studio['id'],'studio_project_name':studio['name'],
            'file_id':file['id'],'discipline':file['discipline'],'last_synced_at':stamp,'metadata_only':True,'demo':True}
        db.flush()
        records.append({'id':doc.id,'filename':doc.filename,'revision':doc.revision,'discipline':file['discipline'],'source_id':external,'demo':True})
    db.commit()
    return {'message':f"{len(records)} sample file records refreshed. Drawing contents were not downloaded.",
        'last_synced_at':stamp,'records':records,'project_id':body.project_id}

@router.delete('/connection')
def disconnect(db:Session=Depends(get_db),user=Depends(current_user)):
    require_write(user)
    row=connection(db,user)
    if row:
        if row.status!='demo':raise HTTPException(409,'This preview cannot disconnect a live Bluebeam connection.')
        if row.provider_account_id!=user.id and user.role not in ('owner','admin'):raise HTTPException(403,'Only the person who connected the sample, or an administrator, can disconnect it.')
        db.delete(row);db.commit()
    return {'message':'Sample disconnected. Previously imported metadata remains in Project documents. No external grant existed.'}
