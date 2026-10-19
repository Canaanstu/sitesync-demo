"""Project-scoped operational workflows. AI drafts, explicit approval applies changes."""
import base64
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Literal
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .database import get_db
from .models import Project, Activity, Procurement, Submittal, RFI, Risk, Email, Workflow, Connection, Audit, public, uid, now
from .security import current_user, project_access, require_write, require_admin, rate_limit
from .config import settings
from .connectors import valid_token
from .planning import workboard, schedule_tasks, template_tasks, local_today
from .workflow_ai import structured, ProposedSchedule, ProposedRFI, research_inspection
from .parsing import parse_document

router = APIRouter(prefix='/api/projects/{project_id}/ops')
Db, Auth = Depends(get_db), Depends(current_user)


def access(db, user, project_id, write=False):
    p = project_access(db, user, project_id)
    if write:
        require_write(user)
    return p


def get_row(db, model, project_id, row_id):
    r = db.get(model, row_id)
    if not r or r.project_id != project_id:
        raise HTTPException(404, 'Record not found in this project.')
    return r


def workflow(db, project_id, kind, data, status='draft', key=None):
    row = Workflow(project_id=project_id, kind=kind, key=key or uid(), data=data, status=status)
    db.add(row)
    db.flush()
    return row


def record_audit(db, user, action, project_id, record_id=None):
    db.add(Audit(organization_id=user.organization_id, user_id=user.id, action=action, detail={'project_id':project_id, 'record_id':record_id}))


def entries(db, project_id, kind):
    return list(db.scalars(select(Workflow).where(Workflow.project_id == project_id, Workflow.kind == kind).order_by(Workflow.created_at.desc())))


def contacts(db, project_id, trade='General'):
    people = entries(db, project_id, 'contact')
    to = [p.data['email'] for p in people if p.data.get('role') == 'architect' or (p.data.get('role') == 'engineer' and trade.lower() in [t.lower() for t in p.data.get('trades', [])])]
    cc = [p.data['email'] for p in people if p.data.get('role') == 'project manager']
    return {'to':list(dict.fromkeys(to)), 'cc':list(dict.fromkeys(cc)), 'basis':'Project directory: architect, matching trade engineer, and project manager. Review distribution before sending.'}


class Profile(BaseModel):
    city: str = Field(min_length=2, max_length=120)
    job_type: str = Field(min_length=2, max_length=120)
    start_date: date
    turnover_date: date
    workdays: list[int] = Field(default=[0,1,2,3,4], min_length=1, max_length=7)
    @field_validator('workdays')
    @classmethod
    def days(cls, v):
        if any(x < 0 or x > 6 for x in v):
            raise ValueError('Working days must be 0 (Monday) through 6 (Sunday).')
        return sorted(set(v))


@router.patch('/profile')
def profile(project_id: str, body: Profile, db: Session=Db, user=Auth):
    p = access(db,user,project_id,True)
    if body.turnover_date < body.start_date:
        raise HTTPException(422,'Turnover must be on or after the start date.')
    p.start_date, p.finish_date = str(body.start_date), str(body.turnover_date)
    p.settings = {**p.settings, 'city':body.city, 'job_type':body.job_type, 'workdays':body.workdays, 'dates_are_demo':False}
    record_audit(db,user,'operations.profile',project_id)
    db.commit()
    return public(p)


