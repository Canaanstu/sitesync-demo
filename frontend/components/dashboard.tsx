'use client';
import Link from 'next/link';
import {useState} from 'react';
import {useQueries,useQuery} from '@tanstack/react-query';
import {CalendarDays,ChevronLeft,ChevronRight,ChevronDown,Home,Package} from 'lucide-react';
import {api,Row} from '../lib/api';
import {DailyOverview,levelOf} from './project-hub';
import {DueOverview} from './field-views';

const iso=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const short=(name:string)=>name.split('|')[0].trim();
const day=(v?:string)=>v?new Date(v.slice(0,10)+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'}):'–';

// Left rail: every project, each expandable to its open tasks.
function ProjectList({projects}:{projects:Row[]}){
 const [open,setOpen]=useState<string|null>(null);
 return <nav className="side" aria-label="Projects"><h2>Projects</h2>
  {projects.map(p=><div className="side-project" key={p.id}>
   <button aria-expanded={open===p.id} onClick={()=>setOpen(open===p.id?null:p.id)}><ChevronDown size={16} className={open===p.id?'':'turned'}/><span>{short(p.name)}</span>{p.risk_count>0&&<i>{p.risk_count}</i>}</button>
   {open===p.id&&<SideTasks project={p}/>}
  </div>)}
  {!projects.length&&<small className="muted">No projects yet.</small>}
 </nav>;
}
function SideTasks({project}:{project:Row}){
 const risks=useQuery({queryKey:['risks',project.id],queryFn:()=>api<Row[]>(`/projects/${project.id}/risks`),refetchInterval:15000});
 const open=(risks.data||[]).filter(r=>['open','in_progress'].includes(r.status));
 return <div className="side-tasks">
  {open.map(r=><Link key={r.id} href={`/projects/${project.id}`} className={'side-task '+levelOf(r.severity)}><span>{r.title}</span>{r.status==='in_progress'&&<small className="working-tag">{r.evidence?.in_progress_by?String(r.evidence.in_progress_by).split(' ')[0]+' is on it':'In progress'}</small>}</Link>)}
  {risks.data&&!open.length&&<small className="muted">All clear.</small>}
  <div className="side-links"><Link href={`/projects/${project.id}`}>Open project</Link><Link href={`/projects/${project.id}/schedule`}>Schedule</Link><Link href={`/projects/${project.id}/procurement`}>Procurement</Link></div>
 </div>;
}

function useOps(projects:Row[]){
 const q=useQueries({queries:projects.flatMap(p=>[
  {queryKey:['ops-board',p.id],queryFn:()=>api(`/projects/${p.id}/ops/board`),refetchInterval:60000},
  {queryKey:['ops-procurement',p.id],queryFn:()=>api(`/projects/${p.id}/ops/procurement`),refetchInterval:60000}])});
 return projects.map((p,i)=>({project:p,board:q[i*2].data as Row|undefined,proc:q[i*2+1].data as Row|undefined}));
}

// One calendar for every project: work, inspections and expected deliveries.
function CompanyCalendar({ops}:{ops:ReturnType<typeof useOps>}){
 const [month,setMonth]=useState(()=>new Date());
 const first=new Date(month.getFullYear(),month.getMonth(),1),start=new Date(first);start.setDate(1-(first.getDay()+6)%7);
 const dates=Array.from({length:42},(_,i)=>new Date(start.getFullYear(),start.getMonth(),start.getDate()+i));
 const today=iso(new Date()),due=(useQuery({queryKey:['notifications'],queryFn:()=>api<Row[]>('/notifications'),refetchInterval:60000}).data||[]);
 const events=(key:string)=>ops.flatMap(({project,board,proc})=>{
  const href=`/projects/${project.id}/schedule`,pn=short(project.name),out:{id:string,label:string,sub:string,kind:string,href:string}[]=[];
  (board?.activities||[]).forEach((a:Row)=>{if(a.start_date&&a.start_date<=key&&(a.finish_date||a.start_date)>=key)out.push({id:a.id,label:a.name,sub:pn,kind:a.work_status==='complete'?'event-complete':'',href})});
  (board?.inspections||[]).forEach((i:Row)=>{if(i.data.scheduled_date===key)out.push({id:i.id,label:i.data.name,sub:pn+' · inspection',kind:'event-inspection',href})});
  (proc?.items||[]).forEach((x:Row)=>{if(x.expected_delivery_date===key&&x.status!=='delivered')out.push({id:x.id,label:x.name,sub:pn+' · delivery',kind:'event-delivery',href:`/projects/${project.id}/procurement`})});
  return out;
 });
 const asOf=iso(new Date()),rows=[{label:'Work',dates:ops.flatMap(o=>(o.board?.activities||[]).filter((a:Row)=>a.work_status!=='complete').map((a:Row)=>a.raw_json?.due_date||a.finish_date))},{label:'Inspections',dates:ops.flatMap(o=>(o.board?.inspections||[]).filter((i:Row)=>!['passed','failed'].includes(i.status)).map((i:Row)=>i.data.scheduled_date))},{label:'Deliveries',dates:ops.flatMap(o=>(o.proc?.items||[]).filter((x:Row)=>x.status!=='delivered').map((x:Row)=>x.expected_delivery_date))}];
 return <><DueOverview asOf={asOf} rows={rows}/><section className="panel calendar-panel"><div className="section-heading"><h3 aria-live="polite">{month.toLocaleDateString('en-US',{month:'long',year:'numeric'})}</h3><div className="ops-actions"><button aria-label="Previous month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}><ChevronLeft/></button><button onClick={()=>setMonth(new Date())}>Today</button><button aria-label="Next month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}><ChevronRight/></button></div></div>
  <div className="schedule-calendar-scroll"><div className="schedule-calendar" aria-label="All projects calendar">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=><b className="calendar-weekday" key={d}>{d}</b>)}
   {dates.map(d=>{const key=iso(d);return <div className={'calendar-day '+(d.getMonth()!==month.getMonth()?'outside-month ':'')+(key===today?'calendar-today':'')} key={key}><time dateTime={key}>{d.getDate()}</time>{due.filter(w=>w.due===key).length>0&&<span className="due-flag" title={due.filter(w=>w.due===key).map(w=>w.project_name+': '+w.title).join('\n')}>{due.filter(w=>w.due===key).length} due</span>}
    {events(key).map(e=><Link key={e.id+key} href={e.href} className={'calendar-event '+e.kind}>{e.label}<small>{e.sub}</small></Link>)}</div>})}
  </div></div></section></>;
}

