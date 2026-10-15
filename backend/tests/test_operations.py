from datetime import date
import pytest
from sqlalchemy import select
from test_app import client
from app.database import SessionLocal
from app.models import Activity, Project, User, Workflow
from app.planning import schedule_tasks, workboard
from app.security import token_for


def new_project(c):
    p=c.post('/api/projects',json={'name':'Operations validation'}).json()
    base='/api/projects/'+p['id']+'/ops'
    assert c.patch(base+'/profile',json={'city':'Greenwich, Connecticut','job_type':'Wellness fit-out','start_date':'2026-10-01','turnover_date':'2026-12-15','workdays':[0,1,2,3,4]}).status_code==200
    return p,base


def test_calendar_dependencies_and_cycles():
    tasks=[{'task_id':'A','duration_days':2,'predecessors':[]},{'task_id':'B','duration_days':1,'predecessors':['A']}]
    result=schedule_tasks(tasks,date(2026,10,2))
    assert result[0]['finish_date']=='2026-10-05'
    assert result[1]['start_date']=='2026-10-06'
    with pytest.raises(ValueError):
        schedule_tasks([{**tasks[0],'predecessors':['B']},tasks[1]],date.today())
    with pytest.raises(ValueError):
        schedule_tasks(tasks,date.today(),[])


def test_imported_schedule_counts_only_workdays(client):
    p,b=new_project(client)
    with SessionLocal() as db:
        db.add(Activity(project_id=p['id'],activity_id='IMPORT',name='Imported work',start_date='2026-10-02',finish_date='2026-10-05',percent_complete=0))
        db.commit()
        board=workboard(db,db.get(Project,p['id']),date(2026,10,2))
        assert board['activities'][0]['remaining_workdays']==2
        assert board['activities'][0]['forecast_finish']=='2026-10-05'


def test_package_status_and_manual_delivery_cannot_bypass_receipts(client):
    p,b=new_project(client)
    item=client.post(b+'/procurement',json={'name':'Controls','status':'ordered'}).json()
    package=client.post(b+'/packages',json={'procurement_id':item['id'],'label':'Controls shipment','status':'ordered','eta':'2026-10-15'})
    assert package.status_code==200
    assert client.get(b+'/procurement').json()['items'][0]['status']=='ordered'
    edited=client.patch(b+'/procurement/'+item['id'],json={'name':'Controls','status':'delivered'})
    assert edited.status_code==422
    assert 'Receive all tracked packages' in edited.json()['detail']
    saved=client.get(b+'/procurement').json()['items'][0]
    assert saved['status']=='ordered'
    assert saved['expected_delivery_date']=='2026-10-15'


def test_confirmed_inspection_requires_appointment_date(client):
    p,b=new_project(client)
    assert client.post(b+'/inspections',json={'name':'Electrical rough-in','status':'confirmed'}).status_code==422
    assert client.post(b+'/inspections',json={'name':'Electrical rough-in','status':'confirmed','scheduled_date':'2026-10-15'}).status_code==200


def test_baseline_approval_and_daily_constraints(client):
    p,b=new_project(client)
    draft=client.post(b+'/schedule/propose',json={'description':'Build spa with electrical rough-in and inspections.','start_date':'2026-10-01','turnover_date':'2026-12-15'}).json()
    tasks=draft['data']['tasks']
    payload={'tasks':tasks,'start_date':'2026-10-01','turnover_date':'2026-12-15','replace_existing':True}
    applied=client.post(b+'/schedule/'+draft['id']+'/apply',json=payload)
    assert applied.status_code==200,applied.text
    assert len(applied.json()['activities'])==12
    assert len(applied.json()['inspections'])==2
    assert client.post(b+'/schedule/'+draft['id']+'/apply',json=payload).status_code==409
    a=applied.json()['activities'][0]
    i=client.post(b+'/inspections',json={'name':'Test hold','status':'confirmed','scheduled_date':'2026-10-20','blocks_activity_ids':[a['id']]}).json()
    board=client.get(b+'/board').json()
    task=next(x for x in board['activities'] if x['id']==a['id'])
    assert task['work_status']=='blocked'
    assert task['forecast_start']>='2026-10-21'
    assert client.patch(b+'/activities/'+a['id'],json={'percent_complete':101}).status_code==422
    assert client.patch(b+'/activities/'+a['id'],json={'percent_complete':100}).status_code==200
    with SessionLocal() as db:
        board=workboard(db,db.get(Project,p['id']),date(2026,11,1))
        assert board['as_of']=='2026-11-01'
        assert board['complete']==1


def test_packages_clear_hold_only_when_all_received(client):
    p,b=new_project(client)
    with SessionLocal() as db:
        a=Activity(project_id=p['id'],name='Install equipment',activity_id='X',start_date='2026-10-01',finish_date='2026-10-02')
        db.add(a);db.commit();aid=a.id
    item=client.post(b+'/procurement',json={'name':'Sauna controls','vendor_email':'supplier@example.com','activity_ids':[aid],'expected_delivery_date':'2026-10-14','required_on_site_date':'2026-10-01'}).json()
    one={'procurement_id':item['id'],'label':'Shipment one','carrier':'UPS','tracking_number':'DEMO123','eta':'2026-10-14','status':'in transit'}
    two={**one,'label':'Shipment two','eta':None}
    x=client.post(b+'/packages',json=one).json()
    y=client.post(b+'/packages',json=two).json()
    assert client.get(b+'/procurement').json()['items'][0]['expected_delivery_date'] is None
    assert client.patch(b+'/packages/'+x['id'],json={**one,'status':'received'}).status_code==200
    assert client.get(b+'/procurement').json()['items'][0]['status']=='in transit'
    assert client.patch(b+'/packages/'+y['id'],json={**two,'status':'received'}).status_code==200
    assert client.get(b+'/procurement').json()['items'][0]['status']=='delivered'
    assert not client.get(b+'/board').json()['activities'][0]['blockers']


