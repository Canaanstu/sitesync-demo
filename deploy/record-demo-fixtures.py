"""Record the fictional demo data into frontend/lib/demo-data.json for the static GitHub Pages build.

Run against a freshly seeded local backend (DEMO_MODE=true, empty database):
    python deploy/record-demo-fixtures.py http://127.0.0.1:8000 demo@example.com 'DemoProject2026!'
The static site only ever contains this fictional seed data.
"""
import json,sys,urllib.request,http.cookiejar
base,email,password=(sys.argv+[None]*4)[1:4]
base=base or 'http://127.0.0.1:8000'
jar=http.cookiejar.CookieJar()
op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def call(path,body=None,method=None):
    req=urllib.request.Request(base+'/api'+path,data=json.dumps(body).encode() if body is not None else None,method=method or ('POST' if body is not None else 'GET'),headers={'Content-Type':'application/json'})
    with op.open(req) as r:
        raw=r.read();return json.loads(raw) if raw else {}
call('/auth/login',{'email':email,'password':password})
out={}
def get(path):
    try:out['GET '+path]=call(path)
    except Exception as e:print('skip',path,e);return None
    return out['GET '+path]
for p in ['/health','/me','/organizations/current','/organizations/members','/organizations/usage','/projects','/integrations']:get(p)
for pr in out['GET /projects']:
    P='/projects/'+pr['id']
    for s in ['','/risks','/members','/sync-status','/ai/history','/ops/board','/ops/procurement','/ops/rfis','/ops/agents']:get(P+s)
    for kind in ['documents','rfis','submittals','procurement','schedule','emails']:
        for row in get(P+'/'+kind) or []:
            get(f"{P}/sources/{kind}/{row['id']}")
    for risk in out['GET '+P+'/risks']:
        for s in risk.get('source_records') or []:get(f"{P}/sources/{s['type']}/{s['id']}")
        for key,path,body in [('mail',P+'/ops/mail/prepare',{'risk_id':risk['id']}),('rfi',P+'/ai/draft-rfi',{'risk_id':risk['id']}),('email',P+'/ai/draft-email',{'risk_id':risk['id']})]:
            try:out[f"POST {path}#{risk['id']}"]=call(path,body)
            except Exception as e:print('skip',path,e)
json.dump(out,open('frontend/lib/demo-data.json','w'),separators=(',',':'),sort_keys=True)
print(len(out),'responses')
