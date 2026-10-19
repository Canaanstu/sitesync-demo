// In-browser stand-in for the SiteSync API, used only by the static GitHub Pages build
// (NEXT_PUBLIC_STATIC_DEMO=true). Reads come from recorded fictional demo data; a few actions
// (tasks, schedule progress, receiving deliveries) change in-memory state that resets on reload.
import raw from './demo-data.json';
type Row=Record<string,any>;
const data:Record<string,any>=JSON.parse(JSON.stringify(raw));
const AUTH='sitesync:static-demo-auth';
const unsupported='This action needs the live backend. The static preview supports tasks, schedule progress and deliveries.';
const wait=()=>new Promise(r=>setTimeout(r,60));
const authed=()=>{try{return localStorage.getItem(AUTH)==='1'}catch{return true}};

function recount(projectId:string){
 const risks:Row[]=data[`GET /projects/${projectId}/risks`]||[],open=risks.filter(r=>r.status==='open');
 const p=(data['GET /projects'] as Row[]).find(x=>x.id===projectId);
 if(p){p.risk_count=open.length;p.high_risks=open.filter(r=>['high','critical'].includes(r.severity)).length}
}
function board(projectId:string):Row{return data[`GET /projects/${projectId}/ops/board`]}

export async function mockApi(path:string,body?:unknown,method?:string):Promise<any>{
 await wait();
 const m=(method||(body?'POST':'GET')).toUpperCase(),clean=path.split('?')[0],b=(body&&!(body instanceof FormData)?body:{}) as Row;
 if(clean==='/health')return {...data['GET /health'],signup_open:true,email_enabled:false};
 if(clean==='/auth/login'||clean==='/auth/signup'){try{localStorage.setItem(AUTH,'1')}catch{}return {ok:true}}
 if(clean==='/auth/logout'){try{localStorage.removeItem(AUTH)}catch{}return {ok:true}}
 if(/^\/auth\/(forgot|reset|verify|resend-verification)$/.test(clean)||(clean==='/me'&&m==='DELETE'))throw new Error('Accounts and email are not available in the static preview.');
 if(clean==='/launch/requests')throw new Error('The request form is turned off on this static preview.');
 if(clean==='/me'&&!authed()){const e=new Error('Sign in to continue.');(e as any).status=401;if(typeof window!=='undefined')window.location.href=(process.env.NEXT_PUBLIC_BASE_PATH||'')+'/login/';throw e}

 const risk=clean.match(/^\/projects\/([^/]+)\/risks\/([^/]+)\/(resolve|dismiss|reopen)$/);
 if(m==='POST'&&risk){
  const [,pid,rid,action]=risk,r=(data[`GET /projects/${pid}/risks`] as Row[]).find(x=>x.id===rid);
  if(r)r.status=action==='resolve'?'resolved':action==='dismiss'?'dismissed':'open';
  recount(pid);return r||{}
 }
 if(m==='POST'&&/\/risks\/run$/.test(clean))return {ok:true};
 if(m==='POST'&&/\/sync$/.test(clean))return {status:'complete'};

 const activity=clean.match(/^\/projects\/([^/]+)\/ops\/activities\/([^/]+)$/);
 if(m==='PATCH'&&activity){
  const a=(board(activity[1]).activities as Row[]).find(x=>x.id===activity[2]);
  if(a){if(b.percent_complete!=null){a.percent_complete=b.percent_complete;a.work_status=b.percent_complete>=100?'complete':a.work_status==='complete'?'upcoming':a.work_status}}
  return a||{}
 }
 const pkg=clean.match(/^\/projects\/([^/]+)\/ops\/packages\/([^/]+)$/);
 if(m==='PATCH'&&pkg){
  const list=data[`GET /projects/${pkg[1]}/ops/procurement`].packages as Row[],x=list.find(p=>p.id===pkg[2]);
  if(x){x.data={...x.data,...b};x.status=b.status||x.status;if(x.status==='received')x.data.received_at=new Date().toISOString().slice(0,10)}
  return x||{}
 }
 const chat=clean.match(/^\/projects\/([^/]+)\/chat(?:\/(members|unread|read))?$/);
 if(chat){
  const key=`GET /projects/${chat[1]}/chat`,me=data['GET /me'];
  if(chat[2]==='members')return [{id:me.id,name:me.full_name||'You'}];
  if(chat[2]==='unread')return {unread:0,mentions:0};
  if(chat[2]==='read')return {ok:true};
  if(m==='POST'){const f=body instanceof FormData?body:null,msg={id:'c'+Date.now(),user_id:me.id,author:'You',body:String(f?.get('body')??b.body??'').trim(),mentions:[],files:[],created_at:new Date().toISOString()};data[key]=[...(data[key]||[]),msg];return msg}
  return data[key]||[]
 }
 if(m==='POST'&&/\/ai\/chat$/.test(clean)){
  const pid=clean.split('/')[2],key=`GET /projects/${pid}/ai/history`,now=new Date().toISOString();
  data[key]=[...(data[key]||[]),{id:'u'+Date.now(),role:'user',content:b.question,sources:[],created_at:now},{id:'a'+Date.now(),role:'assistant',content:'Project AI answers are turned off in this static preview. In the live app, answers cite the schedule, RFIs, submittals and deliveries behind them.',sources:[],created_at:now}];
  return {ok:true}
 }
 if(m==='POST'){
  const recorded=data[`POST ${clean}#${b.risk_id}`];
  if(recorded)return recorded;
  throw new Error(unsupported)
 }
 if(m!=='GET')throw new Error(unsupported);

 if(clean in data||('GET '+clean) in data){return data['GET '+clean]}
 throw new Error('Not available in the static preview.');
}
