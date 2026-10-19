from datetime import date, timedelta
from sqlalchemy import select
from .models import *
from .security import hash_password, verify_password
from .risk_engine import run_rules
from .config import settings


def seed_project(db, organization_id, name='Alo Greenwich | Retail Fit-Out'):
    d = lambda offset: (date.today() + timedelta(days=offset)).isoformat()
    p = Project(organization_id=organization_id, name=name, external_source='demo', start_date=d(-90), finish_date=d(45), settings={'aliases': ['Alo Greenwich', 'Project 24017'], 'email_keywords': ['Greenwich'], 'sync_enabled': True, 'sync_minutes': 15})
    db.add(p)
    db.flush()
    s = Submittal(project_id=p.id, number='037', title='Lighting controls', status='under review', due_date=d(-5), ball_in_court='Northline Design', spec_section='26 09 23')
    db.add(s)
    db.flush()
    db.add_all([
        Procurement(project_id=p.id, name='Lighting controls', vendor='Lumen Supply (demo)', status='not released', lead_time_days=42, required_on_site_date=d(14), expected_delivery_date=d(35), submittal_id=s.id, notes='Awaiting approval of control package.'),
        Procurement(project_id=p.id, name='Custom millwork', vendor='Oak Studio (demo)', status='ordered', lead_time_days=28, required_on_site_date=d(18), expected_delivery_date=d(23)),
        Procurement(project_id=p.id, name='Floor tile', vendor='Stone & Co (demo)', status='delivered', lead_time_days=14, required_on_site_date=d(7), expected_delivery_date=d(-2)),
        Activity(project_id=p.id, activity_id='A-210', name='Ceiling close and lighting installation', trade='Electrical', start_date=d(5), finish_date=d(10), percent_complete=0),
        Activity(project_id=p.id, activity_id='A-240', name='Custom millwork installation', trade='Millwork', start_date=d(18), finish_date=d(22), percent_complete=0),
        Activity(project_id=p.id, activity_id='A-260', name='Floor tile installation', trade='Flooring', start_date=d(7), finish_date=d(12), percent_complete=25),
        RFI(project_id=p.id, number='042', subject='Ceiling coordination at fitting rooms', question='Please confirm ceiling height and lighting fixture coordination before close.', status='open', due_date=d(-2), ball_in_court='Northline Design'),
        RFI(project_id=p.id, number='038', subject='Storefront finish confirmation', question='Confirm finish.', response='Finish confirmed.', status='closed', due_date=d(-10)),
        Submittal(project_id=p.id, number='041', title='Custom millwork shop drawings', status='submitted', due_date=d(-3), ball_in_court='Oak Studio'),
        Email(project_id=p.id, subject='Alo Greenwich - revised ship date for millwork', sender_email='supplier@example.com', sender_name='Demo Supplier', received_at=now(), body_text='The revised ship date is five days after the planned installation. Please review options for expedited shipping.'),
        Email(project_id=p.id, subject='Alo Greenwich - weekly coordination', sender_email='pm@example.com', sender_name='Demo Project Manager', received_at=now(), body_text='Please review the lighting controls and ceiling coordination items before the next meeting.'),
    ])
    doc = Document(project_id=p.id, filename='Demo coordination notes.txt', file_type='txt', raw_text='Ceiling close requires confirmation of RFI 042. Lighting controls approval remains outstanding. These are fictional demonstration notes.')
    db.add(doc)
    db.flush()
    db.add(Chunk(project_id=p.id, document_id=doc.id, chunk_index=0, page_number=1, text=doc.raw_text))
    db.flush()
    run_rules(db, p.id)
    return p


def initialize(db):
    if db.scalar(select(User).limit(1)):
        if settings.private_demo:
            owner=db.scalar(select(User).where(User.email=='demo@example.com'))
            if owner and not verify_password(settings.private_demo_password, owner.password_hash):
                owner.password_hash=hash_password(settings.private_demo_password)
                db.commit()
        if settings.demo_mode:
            upgrade_demo(db)
        return
    if not settings.demo_mode and not (settings.bootstrap_email and settings.bootstrap_password):
        return
    org = Organization(name='Northline Construction' if settings.demo_mode else 'My organization')
    db.add(org)
    db.flush()
    password=settings.private_demo_password if settings.private_demo else ('DemoProject2026!' if settings.demo_mode else settings.bootstrap_password)
    user = User(organization_id=org.id, email='demo@example.com' if settings.demo_mode else settings.bootstrap_email.lower(), full_name='Alex Morgan' if settings.demo_mode else 'Administrator', role='owner', password_hash=hash_password(password))
    db.add(user)
    if settings.demo_mode:
        seed_project(db, org.id)
        db.add(Project(organization_id=org.id, name='Riverside Medical | Interior Renovation', external_source='manual', status='active', settings={'aliases': ['Riverside Medical'], 'sync_enabled': False}))
    db.commit()
    if settings.demo_mode:
        upgrade_demo(db)