// Every purchase and delivery across projects, late ones first. Shipments (packages) supply the tracked ETA when there is one.
const FILTERS:[string,string][]=[['all','All'],['late','Late'],['soon','Next 14 days'],['transit','In transit'],['delivered','Delivered']];
function Procurement({ops}:{ops:ReturnType<typeof useOps>}){
 const [filter,setFilter]=useState('all'),today=iso(new Date()),soon=iso(new Date(Date.now()+14*864e5));
 const all:Row[]=ops.flatMap(({project,proc})=>(proc?.items||[]).map((x:Row)=>{
  const ships=(proc?.packages||[]).filter((k:Row)=>k.data?.procurement_id===x.id&&k.status!=='received'),etas=ships.map((k:Row)=>k.data?.eta).filter(Boolean).sort();
  const delivered=x.status==='delivered',eta=etas[0]||x.expected_delivery_date;
  return {...x,pid:project.id,pname:short(project.name),delivered,late:!!x.late&&!delivered,eta,transit:!delivered&&ships.length>0,ships:ships.length};
 })).sort((a:Row,b:Row)=>Number(b.late)-Number(a.late)||Number(a.delivered)-Number(b.delivered)||String(a.eta||'9').localeCompare(String(b.eta||'9')));
 const match=(x:Row)=>filter==='all'||(filter==='late'&&x.late)||(filter==='delivered'&&x.delivered)||(filter==='transit'&&x.transit)||(filter==='soon'&&!x.delivered&&x.eta&&x.eta>=today&&x.eta<=soon);
 const count=(f:string)=>all.filter(x=>f==='all'||(f==='late'&&x.late)||(f==='delivered'&&x.delivered)||(f==='transit'&&x.transit)||(f==='soon'&&!x.delivered&&x.eta&&x.eta>=today&&x.eta<=soon)).length;
 const rows=all.filter(match);
 if(!all.length)return <div className="empty"><span className="empty-art"><Package size={30}/></span><h3>No deliveries yet</h3></div>;
 return <>
  <div className="stat-row"><div className="stat bad"><b>{count('late')}</b><span>Late</span></div><div className="stat"><b>{count('soon')}</b><span>Due in 14 days</span></div><div className="stat"><b>{count('transit')}</b><span>In transit</span></div><div className="stat ok"><b>{count('delivered')}</b><span>Delivered</span></div></div>
  <div className="filter-row" role="group" aria-label="Filter deliveries">{FILTERS.map(([k,label])=><button key={k} className={filter===k?'active':''} aria-pressed={filter===k} onClick={()=>setFilter(k)}>{label}<small>{count(k)}</small></button>)}</div>
  <div className="mat-table" role="table" aria-label="Deliveries across projects">
   <div className="mat-row mat-head" role="row"><span>Item</span><span>Project</span><span>Status</span><span>Needed</span><span>Expected</span></div>
   {rows.map(x=><Link role="row" key={x.pid+x.id} href={`/projects/${x.pid}/procurement`} className="mat-row">
    <span><b>{x.name}</b><small>{[x.vendor,x.linked_activities?.[0]&&'For '+x.linked_activities[0]].filter(Boolean).join(' · ')}</small></span><span>{x.pname}</span>
    <span>{x.late?<span className="chip prio high">Late</span>:x.delivered?<span className="chip prio done">Delivered</span>:<span className="chip">{x.transit?'In transit':x.status}</span>}</span><span>{day(x.required_on_site_date)}</span><span>{day(x.eta)}</span></Link>)}
   {!rows.length&&<div className="mat-row"><span>Nothing in this view.</span></div>}
  </div></>;
}

