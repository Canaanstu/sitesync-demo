'use client';
import Link from 'next/link';
import {useState} from 'react';
import {useQueries,useQuery} from '@tanstack/react-query';
import {CalendarDays,ChevronLeft,ChevronRight,ChevronDown,Home,Package} from 'lucide-react';
import {api,Row} from '../lib/api';
import {DailyOverview,levelOf} from './project-hub';

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
 const risks=useQuery({queryKey:['risks',project.id],queryFn:()=>api<Row[]>(`/projects/${project.id}/risks`)});
 const open=(risks.data||[]).filter(r=>r.status==='open');
 return <div className="side-tasks">
  {open.map(r=><Link key={r.id} href={`/projects/${project.id}`} className={'side-task '+levelOf(r.severity)}><span>{r.title}</span></Link>)}
  {risks.data&&!open.length&&<small className="muted">All clear.</small>}
  <div className="side-links"><Link href={`/projects/${project.id}`}>Open project</Link><Link href={`/projects/${project.id}/schedule`}>Schedule</Link><Link href={`/projects/${project.id}/procurement`}>Materials</Link></div>
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
 const today=iso(new Date());
 const events=(key:string)=>ops.flatMap(({project,board,proc})=>{
  const href=`/projects/${project.id}/schedule`,pn=short(project.name),out:{id:string,label:string,sub:string,kind:string,href:string}[]=[];
  (board?.activities||[]).forEach((a:Row)=>{if(a.start_date&&a.start_date<=key&&(a.finish_date||a.start_date)>=key)out.push({id:a.id,label:a.name,sub:pn,kind:a.work_status==='complete'?'event-complete':'',href})});
  (board?.inspections||[]).forEach((i:Row)=>{if(i.data.scheduled_date===key)out.push({id:i.id,label:i.data.name,sub:pn+' · inspection',kind:'event-inspection',href})});
  (proc?.items||[]).forEach((x:Row)=>{if(x.expected_delivery_date===key&&x.status!=='delivered')out.push({id:x.id,label:x.name,sub:pn+' · delivery',kind:'event-delivery',href:`/projects/${project.id}/procurement`})});
  return out;
 });
 return <section className="panel calendar-panel"><div className="section-heading"><h3 aria-live="polite">{month.toLocaleDateString('en-US',{month:'long',year:'numeric'})}</h3><div className="ops-actions"><button aria-label="Previous month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}><ChevronLeft/></button><button onClick={()=>setMonth(new Date())}>Today</button><button aria-label="Next month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}><ChevronRight/></button></div></div>
  <div className="schedule-calendar-scroll"><div className="schedule-calendar" aria-label="All projects calendar">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=><b className="calendar-weekday" key={d}>{d}</b>)}
   {dates.map(d=>{const key=iso(d);return <div className={'calendar-day '+(d.getMonth()!==month.getMonth()?'outside-month ':'')+(key===today?'calendar-today':'')} key={key}><time dateTime={key}>{d.getDate()}</time>
    {events(key).map(e=><Link key={e.id+key} href={e.href} className={'calendar-event '+e.kind}>{e.label}<small>{e.sub}</small></Link>)}</div>})}
  </div></div></section>;
}

// Every purchase across projects, late ones first.
function Materials({ops}:{ops:ReturnType<typeof useOps>}){
 const rows=ops.flatMap(({project,proc})=>(proc?.items||[]).map((x:Row)=>({...x,pid:project.id,pname:short(project.name)})))
  .sort((a:Row,b:Row)=>Number(!!b.late&&b.status!=='delivered')-Number(!!a.late&&a.status!=='delivered')||String(a.expected_delivery_date||'9').localeCompare(String(b.expected_delivery_date||'9')));
 if(!rows.length)return <div className="empty"><span className="empty-art"><Package size={30}/></span><h3>No materials yet</h3></div>;
 return <div className="mat-table" role="table" aria-label="Materials across projects">
  <div className="mat-row mat-head" role="row"><span>Item</span><span>Project</span><span>Status</span><span>Expected</span></div>
  {rows.map((x:Row)=>{const late=x.late&&x.status!=='delivered';return <Link role="row" key={x.id} href={`/projects/${x.pid}/procurement`} className="mat-row">
   <span><b>{x.name}</b>{x.linked_activities?.[0]&&<small>For {x.linked_activities[0]}</small>}</span><span>{x.pname}</span>
   <span>{late?<span className="chip prio high">Late</span>:<span className="chip">{x.status}</span>}</span><span>{day(x.expected_delivery_date)}</span></Link>})}
 </div>;
}

const TABS=[['home','Overview',Home],['schedule','Schedule',CalendarDays],['materials','Materials',Package]] as const;
export function Dashboard({projects,name,company}:{projects:Row[],name?:string,company?:string}){
 const [tab,setTab]=useState<string>('home'),ops=useOps(projects);
 return <div className="dash"><ProjectList projects={projects}/>
  <div className="dash-main">
   <div className="tabs" role="tablist" aria-label="Dashboard">{TABS.map(([k,label,Icon])=><button key={k} role="tab" aria-selected={tab===k} className={tab===k?'active':''} onClick={()=>setTab(k)}><Icon size={16}/>{label}</button>)}</div>
   {tab==='home'&&<DailyOverview projects={projects} name={name} company={company}/>}
   {tab==='schedule'&&<><h1>Schedule</h1><CompanyCalendar ops={ops}/></>}
   {tab==='materials'&&<><h1>Materials</h1><Materials ops={ops}/></>}
  </div></div>;
}
