'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {Mic,Square,NotebookPen,BellRing,X,Lightbulb} from 'lucide-react';
import {api,Row} from '../lib/api';
import {whenText} from './notifications';

const ROLE_LABEL:Record<string,string>={super:'Superintendent',pm:'Project manager',member:'Team member'};
export const roleLabel=(r?:string)=>ROLE_LABEL[r||'member']||'Team member';
const ago=(iso:string)=>{
 const s=Math.max(0,(Date.now()-new Date(iso).getTime())/1000);
 if(s<90)return 'just now';
 if(s<3600)return Math.round(s/60)+' min ago';
 if(s<86400)return Math.round(s/3600)+' h ago';
 return new Date(iso).toLocaleDateString('en-US',{month:'short',day:'numeric'});
};

// Short, plain-language setup help for each part of the app. Dismissed cards stay dismissed on this device.
const GUIDES:Record<string,{title:string,steps:string[]}>={
 schedule:{title:'How the schedule works',steps:['Start with “Next 7 days”: everything due this week is listed there first.','Jot a note the moment something happens. It is stamped with the date and time, and you can tie it to an activity.','Change an activity’s dates or percent complete and the whole team sees it under “What changed”.']},
 materials:{title:'How materials work',steps:['Add each purchase package with its expected delivery date.','Link the package to the activities that need it. Late deliveries then show up as schedule risk.','Mark a package received when it arrives; the schedule refreshes by itself.']},
 rfi:{title:'How RFIs work',steps:['Describe what you see in the field and attach a photo or markup.','SiteSync drafts the RFI. You review the trade, recipients and wording.','Nothing is sent or published until you approve it.']},
 crew:{title:'How the crew view works',steps:['Chat is shared with everyone on this project.','Your project role (superintendent, project manager or team member) decides what your daily summary leads with.','Ask an administrator to set roles in Project settings → Access.']},
 projects:{title:'Get your projects in',steps:['Connect Procore under Tools, then press Import to bring projects across. You can import one, a few, or all of them in one go.','No Procore? Press New to start a project and add its schedule.','Invite teammates from Settings so your whole crew shares the same projects.']},
 import:{title:'Importing many projects',steps:['Tick the projects you want, or press “Import all”.','Projects already in SiteSync are skipped, so it is safe to run again.','Each project keeps syncing RFIs and submittals from Procore after it is imported.']},
};
export function HowTo({id}:{id:keyof typeof GUIDES|string}){
 const key='sitesync:howto:'+id,[hidden,setHidden]=useState(true),g=GUIDES[id];
 useEffect(()=>{try{setHidden(localStorage.getItem(key)==='1')}catch{setHidden(false)}},[key]);
 if(!g||hidden)return null;
 return <aside className="howto" aria-label={g.title}><Lightbulb size={20} aria-hidden="true"/><div><b>{g.title}</b><ol>{g.steps.map((s,i)=><li key={i}>{s}</li>)}</ol><small><Link href="/tutorial">Full tutorial</Link></small></div><button className="icon" aria-label={`Hide “${g.title}”`} onClick={()=>{setHidden(true);try{localStorage.setItem(key,'1')}catch{}}}><X size={16}/></button></aside>;
}

