from datetime import date
from test_app import client
from test_operations import new_project
from app.database import SessionLocal
from app.models import Activity, Workflow, Procurement, Project
from app.planning import workboard
from app.progress import completion_summary


def test_evidence_completion_reopens_and_refreshes_project_summary(client):
    p,b=new_project(client)
    with SessionLocal() as db:
        milestone=Activity(project_id=p['id'],name='Inspection milestone',start_date='2026-10-01',finish_date='2026-10-02',percent_complete=0)
        installation=Activity(project_id=p['id'],name='Install equipment',start_date='2026-10-03',finish_date='2026-10-05',percent_complete=0)
        inspection=Workflow(project_id=p['id'],kind='inspection',key='qa-inspection',status='planned',data={'name':'Final inspection','blocks_activity_ids':[]})
        db.add_all([milestone,installation,inspection]);db.commit();aid,iid=milestone.id,inspection.id
    response=client.patch(b+'/activities/'+aid+'/plan',json={'start_date':'2026-10-01','finish_date':'2026-10-02','progress_kind':'inspection','progress_id':iid})
    assert response.status_code==200,response.text
    assert client.patch(b+'/activities/'+aid,json={'percent_complete':100}).status_code==409
    with SessionLocal() as db:
        inspection=db.get(Workflow,iid);inspection.status='passed';db.commit()
        board=workboard(db,db.get(Project,p['id']),date(2026,10,5))
        assert next(a for a in board['activities'] if a['id']==aid)['percent_complete']==100
        assert completion_summary(db,p['id'])['completion_percent']==50
        inspection.status='failed';db.commit()
        assert completion_summary(db,p['id'])['completion_percent']==0
    assert client.patch(b+'/activities/'+aid+'/plan',json={'start_date':'2026-10-05','finish_date':'2026-10-01'}).status_code==422
    assert client.patch(b+'/activities/'+aid+'/plan',json={'start_date':'2026-10-01','finish_date':'2026-10-03'}).status_code==200


def test_evidence_must_belong_to_project_and_not_be_installation_prerequisite(client):
    p,b=new_project(client);other,_=new_project(client)
    with SessionLocal() as db:
        activity=Activity(project_id=p['id'],name='Install material',percent_complete=0)
        db.add(activity);db.flush()
        item=Procurement(project_id=p['id'],name='Equipment',status='delivered',raw_json={'activity_ids':[activity.id]})
        foreign=Workflow(project_id=other['id'],kind='inspection',key='qa-inspection',status='passed',data={'name':'Other project'})
        db.add_all([item,foreign]);db.commit();aid,pid,iid=activity.id,item.id,foreign.id
    payload={'start_date':'2026-10-01','finish_date':'2026-10-03','progress_kind':'delivery','progress_id':pid}
    assert client.patch(b+'/activities/'+aid+'/plan',json=payload).status_code==422
    payload.update(progress_kind='inspection',progress_id=iid)
    assert client.patch(b+'/activities/'+aid+'/plan',json=payload).status_code==404