def upgrade_demo(db):
    """One-time, non-destructive upgrade of the known fictional demo workspace."""
    user=db.scalar(select(User).where(User.email=='demo@example.com'))
    if not user:
        return
    org=db.get(Organization,user.organization_id)
    org.name='Schimenti Construction Company'
    user.full_name='Schimenti Construction Company'
    seed_workspace(db,org)


def seed_workspace(db,org):
    """Idempotently give an organization the fictional sample projects (Alo Yoga, Sage and Sound)."""
    projects=list(db.scalars(select(Project).where(Project.organization_id==org.id)))
    for old in projects:
        if old.name=='Harbor House | Procore Demo' and old.external_source=='demo' and old.procore_project_id=='demo-procore-project':
            old.status='archived'
    alo=next((p for p in projects if p.name in ('Alo Greenwich | Retail Fit-Out','Alo Yoga')),None)
    sage=next((p for p in projects if p.name in ('Riverside Medical | Interior Renovation','Sage and Sound')),None)
    if not alo:
        alo=seed_project(db,org.id,'Alo Yoga')
    if not sage:
        sage=seed_project(db,org.id,'Sage and Sound')
    for p,name,kind in [(alo,'Alo Yoga','Retail fit-out'),(sage,'Sage and Sound','Wellness / spa fit-out')]:
        p.name=name
        if p.settings.get('sitesync_demo_v1'):
            continue
        p.external_source='demo'
        today=date.today()
        p.start_date=today.isoformat()
        p.finish_date=(today+timedelta(days=70 if p==sage else 60)).isoformat()
        p.settings={**p.settings,'sitesync_demo_v1':True,'city':'Greenwich, Connecticut','job_type':kind,'timezone':'America/New_York','workdays':[0,1,2,3,4],'dates_are_demo':True}
        for role,email,trades in [('architect','architect@example.com',[]),('engineer','electrical@example.com',['Electrical']),('engineer','mep@example.com',['Plumbing','Mechanical']),('project manager','pm@example.com',[])]:
            db.add(Workflow(project_id=p.id,kind='contact',key=uid(),status='active',data={'name':role.title()+' (demo)','email':email,'role':role,'trades':trades}))
        activities=list(db.scalars(select(Activity).where(Activity.project_id==p.id)))
        if not activities:
            for code,title,trade,offset in [('S01','Sauna electrical rough-in','Electrical',0),('S02','Sauna equipment installation','Electrical',8),('S03','Wellness millwork and finishes','Millwork',12)]:
                a=Activity(project_id=p.id,activity_id=code,name=title,trade=trade,start_date=(today+timedelta(days=offset)).isoformat(),finish_date=(today+timedelta(days=offset+4)).isoformat(),raw_json={'duration_days':5})
                db.add(a)
                activities.append(a)
            db.flush()
            db.add(Procurement(project_id=p.id,name='Dry sauna heater and control box',vendor='Sauna supplier (demo)',status='ordered',lead_time_days=21,required_on_site_date=(today+timedelta(days=8)).isoformat(),expected_delivery_date=(today+timedelta(days=12)).isoformat(),raw_json={'vendor_email':'sauna-supplier@example.com','activity_ids':[activities[1].id]}))
            db.add(RFI(project_id=p.id,number='012',subject='ELECTRICAL – Dry Sauna Contactor/Control Box Location',question='Please confirm the proposed accessible Anteroom location for the dry sauna contactor/control box and provide any required mounting height, clearances and wiring-distance limitations. Demo coordination item; verify manufacturer requirements.',status='open',due_date=(today+timedelta(days=2)).isoformat(),ball_in_court='Electrical engineer (demo)',raw_json={'trade':'Electrical'}))
        db.flush()
        for item in db.scalars(select(Procurement).where(Procurement.project_id==p.id)):
            linked=[a.id for a in activities if any(w in a.name.lower() for w in item.name.lower().split() if len(w)>4)]
            item.raw_json={**(item.raw_json or {}),'vendor_email':(item.raw_json or {}).get('vendor_email','supplier@example.com'),'activity_ids':(item.raw_json or {}).get('activity_ids',linked)}
            if item.status!='delivered':
                db.add(Workflow(project_id=p.id,kind='package',key=uid(),status='ordered',data={'procurement_id':item.id,'label':item.name+' / shipment 1','carrier':'Other','tracking_number':'','eta':item.expected_delivery_date,'status':'ordered'}))
        db.add(Workflow(project_id=p.id,kind='inspection',key=uid(),status='planned',data={'name':'Electrical rough-in inspection','scheduled_date':None,'blocks_activity_ids':[activities[-1].id] if activities else [],'notes':'Demo hold point. Confirm scope and request in City Squared.'}))
        db.flush()
        run_rules(db,p.id)
    db.commit()