function Dictation({onText}:{onText:(t:string)=>void}){
 const [on,setOn]=useState(false),rec=useRef<any>(null);
 const Ctor=typeof window!=='undefined'?(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition:null;
 useEffect(()=>()=>rec.current?.stop?.(),[]);
 if(!Ctor)return null;
 function toggle(){
  if(on){rec.current?.stop();return}
  const r=new Ctor();r.lang='en-US';r.interimResults=false;r.continuous=false;
  r.onresult=(e:any)=>onText(Array.from(e.results).map((x:any)=>x[0].transcript).join(' '));
  r.onend=()=>setOn(false);r.onerror=()=>setOn(false);
  rec.current=r;setOn(true);r.start();
 }
 return <button type="button" className="icon" aria-pressed={on} aria-label={on?'Stop dictating':'Dictate a note'} title={on?'Stop':'Speak your note'} onClick={toggle}>{on?<Square size={16}/>:<Mic size={18}/>}</button>;
}

// A one-line note box for the field: write or speak it, and it is saved with the time and (optionally) an activity.
export function QuickNote({projectId,activities,canEdit}:{projectId:string,activities:Row[],canEdit:boolean}){
 const cache=useQueryClient(),[text,setText]=useState(''),[activity,setActivity]=useState(''),[busy,setBusy]=useState(false),[msg,setMsg]=useState('');
 async function save(e:React.FormEvent){
  e.preventDefault();if(!text.trim())return;
  setBusy(true);setMsg('');
  try{await api(`/projects/${projectId}/notes`,{text:text.trim(),activity_id:activity||null});setText('');setActivity('');setMsg('Saved with the time.');await cache.invalidateQueries({queryKey:['changes',projectId]})}
  catch(err){setMsg((err as Error).message)}finally{setBusy(false)}
 }
 return <form className="quick-note" onSubmit={save} aria-label="Quick note">
  <label className="sr-only" htmlFor="qn-text">Note</label>
  <input id="qn-text" value={text} maxLength={600} disabled={!canEdit||busy} onChange={e=>setText(e.target.value)} placeholder="Note it now: “Inspector coming Thursday 8am”"/>
  <Dictation onText={t=>setText(v=>(v?v+' ':'')+t)}/>
  <label className="sr-only" htmlFor="qn-activity">Related activity</label>
  <select id="qn-activity" value={activity} disabled={!canEdit||busy} onChange={e=>setActivity(e.target.value)}><option value="">No activity</option>{activities.filter(a=>!a.raw_json?.superseded).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
  <button className="primary" disabled={!canEdit||busy||!text.trim()}><NotebookPen size={16}/>Note this</button>
  {msg&&<small role="status">{msg}</small>}
 </form>;
}

function Feed({projectId}:{projectId:string}){
 const cache=useQueryClient(),[open,setOpen]=useState(false);
 const feed=useQuery({queryKey:['changes',projectId],queryFn:()=>api(`/projects/${projectId}/changes?limit=30`),refetchInterval:60000,retry:false});
 const events:Row[]=feed.data?.events||[],fresh:number=feed.data?.new||0;
 async function toggle(){
  const next=!open;setOpen(next);
  if(next&&fresh>0){try{await api(`/projects/${projectId}/changes/read`,{});await cache.setQueryData(['changes',projectId],(o:Row|undefined)=>o?{...o,new:0}:o)}catch{}}
 }
 if(feed.isError)return null;
 return <section className="feed">
  <button className="feed-toggle" aria-expanded={open} onClick={toggle}><BellRing size={16} aria-hidden="true"/>What changed{fresh>0&&<i aria-label={`${fresh} new`}>{fresh}</i>}<small>{events.length?`Latest ${ago(events[0].created_at)}`:'Nothing yet'}</small></button>
  {open&&<ul className="feed-list">{events.map(e=><li key={e.id} className={e.new?'new':''}><span className="feed-kind">{e.kind==='note'?'Note':e.kind==='schedule'?'Schedule':e.kind==='sync'?'Procore':e.kind==='import'?'Import':'Team'}</span><span>{e.kind==='note'&&e.activity&&<b>{e.activity}: </b>}{e.summary}<small>{e.author} · {ago(e.created_at)}</small></span></li>)}{!events.length&&<li className="muted">Changes to the schedule and field notes appear here for the whole team.</li>}</ul>}
 </section>;
}

// Top of the Schedule tab: what is due, a one-tap note box, and what the team changed.
export function ScheduleTop({projectId,activities,warnings,canEdit}:{projectId:string,activities:Row[],warnings:Row[],canEdit:boolean}){
 const feed=useQuery({queryKey:['changes',projectId],queryFn:()=>api(`/projects/${projectId}/changes?limit=30`),refetchInterval:60000,retry:false});
 const week=warnings.slice(0,6);
 return <div className="sched-top">
  <HowTo id="schedule"/>
  <section className="next7" aria-label="Next 7 days"><div className="next7-head"><h3>Next 7 days</h3>{feed.data?.role&&feed.data.role!=='member'&&<span className="role-pill">{roleLabel(feed.data.role)}</span>}</div>
   {week.length?<ul>{week.map(w=><li key={w.key} className={w.overdue?'late':''}><b>{w.title}</b><small>{whenText(w)}</small></li>)}</ul>:<p className="muted">Nothing due in the next 7 days.</p>}
   {warnings.length>week.length&&<small className="muted">+ {warnings.length-week.length} more in the plan below</small>}
  </section>
  <QuickNote projectId={projectId} activities={activities} canEdit={canEdit}/>
  <Feed projectId={projectId}/>
 </div>;
}

// Project settings: who is the superintendent, who is the project manager.
export function RoleSelect({projectId,userId,name}:{projectId:string,userId:string,name:string}){
 const cache=useQueryClient(),team=useQuery({queryKey:['team',projectId],queryFn:()=>api<Row[]>(`/projects/${projectId}/team`),retry:false});
 const role=team.data?.find(t=>t.id===userId)?.role||'member';
 return <label className="role-select"><span className="sr-only">Project role for {name}</span><select value={role} onChange={async e=>{await api(`/projects/${projectId}/members/${userId}/role`,{role:e.target.value},'PUT');await cache.invalidateQueries({queryKey:['team',projectId]});await cache.invalidateQueries({queryKey:['changes',projectId]})}}>{Object.entries(ROLE_LABEL).map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>;
}

// Settings: one summary email a day, and only when something changed.
export function DigestSetting(){
 const cache=useQueryClient(),d=useQuery({queryKey:['digest'],queryFn:()=>api('/me/digest'),retry:false});
 if(d.isError||!d.data)return null;
 return <section className="panel form-panel"><h2>Daily summary</h2>
  <p className="muted">One email a day, only when something changed on your projects. It leads with what is due if you are the superintendent, and with what changed if you are the project manager. Everything is also in each project’s “What changed”.</p>
  <label className="role-select"><span className="sr-only">Daily summary email</span><select value={d.data.digest} onChange={async e=>{await api('/me/digest',{digest:e.target.value},'PUT');await cache.invalidateQueries({queryKey:['digest']})}}><option value="daily">Email me once a day</option><option value="off">No email, I will check the app</option></select></label>
  {!d.data.email_enabled&&<small className="muted">Email sending is not set up on this server yet, so nothing is sent. The preview below shows what it would say.</small>}
  <details><summary>Preview today’s summary</summary><pre className="digest-preview">{d.data.preview||'Nothing has changed since yesterday, so no email would be sent.'}</pre></details>
 </section>;
}
