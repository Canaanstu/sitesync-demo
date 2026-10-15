from test_app import client
from test_operations import new_project
from app.database import SessionLocal
from app.models import Submittal


def test_procurement_submittal_scope_and_unknown_lead(client):
    project,base=new_project(client)
    other,other_base=new_project(client)
    with SessionLocal() as db:
        linked=Submittal(project_id=project['id'],number='26-01',title='Controls',status='pending',lead_time_days=21,ball_in_court='Engineer')
        foreign=Submittal(project_id=other['id'],title='Other project')
        db.add_all([linked,foreign]);db.commit()
        linked_id,foreign_id=linked.id,foreign.id
    assert client.post(base+'/procurement',json={'name':'Controls','submittal_id':foreign_id}).status_code==404
    response=client.post(base+'/procurement',json={'name':'Controls','submittal_id':linked_id,'required_on_site_date':'2026-12-01'})
    assert response.status_code==200
    item=response.json()
    assert item['lead_time_days'] is None
    assert item['status']=='not released'
    board=client.get(base+'/procurement').json()
    saved=next(i for i in board['items'] if i['id']==item['id'])
    assert saved['submittal']['ball_in_court']=='Engineer'
    assert saved['approval_pending'] is True
    assert saved['suggested_release_date'] is None
    assert foreign_id not in [s['id'] for s in board['submittals']]
    assert client.patch(base+'/procurement/'+item['id'],json={'name':'Controls','submittal_id':foreign_id}).status_code==404
    # Older clients that omit the relationship must not erase it.
    response=client.patch(base+'/procurement/'+item['id'],json={'name':'Controls','lead_time_days':21,'required_on_site_date':'2026-12-01'})
    assert response.status_code==200
    assert response.json()['submittal_id']==linked_id
    saved=next(i for i in client.get(base+'/procurement').json()['items'] if i['id']==item['id'])
    assert saved['suggested_release_date']=='2026-11-10'
    assert client.patch(base+'/procurement/'+item['id'],json={'name':'Controls','submittal_id':None}).json()['submittal_id'] is None