class Contact(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    email: str = Field(max_length=254)
    role: Literal['architect','engineer','project manager','vendor','contractor']
    trades: list[str] = Field(default_factory=list,max_length=20)
    @field_validator('email')
    @classmethod
    def valid_email(cls,v):
        if not re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+',v):
            raise ValueError('Enter a valid email address.')
        return v.lower()


@router.post('/contacts')
def add_contact(project_id: str, body: Contact, db: Session=Db,user=Auth):
    access(db,user,project_id,True)
    require_admin(user)
    row = workflow(db,project_id,'contact',body.model_dump(),status='active')
    db.commit()
    return public(row)


@router.delete('/contacts/{contact_id}')
def delete_contact(project_id: str, contact_id: str, db: Session=Db,user=Auth):
    access(db,user,project_id,True)
    require_admin(user)
    row = get_row(db,Workflow,project_id,contact_id)
    if row.kind != 'contact':
        raise HTTPException(404,'Contact not found.')
    db.delete(row)
    db.commit()
    return {'message':'Contact removed.'}


@router.get('/board')
def board(project_id: str, db: Session=Db,user=Auth):
    p = access(db,user,project_id)
    return {**workboard(db,p), 'project':public(p), 'contacts':[public(c) for c in entries(db,project_id,'contact')], 'demo_mode':settings.demo_mode}


class PlanRequest(BaseModel):
    description: str = Field(min_length=10,max_length=6000)
    start_date: date
    turnover_date: date


@router.post('/schedule/propose')
def propose(project_id: str, body: PlanRequest, db: Session=Db,user=Auth):
    p = access(db,user,project_id,True)
    rate_limit('plan:'+user.id,10)
    if body.turnover_date < body.start_date:
        raise HTTPException(422,'Turnover must follow the start date.')
    proposal = structured('Create a construction working-day schedule with dependencies. Durations are planning allowances, never guaranteed. Include inspection hold points; identify missing scope, crew capacity and municipal availability. Avoid artificial compression to meet turnover.', {**body.model_dump(mode='json'),'project':p.name,'job_type':p.settings.get('job_type'),'city':p.settings.get('city')},ProposedSchedule)
    proposal = proposal or {'tasks':template_tasks(p.settings.get('job_type',''),body.description), 'assumptions':['Demo template: durations require superintendent review.','Monday–Friday unless the project calendar is changed.','Crew capacity, holidays, permit readiness and inspection availability must be verified.']}
    try:
        tasks = schedule_tasks(proposal['tasks'],body.start_date,p.settings.get('workdays',[0,1,2,3,4]),p.settings.get('holidays',[]))
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    row = workflow(db,project_id,'schedule_plan',{**proposal,**body.model_dump(mode='json'),'tasks':tasks,'mode':'demo template' if settings.demo_mode else 'AI draft'})
    db.commit()
    return public(row)


class ApplyPlan(ProposedSchedule):
    start_date: date
    turnover_date: date
    replace_existing: bool = False


@router.post('/schedule/{plan_id}/apply')
def apply_plan(project_id: str, plan_id: str, body: ApplyPlan, db: Session=Db,user=Auth):
    p = access(db,user,project_id,True)
    row = get_row(db,Workflow,project_id,plan_id)
    if row.kind != 'schedule_plan' or row.status != 'draft':
        raise HTTPException(409,'This schedule is not an unapplied draft.')
    if body.turnover_date < body.start_date:
        raise HTTPException(422,'Turnover must follow the start date.')
    active = [a for a in db.scalars(select(Activity).where(Activity.project_id==project_id)) if not (a.raw_json or {}).get('superseded')]
    if active and not body.replace_existing:
        raise HTTPException(409,'Review and confirm replacement of the current baseline. Previous activities are retained in history.')
    # A new baseline invalidates old activity links: explicitly block rather than silently ignore them.
    try:
        tasks=schedule_tasks([t.model_dump() for t in body.tasks],body.start_date,p.settings.get('workdays',[0,1,2,3,4]),p.settings.get('holidays',[]))
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    claim=db.execute(update(Workflow).where(Workflow.id==row.id,Workflow.status=='draft').values(status='applying'))
    if claim.rowcount!=1:
        db.rollback()
        raise HTTPException(409,'This schedule has already been applied.')
    for a in active:
        a.raw_json={**(a.raw_json or {}),'superseded':True}
    mapping={}
    for t in tasks:
        a=Activity(project_id=project_id,activity_id=t['task_id'],name=t['name'],trade=t['trade'],start_date=t['start_date'],finish_date=t['finish_date'],predecessor_ids=t['predecessors'],raw_json={'duration_days':t['duration_days'],'plan_id':row.id})
        db.add(a)
        db.flush()
        mapping[t['task_id']]=a.id
    for t in tasks:
        if t['trade'].lower()=='inspection':
            dependent=[mapping[x['task_id']] for x in tasks if t['task_id'] in x['predecessors']]
            workflow(db,project_id,'inspection',{'name':t['name'],'scheduled_date':None,'target_date':t['start_date'],'blocks_activity_ids':dependent,'plan_id':row.id},'planned')
    row.status='applied'
    row.data={**row.data,'tasks':tasks}
    p.start_date,p.finish_date=str(body.start_date),str(body.turnover_date)
    record_audit(db,user,'schedule.applied',project_id,row.id)
    db.commit()
    return workboard(db,p)


class Progress(BaseModel):
    percent_complete: float = Field(ge=0,le=100)


@router.patch('/activities/{activity_id}')
def progress(project_id: str,activity_id: str,body: Progress,db: Session=Db,user=Auth):
    p=access(db,user,project_id,True)
    a=get_row(db,Activity,project_id,activity_id)
    if (a.raw_json or {}).get('progress_source',{}).get('kind') in ('inspection','delivery'):
        raise HTTPException(409,'This milestone updates from its linked evidence. Choose field progress to enter a manual value.')
    a.percent_complete=body.percent_complete
    a.raw_json={**(a.raw_json or {}),'actual_finish':local_today(p).isoformat() if body.percent_complete==100 else None}
    record_audit(db,user,'activity.progress',project_id,a.id)
    db.commit()
    return public(a)


class ActivityPlan(BaseModel):
    start_date: date
    finish_date: date
    progress_kind: Literal['field','inspection','delivery'] = 'field'
    progress_id: str | None = None

    @model_validator(mode='after')
    def dates_in_order(self):
        if self.finish_date < self.start_date:
            raise ValueError('Finish must be on or after start.')
        if self.progress_kind != 'field' and not self.progress_id:
            raise ValueError('Choose the evidence that completes this milestone.')
        return self


@router.patch('/activities/{activity_id}/plan')
def edit_activity_plan(project_id: str,activity_id: str,body: ActivityPlan,db: Session=Db,user=Auth):
    p=access(db,user,project_id,True)
    a=get_row(db,Activity,project_id,activity_id)
    if body.progress_kind=='inspection':
        source=get_row(db,Workflow,project_id,body.progress_id)
        if source.kind!='inspection':
            raise HTTPException(422,'Choose an inspection.')
        if a.id in source.data.get('blocks_activity_ids',[]):
            raise HTTPException(422,'This inspection blocks the activity. Only use automatic completion for the inspection milestone itself, not installation work.')
    elif body.progress_kind=='delivery':
        source=get_row(db,Procurement,project_id,body.progress_id)
        if a.id in (source.raw_json or {}).get('activity_ids',[]):
            raise HTTPException(422,'This material is a prerequisite for the activity. Only use automatic completion for a delivery milestone, not installation work.')
    from .progress import activity_progress
    old_progress=activity_progress(db,a)[0]
    data={**(a.raw_json or {})}
    data.pop('duration_days',None)
    data['progress_source']={'kind':body.progress_kind,'id':body.progress_id}
    data['plan_updated_at']=now()
    if body.progress_kind=='field':
        a.percent_complete=old_progress
    else:
        data.pop('actual_finish',None)
    a.raw_json=data
    a.start_date=body.start_date.isoformat()
    a.finish_date=body.finish_date.isoformat()
    record_audit(db,user,'activity.plan',project_id,a.id)
    db.commit()
    return public(a)


class Inspection(BaseModel):
    name: str = Field(min_length=3,max_length=160)
    scheduled_date: date | None = None
    status: Literal['planned','requested','confirmed','passed','failed'] = 'planned'
    blocks_activity_ids: list[str] = Field(default_factory=list,max_length=150)
    notes: str = Field(default='',max_length=2000)

    @model_validator(mode='after')
    def confirmed_date(self):
        if self.status=='confirmed' and not self.scheduled_date:
            raise ValueError('A confirmed inspection requires an appointment date.')
        return self


def validate_links(db,project_id,ids):
    for i in ids:
        a=get_row(db,Activity,project_id,i)
        if (a.raw_json or {}).get('superseded'):
            raise HTTPException(422,'Select an activity from the current schedule.')


@router.post('/inspections')
def add_inspection(project_id:str,body:Inspection,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    validate_links(db,project_id,body.blocks_activity_ids)
    row=workflow(db,project_id,'inspection',body.model_dump(mode='json'),body.status)
    db.commit()
    return public(row)


@router.patch('/inspections/{inspection_id}')
def edit_inspection(project_id:str,inspection_id:str,body:Inspection,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    row=get_row(db,Workflow,project_id,inspection_id)
    if row.kind!='inspection':
        raise HTTPException(404,'Inspection not found.')
    validate_links(db,project_id,body.blocks_activity_ids)
    row.data={**row.data,**body.model_dump(mode='json')}
    row.status=body.status
    row.updated_at=now()
    db.commit()
    return public(row)


class Research(BaseModel):
    inspection_type: str=Field(min_length=3,max_length=150)


@router.post('/research')
def research(project_id:str,body:Research,db:Session=Db,user=Auth):
    p=access(db,user,project_id,True)
    rate_limit('research:'+user.id,8)
    result=research_inspection(p.settings.get('city','Unspecified municipality'),body.inspection_type)
    row=workflow(db,project_id,'inspection_research',{**result,'inspection_type':body.inspection_type,'city':p.settings.get('city'),'researched_at':now()},'reference')
    db.commit()
    return public(row)


class Purchase(BaseModel):
    name: str=Field(min_length=2,max_length=160)
    vendor: str=Field(default='',max_length=160)
    vendor_email: str=Field(default='',max_length=254)
    status: Literal['not released','ordered','in transit','delivered'] = 'not released'
    expected_delivery_date: date | None=None
    required_on_site_date: date | None=None
    lead_time_days: int | None=Field(default=None,ge=0,le=3650)
    submittal_id: str | None=None
    activity_ids: list[str]=Field(default_factory=list,max_length=150)
    notes: str=Field(default='',max_length=2000)
    @field_validator('vendor_email')
    @classmethod
    def mail(cls,v):
        return Contact.valid_email(v) if v else ''


@router.get('/procurement')
def purchases(project_id:str,db:Session=Db,user=Auth):
    p=access(db,user,project_id)
    items=[]
    active={a['id']:a for a in workboard(db,p)['activities']}
    submittals={s.id:s for s in db.scalars(select(Submittal).where(Submittal.project_id==project_id))}
    for r in db.scalars(select(Procurement).where(Procurement.project_id==project_id)):
        linked=[active[i] for i in (r.raw_json or {}).get('activity_ids',[]) if i in active]
        need=min([x['start_date'] for x in linked if x['start_date']] + ([r.required_on_site_date] if r.required_on_site_date else []),default=None)
        sub=submittals.get(r.submittal_id)
        approved=bool(sub and (sub.status or '').strip().lower() in {'approved','approved as noted'})
        release_by=None
        if need and r.lead_time_days is not None:
            try:
                release_by=(date.fromisoformat(str(need)) - timedelta(days=r.lead_time_days)).isoformat()
            except ValueError:
                pass
        items.append({**public(r),'submittal':public(sub) if sub else None,'approval_pending':bool(sub and not approved),
            'suggested_release_date':release_by,'schedule_need_date':need,
            'late':bool(r.status!='delivered' and need and r.expected_delivery_date and r.expected_delivery_date>need),
            'linked_activities':[x['name'] for x in linked]})
    return {'items':items,'submittals':[public(s) for s in submittals.values()],'packages':[public(x) for x in entries(db,project_id,'package')]}


@router.post('/procurement')
def purchase(project_id:str,body:Purchase,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    validate_links(db,project_id,body.activity_ids)
    if body.submittal_id:
        get_row(db,Submittal,project_id,body.submittal_id)
    data=body.model_dump(mode='json')
    extra={k:data.pop(k) for k in ['activity_ids','vendor_email']}
    row=Procurement(project_id=project_id,raw_json=extra,**data)
    db.add(row)
    db.commit()
    return public(row)


@router.patch('/procurement/{item_id}')
def edit_purchase(project_id:str,item_id:str,body:Purchase,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    validate_links(db,project_id,body.activity_ids)
    if body.submittal_id:
        get_row(db,Submittal,project_id,body.submittal_id)
    row=get_row(db,Procurement,project_id,item_id)
    if body.status=='delivered' and any(p.data['procurement_id']==item_id and p.status!='received' for p in entries(db,project_id,'package')):
        raise HTTPException(422,'Receive all tracked packages before marking this item delivered.')
    data=body.model_dump(mode='json')
    if 'submittal_id' not in body.model_fields_set:
        data.pop('submittal_id',None)
    row.raw_json={**(row.raw_json or {}),**{k:data.pop(k) for k in ['activity_ids','vendor_email']}}
    for k,v in data.items():
        setattr(row,k,v)
    update_delivery(db,row)
    db.commit()
    return public(row)


class Package(BaseModel):
    procurement_id: str
    label: str=Field(min_length=2,max_length=160)
    carrier: Literal['UPS','FedEx','USPS','DHL','Other']='Other'
    tracking_number: str=Field(default='',max_length=100,pattern=r'^[A-Za-z0-9 -]*$')
    eta: date | None=None
    status: Literal['ordered','in transit','delayed','received']='ordered'


def update_delivery(db,item):
    packages=[r for r in entries(db,item.project_id,'package') if r.data['procurement_id']==item.id]
    if packages and all(r.status=='received' for r in packages):
        item.status='delivered'
    elif packages:
        item.status='ordered' if all(r.status=='ordered' for r in packages) else 'in transit'
        remaining=[r.data.get('eta') for r in packages if r.status!='received']
        item.expected_delivery_date=max(remaining) if remaining and all(remaining) else None


@router.post('/packages')
def add_package(project_id:str,body:Package,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    item=get_row(db,Procurement,project_id,body.procurement_id)
    row=workflow(db,project_id,'package',body.model_dump(mode='json'),body.status)
    update_delivery(db,item)
    db.commit()
    return public(row)


@router.patch('/packages/{package_id}')
def edit_package(project_id:str,package_id:str,body:Package,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    row=get_row(db,Workflow,project_id,package_id)
    if row.kind!='package' or row.data['procurement_id']!=body.procurement_id:
        raise HTTPException(422,'Package must remain linked to its original procurement item.')
    item=get_row(db,Procurement,project_id,body.procurement_id)
    row.data={**body.model_dump(mode='json'),'received_at':now() if body.status=='received' else None}
    row.status=body.status
    row.updated_at=now()
    db.flush()
    update_delivery(db,item)
    db.commit()
    return public(row)


def infer_trade(text):
    for trade,words in [('Electrical',['electrical','contactor','circuit','voltage','lighting']),('Plumbing',['plumbing','drain','water supply']),('Mechanical',['hvac','duct','ventilation']),('Architectural',['ceiling','wall','finish','door','location'])]:
        if any(w in text.lower() for w in words):
            return trade
    return 'General'


@router.get('/rfis')
def rfi_list(project_id:str,db:Session=Db,user=Auth):
    access(db,user,project_id)
    return [public(x) for x in db.scalars(select(RFI).where(RFI.project_id==project_id).order_by(RFI.created_at.desc()))]


@router.post('/rfis/generate')
async def create_rfi(project_id:str,description:str=Form(...,min_length=10,max_length=10000),files:list[UploadFile]=File(default=[]),db:Session=Db,user=Auth):
    p=access(db,user,project_id,True)
    rate_limit('rfi:'+user.id,10)
    if len(files)>5:
        raise HTTPException(422,'Upload at most five attachments.')
    attachments,images,total=[],[],0
    for f in files:
        if not f.filename:
            continue
        raw=await f.read(10_000_001)
        total+=len(raw)
        if total>10_000_000:
            raise HTTPException(413,'Combined attachments must be under 10 MB.')
        name=Path((f.filename or 'attachment').replace('\\','/')).name[:180]
        suffix=Path(name).suffix.lower()
        mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.pdf':'application/pdf','.txt':'text/plain'}.get(suffix)
        if not mime:
            raise HTTPException(422,'Use PNG, JPEG, PDF or TXT attachments.')
        text=''
        if suffix in ('.png','.jpg','.jpeg'):
            if not (raw.startswith(b'\x89PNG\r\n\x1a\n') if suffix=='.png' else raw.startswith(b'\xff\xd8\xff')):
                raise HTTPException(422,'The image does not match its file type.')
            images.append((mime,raw))
        else:
            try:
                text='\n'.join(t for _,t in parse_document(raw,name))[:30000]
            except Exception:
                raise HTTPException(422,'Attachment text could not be read. Use a text PDF or a PNG/JPEG markup.')
        attachments.append({'filename':name,'mime':mime,'text':text,'content':base64.b64encode(raw).decode()})
    generated=structured('Write a construction RFI in this style: TRADE – Specific Issue title; concise factual background; Please confirm the required condition/location; proposed solution if supplied; final direct confirmation question. Ask for missing dimensions/clearances only when relevant. Do not invent model numbers, code requirements, attachments or technical facts. Infer the trade. Mark missing information separately. Use only supplied evidence.', {'project':p.name,'job_type':p.settings.get('job_type'),'description':description,'attachments':[{'filename':a['filename'],'text':a['text']} for a in attachments]},ProposedRFI,images)
    trade=infer_trade(description)
    if not generated:
        title=re.split(r'\n|\.\s',description, maxsplit=1)[0].removeprefix('RFI Title:').strip()[:130]
        title=title if ' – ' in title or ' — ' in title else trade.upper()+' – '+title
        narrative=description.split('\n',1)[1].strip() if description.startswith('RFI Title:') and '\n' in description else description
        generated={'title':title,'trade':trade,'background':narrative,'clarification':'' if 'please confirm' in narrative.lower() else 'Please confirm the required condition described above.','proposed_solution':'','confirmation':'Please confirm whether the proposed condition is acceptable. If not, please provide the required alternative and applicable dimensions or installation requirements.','missing_information':['Demo draft uses your supplied description. Verify technical facts and complete any missing proposed solution.']+(['Images are attached for reviewer reference; image contents have not been analyzed in demo mode.'] if images else []),'attachment_observations':[]}
    elif images and settings.ai_provider!='openai':
        generated['missing_information'].append('This provider did not analyze image attachments; review the images manually.')
    distribution=contacts(db,project_id,generated['trade'])
    attachment_ids=[]
    for a in attachments:
        attachment_ids.append(workflow(db,project_id,'attachment',a,'stored').id)
    body='\n\n'.join(generated[k] for k in ['background','clarification','proposed_solution','confirmation'] if generated[k])
    row=RFI(project_id=project_id,number='DRAFT-'+uid()[:6].upper(),subject=generated['title'],question=body,status='draft',ball_in_court=', '.join(distribution['to']),raw_json={'trade':generated['trade'],'job_type':p.settings.get('job_type','Unspecified'),'distribution':distribution,'attachments':[{'id':i,'filename':a['filename']} for i,a in zip(attachment_ids,attachments)],'missing_information':generated['missing_information'],'attachment_observations':generated['attachment_observations'],'mode':'demo template' if settings.demo_mode else 'AI draft'})
    db.add(row)
    db.flush()
    record_audit(db,user,'rfi.drafted',project_id,row.id)
    db.commit()
    return public(row)


class RFIEdits(BaseModel):
    subject:str=Field(min_length=3,max_length=200)
    question:str=Field(min_length=10,max_length=20000)
    to:list[str]=Field(default_factory=list,max_length=30)
    cc:list[str]=Field(default_factory=list,max_length=30)
    @field_validator('to','cc')
    @classmethod
    def mails(cls,v):
        return [Contact.valid_email(x) for x in v]


@router.patch('/rfis/{rfi_id}')
def rfi_edit(project_id:str,rfi_id:str,body:RFIEdits,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    row=get_row(db,RFI,project_id,rfi_id)
    row.subject,row.question=body.subject,body.question
    row.raw_json={**(row.raw_json or {}),'distribution':{'to':body.to,'cc':body.cc}}
    db.commit()
    return public(row)


@router.get('/attachments/{attachment_id}')
def download(project_id:str,attachment_id:str,db:Session=Db,user=Auth):
    access(db,user,project_id)
    row=get_row(db,Workflow,project_id,attachment_id)
    if row.kind!='attachment':
        raise HTTPException(404,'Attachment not found.')
    from urllib.parse import quote
    return Response(base64.b64decode(row.data['content']),media_type=row.data['mime'],headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.data['filename'])})


class MailRequest(BaseModel):
    risk_id:str | None=None
    rfi_id:str | None=None


@router.post('/mail/prepare')
def prepare_mail(project_id:str,body:MailRequest,db:Session=Db,user=Auth):
    p=access(db,user,project_id,True)
    distribution=contacts(db,project_id)
    attachments=[]
    if body.rfi_id:
        r=get_row(db,RFI,project_id,body.rfi_id)
        subject=f'{p.name} | RFI {r.number}: {r.subject}'
        content=r.question
        distribution=(r.raw_json or {}).get('distribution') or contacts(db,project_id,infer_trade(r.subject))
        attachments=(r.raw_json or {}).get('attachments',[])
    elif body.risk_id:
        r=get_row(db,Risk,project_id,body.risk_id)
        subject=f'{p.name} | Follow-up: {r.title}'
        content=f'Hello,\n\nWe are following up on {r.title.lower()}.\n\n{r.description}\n\n{r.recommended_action}\n\nPlease confirm the current status and expected completion date so we can coordinate the project schedule.\n\nThank you,\n{user.full_name}\n{p.name}'
        for s in r.source_records or []:
            if s.get('type')=='rfis':
                source_rfi=get_row(db,RFI,project_id,s['id'])
                distribution=(source_rfi.raw_json or {}).get('distribution') or contacts(db,project_id,infer_trade(source_rfi.subject+' '+(source_rfi.question or '')))
                break
            if s.get('type')=='procurement':
                item=get_row(db,Procurement,project_id,s['id'])
                if (item.raw_json or {}).get('vendor_email'):
                    distribution={**distribution,'to':[item.raw_json['vendor_email']],'basis':'Vendor email recorded on the linked procurement item.'}
                    break
            if s.get('type')=='emails':
                e=get_row(db,Email,project_id,s['id'])
                if e.sender_email:
                    distribution={**distribution,'to':[e.sender_email],'basis':'Sender of the linked project email.'}
                    break
    else:
        raise HTTPException(422,'Select a risk or RFI to draft a message.')
    row=workflow(db,project_id,'mail',{'subject':subject,'body':content,**distribution,'attachments':attachments},'draft')
    db.commit()
    return public(row)


class MailEdit(BaseModel):
    to:list[str]=Field(min_length=1,max_length=30)
    cc:list[str]=Field(default_factory=list,max_length=30)
    subject:str=Field(min_length=3,max_length=250)
    body:str=Field(min_length=5,max_length=20000)
    @field_validator('to','cc')
    @classmethod
    def mails(cls,v):
        return [Contact.valid_email(x) for x in v]


@router.post('/mail/{mail_id}/review')
def review_mail(project_id:str,mail_id:str,body:MailEdit,db:Session=Db,user=Auth):
    access(db,user,project_id,True)
    row=get_row(db,Workflow,project_id,mail_id)
    if row.kind!='mail' or row.status not in ('draft','reviewed'):
        raise HTTPException(409,'This message has already been submitted. Check its status before composing another.')
    revision=uid()
    row.data={**row.data,**body.model_dump(),'approval_token':revision,'reviewed_by':user.id}
    row.status='reviewed'
    row.updated_at=revision
    db.commit()
    return {**public(row),'send_enabled':settings.demo_mode or settings.enable_email_send,'demo_mode':settings.demo_mode}


class Approval(BaseModel):
    approval_token:str


@router.post('/mail/{mail_id}/send')
def send_mail(project_id:str,mail_id:str,body:Approval,db:Session=Db,user=Auth):
    p=access(db,user,project_id,True)
    rate_limit('send:'+user.id,5)
    row=get_row(db,Workflow,project_id,mail_id)
    if row.kind!='mail' or row.status!='reviewed' or row.data.get('approval_token')!=body.approval_token or row.data.get('reviewed_by')!=user.id:
        raise HTTPException(409,'Review this exact message before approving send. It may already have been submitted.')
    token=None
    if not settings.demo_mode:
        if not settings.enable_email_send:
            raise HTTPException(409,'Enable server email sending and reconnect Microsoft with Mail.Send permission.')
        c=db.scalar(select(Connection).where(Connection.organization_id==user.organization_id,Connection.provider=='microsoft',Connection.status=='connected'))
        if not c or 'Mail.Send' not in c.scopes:
            raise HTTPException(409,'Reconnect Microsoft with delegated Mail.Send permission.')
        if any(x.lower().endswith('@example.com') for x in row.data['to']+row.data['cc']):
            raise HTTPException(422,'Replace demo recipient addresses before sending live email.')
        token=valid_token(db,c)
    payload={'subject':row.data['subject'],'body':{'contentType':'Text','content':row.data['body']},'toRecipients':[{'emailAddress':{'address':x}} for x in row.data['to']],'ccRecipients':[{'emailAddress':{'address':x}} for x in row.data['cc']]}
    attachments=[]
    for a in row.data.get('attachments',[]):
        stored=get_row(db,Workflow,project_id,a['id'])
        if stored.kind!='attachment':
            raise HTTPException(422,'Invalid attachment.')
        attachments.append({'@odata.type':'#microsoft.graph.fileAttachment','name':stored.data['filename'],'contentType':stored.data['mime'],'contentBytes':stored.data['content']})
    if sum(len(a['contentBytes']) for a in attachments)>3_000_000:
        raise HTTPException(422,'Attachments exceed the direct-send limit. Download and attach them in Outlook instead.')
    if attachments:
        payload['attachments']=attachments
    claimed=db.execute(update(Workflow).where(Workflow.id==row.id,Workflow.status=='reviewed',Workflow.updated_at==body.approval_token).values(status='sending'))
    if claimed.rowcount!=1:
        db.rollback()
        raise HTTPException(409,'This message changed or was already submitted.')
    db.commit()
    db.refresh(row)
    if settings.demo_mode:
        row.status='simulated'
        message='Demo send recorded. No email was transmitted.'
    else:
        try:
            # No retry: a timeout can occur after Microsoft accepts a message.
            response=httpx.post('https://graph.microsoft.com/v1.0/me/sendMail',headers={'Authorization':'Bearer '+token},json={'message':payload,'saveToSentItems':True},timeout=30)
            row.status='accepted' if response.status_code==202 else 'failed'
            message='Microsoft accepted the email for sending; delivery is not confirmed.' if row.status=='accepted' else 'Microsoft rejected the request. Check account permissions and Sent Items before composing another message.'
        except httpx.HTTPError:
            row.status='unknown'
            message='Sending status is unknown. Check Outlook Sent Items before retrying to avoid duplicate email.'
    row.data={**row.data,'result':message,'submitted_at':now()}
    record_audit(db,user,'mail.'+row.status,project_id,row.id)
    db.commit()
    return public(row)


@router.get('/agents')
def agents(project_id:str,db:Session=Db,user=Auth):
    p=access(db,user,project_id)
    b=workboard(db,p)
    late=[x for x in db.scalars(select(Procurement).where(Procurement.project_id==project_id)) if x.status!='delivered' and x.expected_delivery_date and x.required_on_site_date and x.expected_delivery_date>x.required_on_site_date]
    stale_links=[]
    active={a['id'] for a in b['activities']}
    for x in db.scalars(select(Procurement).where(Procurement.project_id==project_id)):
        if any(i not in active for i in (x.raw_json or {}).get('activity_ids',[])):
            stale_links.append('Relink '+x.name+' to the new schedule.')
    tasks=[{'title':a['name'],'detail':'Remaining work: '+str(a['remaining_workdays'])+' working days.','link':'schedule?view=today'} for a in b['today']]
    tasks += [{'title':a['name'],'detail':'; '.join(a['blockers']),'link':'schedule?view=blocked'} for a in b['blocked']]
    tasks += [{'title':'Expedite '+x.name,'detail':f'Expected {x.expected_delivery_date}; required {x.required_on_site_date}.','link':'procurement'} for x in late]
    tasks += [{'title':'Request '+i['data']['name'],'detail':'No appointment confirmed. Check municipal availability.','link':'schedule?view=inspections'} for i in b['inspections'] if i['status']=='planned']
    tasks += [{'title':x,'detail':'The prior baseline was replaced; confirm the new installation activity.','link':'procurement'} for x in stale_links]
    tasks += [{'title':'Relink '+i['data']['name'],'detail':'The previous baseline was replaced. Select the activities held by this inspection.','link':'schedule?view=inspections'} for i in b['inspections'] if i['status']!='passed' and any(k not in active for k in i['data'].get('blocks_activity_ids',[]))]
    return {'as_of':b['as_of'],'generated_at':now(),'mode':'deterministic project coordinator','summary':f"{len(b['today'])} {'activity needs' if len(b['today'])==1 else 'activities need'} work today; {len(b['blocked'])} have blockers. Forecast turnover: {b['forecast_finish'] or 'not set'}.",'tasks':tasks,'research':[public(r) for r in entries(db,project_id,'inspection_research')[:10]],'outbox':[{'id':r.id,'status':r.status,'subject':r.data.get('subject'),'to':r.data.get('to'),'result':r.data.get('result')} for r in entries(db,project_id,'mail')[:20]],'note':'Recomputed from the current date and project records on every refresh. No external messages or appointments are sent automatically.'}