const dayCount=(d:string|undefined,asOf:string)=>d?Math.round((Date.parse(d.slice(0,10)+'T12:00:00')-Date.parse(asOf+'T12:00:00'))/864e5):null;
// One card per project with its own schedule and procurement, straight from the top view.
function ProjectCards({ops}:{ops:ReturnType<typeof useOps>}){
 const asOf=iso(new Date());
 return <><div className="section-title"><h2>Your projects</h2></div><div className="proj-cards">{ops.map(({project,board,proc})=>{
  const due=(board?.activities||[]).filter((a:Row)=>a.work_status!=='complete').map((a:Row)=>dayCount(a.raw_json?.due_date||a.finish_date,asOf)),over=due.filter((n:number|null)=>n!=null&&n<0).length,week=due.filter((n:number|null)=>n!=null&&n>=0&&n<=7).length;
  const items=(proc?.items||[]).filter((x:Row)=>x.status!=='delivered'),late=items.filter((x:Row)=>x.late).length,coming=items.filter((x:Row)=>{const n=dayCount(x.expected_delivery_date,asOf);return n!=null&&n>=0&&n<=7}).length;
  return <article className="proj-card" key={project.id}><Link className="proj-card-name" href={`/projects/${project.id}`}><b>{short(project.name)}</b><ChevronRight size={16}/></Link>
   <Link className="proj-card-row" href={`/projects/${project.id}/schedule`}><CalendarDays size={18}/><span><b>Schedule</b><small>{board?`${over} overdue · ${week} due this week`:'Loading…'}</small></span>{over>0&&<i className="bad">{over}</i>}</Link>
   <Link className="proj-card-row" href={`/projects/${project.id}/procurement`}><Package size={18}/><span><b>Procurement</b><small>{proc?`${late} late · ${coming} arriving this week`:'Loading…'}</small></span>{late>0&&<i className="bad">{late}</i>}</Link>
  </article>})}</div></>;
}

// Narrow the company-wide Schedule and Procurement tabs to one project.
function ProjectFilter({projects,value,onChange}:{projects:Row[],value:string,onChange:(v:string)=>void}){
 if(projects.length<2)return null;
 return <div className="filter-row" role="group" aria-label="Project">{[['all','All projects'],...projects.map(p=>[p.id,short(p.name)])].map(([k,l])=><button key={k} className={value===k?'active':''} aria-pressed={value===k} onClick={()=>onChange(k)}>{l}</button>)}</div>;
}

const TABS=[['home','Overview',Home],['schedule','Schedule',CalendarDays],['procurement','Procurement',Package]] as const;
export function Dashboard({projects,name,company}:{projects:Row[],name?:string,company?:string}){
 const [tab,setTab]=useState<string>('home'),[only,setOnly]=useState('all'),all=useOps(projects),ops=only==='all'?all:all.filter(o=>o.project.id===only);
 return <div className="dash"><ProjectList projects={projects}/>
  <div className="dash-main">
   <div className="tabs" role="tablist" aria-label="Dashboard">{TABS.map(([k,label,Icon])=><button key={k} role="tab" aria-selected={tab===k} className={tab===k?'active':''} onClick={()=>setTab(k)}><Icon size={16}/>{label}</button>)}</div>
   {tab==='home'&&<DailyOverview projects={projects} name={name} company={company} slot={<ProjectCards ops={all}/>}/>}
   {tab==='schedule'&&<><h1>Schedule</h1><ProjectFilter projects={projects} value={only} onChange={setOnly}/><CompanyCalendar ops={ops}/></>}
   {tab==='procurement'&&<><h1>Procurement</h1><ProjectFilter projects={projects} value={only} onChange={setOnly}/><Procurement ops={ops}/></>}
  </div></div>;
}