def test_rfi_attachments_distribution_and_email_approval(client):
    p,b=new_project(client)
    for role,email,trades in [('architect','architect@example.com',[]),('engineer','engineer@example.com',['Electrical'])]:
        assert client.post(b+'/contacts',json={'name':role,'email':email,'role':role,'trades':trades}).status_code==200
    response=client.post(b+'/rfis/generate',data={'description':'Dry sauna electrical contactor box location: propose accessible Anteroom panel.'},files=[('files',('notes.txt',b'Field note: accessible panel in the Anteroom.','text/plain'))])
    assert response.status_code==200,response.text
    r=response.json()
    assert r['raw_json']['trade']=='Electrical'
    assert set(r['raw_json']['distribution']['to'])=={'architect@example.com','engineer@example.com'}
    assert 'not be invented' not in r['question']
    attachment=r['raw_json']['attachments'][0]
    assert client.get(b+'/attachments/'+attachment['id']).content.startswith(b'Field note')
    p2,b2=new_project(client)
    assert client.get(b2+'/attachments/'+attachment['id']).status_code==404
    mail=client.post(b+'/mail/prepare',json={'rfi_id':r['id']}).json()
    assert client.post(b+'/mail/'+mail['id']+'/send',json={'approval_token':'not-reviewed'}).status_code==409
    edit={k:mail['data'][k] for k in ['to','cc','subject','body']}
    reviewed=client.post(b+'/mail/'+mail['id']+'/review',json=edit).json()
    old=reviewed['data']['approval_token']
    edit['subject']='Revised reviewed subject'
    revised=client.post(b+'/mail/'+mail['id']+'/review',json=edit).json()
    assert client.post(b+'/mail/'+mail['id']+'/send',json={'approval_token':old}).status_code==409
    approval={'approval_token':revised['data']['approval_token']}
    sent=client.post(b+'/mail/'+mail['id']+'/send',json=approval)
    assert sent.status_code==200,sent.text
    assert sent.json()['status']=='simulated'
    assert client.post(b+'/mail/'+mail['id']+'/send',json=approval).status_code==409


def test_research_unknown_wait_and_project_access(client):
    p,b=new_project(client)
    r=client.post(b+'/research',json={'inspection_type':'Electrical rough-in'}).json()['data']
    assert r['lead_time_days'] is None
    assert r['mode']=='reference'
    assert all('greenwichct.gov' in s['url'] for s in r['sources'])
    with SessionLocal() as db:
        from app.models import Organization
        org=Organization(name='Other');db.add(org);db.flush()
        user=User(organization_id=org.id,email='ops-other@example.com',role='owner',password_hash='not-used')
        db.add(user);db.commit();token=token_for(user)
    client.cookies.set('session',token)
    assert client.get(b+'/board').status_code==404
    assert client.post(b+'/research',json={'inspection_type':'Electrical'}).status_code==404


def test_live_send_timeout_is_not_retried(client,monkeypatch):
    from app import operations
    import httpx
    from app.models import Connection
    from app.security import encrypt_token
    import time
    p,b=new_project(client)
    r=client.post(b+'/rfis/generate',data={'description':'Electrical fixture height needs design confirmation.'}).json()
    mail=client.post(b+'/mail/prepare',json={'rfi_id':r['id']}).json()
    review=client.post(b+'/mail/'+mail['id']+'/review',json={'to':['reviewer@contractor.test'],'cc':[],'subject':'Test approved draft','body':'Test message for mocked transport only.'}).json()
    with SessionLocal() as db:
        project=db.get(Project,p['id'])
        c=db.scalar(select(Connection).where(Connection.organization_id==project.organization_id,Connection.provider=='microsoft'))
        if not c:
            c=Connection(organization_id=project.organization_id,provider='microsoft');db.add(c)
        c.status='connected';c.scopes=['Mail.Send'];c.expires_at=time.time()+3600;c.access_token_encrypted=encrypt_token('mock-token')
        db.commit()
    monkeypatch.setattr(operations.settings,'demo_mode',False)
    monkeypatch.setattr(operations.settings,'enable_email_send',True)
    monkeypatch.setattr(operations,'rate_limit',lambda *args:None)
    calls=[]
    def fail(*args,**kwargs):
        calls.append(args)
        raise httpx.ReadTimeout('mock timeout')
    monkeypatch.setattr(operations.httpx,'post',fail)
    body={'approval_token':review['data']['approval_token']}
    response=client.post(b+'/mail/'+mail['id']+'/send',json=body)
    assert response.status_code==200,response.text
    assert response.json()['status']=='unknown'
    assert client.post(b+'/mail/'+mail['id']+'/send',json=body).status_code==409
    assert len(calls)==1


def test_viewer_cannot_write_operational_records(client):
    from app.models import ProjectMember
    p,b=new_project(client)
    with SessionLocal() as db:
        project=db.get(Project,p['id'])
        user=User(organization_id=project.organization_id,email='ops-viewer@example.com',role='viewer',password_hash='not-used')
        db.add(user);db.flush();db.add(ProjectMember(project_id=p['id'],user_id=user.id));db.commit();token=token_for(user)
    client.cookies.set('session',token)
    assert client.get(b+'/board').status_code==200
    assert client.post(b+'/procurement',json={'name':'Unauthorized material'}).status_code==403
    assert client.post(b+'/rfis/generate',data={'description':'Unauthorized draft from viewer.'}).status_code==403
