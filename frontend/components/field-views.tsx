'use client';
import {useEffect,useState} from 'react';
import {ArrowRight,CalendarDays,Check,CheckCircle2,Hammer,Hourglass,PackageCheck,Package,PackageX,PartyPopper,Plus,Search,Sparkles,Siren,Construction,Smile} from 'lucide-react';
import {Row} from '../lib/api';
import {ScheduleCalendar} from './schedule-calendar';
import {Choices,StatusChip} from './field-controls';

export const dateLabel=(s?:string)=>s?new Date(s.slice(0,10)+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'}):'Date not set';
const day=(s?:string)=>s?Date.parse(s.slice(0,10)+'T12:00:00'):0;

// Follow recorded dependencies instead of claiming a calculated critical path.
export function finishPriority(activities:Row[]){
 const aliases=new Map(activities.flatMap(a=>[[a.id,a.id],[a.activity_id||a.id,a.id]]));
 const successors=new Map<string,Row[]>();
 activities.forEach(a=>(a.predecessor_ids||[]).forEach((p:string)=>{const id=aliases.get(p)||p;successors.set(id,[...(successors.get(id)||[]),a]);}));
 function finish(a:Row,visited=new Set<string>()):number{if(visited.has(a.id))return 0;visited.add(a.id);return Math.max(day(a.forecast_finish),...(successors.get(a.id)||[]).map(n=>finish(n,visited)));}
 return [...activities].sort((a,b)=>Number(a.work_status==='complete')-Number(b.work_status==='complete')||Number(!b.forecast_finish)-Number(!a.forecast_finish)||finish(b)-finish(a)||Number(b.work_status==='blocked')-Number(a.work_status==='blocked')||day(a.start_date)-day(b.start_date));
}
export function activitySignals(a:Row,items:Row[],risks:Row[]){
 const signals=(a.blockers||[]).map((reason:string)=>{
  if(reason.startsWith('Delivery:')){const item=items.find(i=>reason==='Delivery: '+i.name);return {label:item?.late?'Late delivery':'Awaiting delivery',detail:reason.slice(10),kind:'delivery'};}
  if(reason.startsWith('Inspection:'))return {label:'Pending inspection',detail:reason.slice(12),kind:'inspection'};
  return {label:reason.startsWith('Finish ')?'Predecessor incomplete':'Review dependency',detail:reason,kind:'dependency'};
 });
 if(risks.some(r=>r.status==='open'&&r.category==='rfi'&&r.source_records?.some((s:Row)=>s.id===a.id)))signals.push({label:'Open RFI',detail:'Review the linked RFI before directing this work.',kind:'rfi'});
 return signals;
}


const nextStepUp=(v:number)=>[25,50,75,100].find(n=>n>v)??100;
const daysBetween=(a?:string,b?:string)=>a&&b?Math.round((day(a)-day(b))/864e5):null;

export const dueOf=(a:Row)=>a.raw_json?.due_date||a.finish_date;
const addDays=(iso:string,n:number)=>{const d=new Date(iso.slice(0,10)+'T12:00:00');d.setDate(d.getDate()+n);return d.toLocaleDateString('en-CA')};
// Working days between two dates, weekends excluded (the server applies the project's own calendar when it saves).
export function workdays(start?:string,finish?:string){
 if(!start||!finish)return null;
 let n=0;for(let d=new Date(start.slice(0,10)+'T12:00:00'),end=new Date(finish.slice(0,10)+'T12:00:00');d<=end;d.setDate(d.getDate()+1)){if(d.getDay()%6)n++}
 return Math.max(1,n);
}
export function dueChip(due:string|undefined,asOf:string,done=false){
 if(!due||done)return null;
 const days=daysBetween(due,asOf);
 if(days==null||days>7)return null;
 return {text:days<0?`Overdue ${-days}d`:days===0?'Due today':days===1?'Due tomorrow':`Due in ${days} days`,late:days<0};
}
const STATUS_LABEL:[string,string][]=[['all','Any status'],['upcoming','Not started'],['today','In progress'],['blocked','Blocked'],['overdue','Overdue'],['complete','Complete']];
const WEEKS=[2,3,4,6];

export function ScheduleView({board,items,risks,canEdit,busy,open,onProgress,warnings=[]}:{board:Row,items:Row[],risks:Row[],canEdit:boolean,busy:boolean,open:(kind:string,row?:Row|null)=>void,onProgress:(a:Row,value:number)=>void,warnings?:Row[]}){
 const [view,setView]=useState(''),[q,setQ]=useState(''),[trade,setTrade]=useState('all'),[status,setStatus]=useState('all'),[weeks,setWeeks]=useState(3);
 const activities:Row[]=board.activities||[];
 useEffect(()=>{
  const requested=new URLSearchParams(window.location.search).get('view');
  if(requested==='blocked'||requested==='today')setStatus(requested);
  setView(requested&&['calendar','complete','inspections','lookahead'].includes(requested)?requested:'all');
 },[]);
 const current=view||'all',asOf:string=board.as_of;
 const trades=[...new Set(activities.map(a=>a.trade).filter(Boolean))].sort() as string[];
 const matches=(a:Row)=>(trade==='all'||a.trade===trade)&&(status==='all'||a.work_status===status)&&`${a.name} ${a.trade||''}`.toLowerCase().includes(q.trim().toLowerCase());
 const filtered=activities.filter(matches);
 const shown=finishPriority(filtered).filter(a=>current==='complete'?a.work_status==='complete':status!=='all'||a.work_status!=='complete');
 const windowEnd=addDays(asOf,weeks*7);
 const ahead=filtered.filter(a=>a.work_status!=='complete'&&(a.start_date||asOf)<=windowEnd&&(a.finish_date||a.start_date||asOf)>=asOf).sort((x,y)=>String(x.start_date||'').localeCompare(String(y.start_date||'')));
 const weekOf=(a:Row)=>Math.min(weeks-1,Math.max(0,Math.floor((daysBetween(a.start_date||asOf,asOf)||0)/7)));
 const variance=board.variance_days,tone=variance==null?'':variance>0?'bad':'good';
 const soon=warnings.filter(w=>w.days<=7);
 const filterActive=q||trade!=='all'||status!=='all';
 const activityRow=(a:Row)=>{
  const signals=activitySignals(a,items,risks),pct=a.percent_complete||0,auto=['inspection','delivery'].includes(a.raw_json?.progress_source?.kind),blocked=signals.length>0,days=workdays(a.start_date,a.finish_date),chip=dueChip(dueOf(a),asOf,a.work_status==='complete');
  return <article className={'activity '+(blocked?'blocked':a.work_status==='complete'?'done':'')} key={a.id}>
   <button className="activity-main" onClick={()=>open('activity',{...a,signals})}>
    <span className="row-icon">{a.work_status==='complete'?<CheckCircle2 size={20}/>:blocked?<Construction size={20}/>:a.work_status==='today'?<Hammer size={20}/>:<Hourglass size={20}/>}</span>
    <span className="row-main"><b>{a.name}</b><small>{[a.trade,days&&`${days} working day${days>1?'s':''}`,`${dateLabel(a.start_date)} – ${dateLabel(a.finish_date)}`,`due ${dateLabel(dueOf(a))}`].filter(Boolean).join(' · ')}</small>
     {(blocked||chip)&&<span className="chips">{chip&&<span className={'chip '+(chip.late?'prio high':'due-soon')}>{chip.text}</span>}{signals.slice(0,2).map((s:Row,i:number)=><StatusChip key={i} label={s.label} tone="amber" kind={s.kind}/>)}</span>}</span>
   </button>
   <div className="progress">
    <span>{pct}% done</span>
    {pct<100&&!auto&&!blocked&&<button className="primary small" disabled={!canEdit||busy} title="Add progress" aria-label={`Add progress to ${a.name}`} onClick={()=>onProgress(a,nextStepUp(pct))}>Add 25%</button>}
    <button className="ghost" aria-label={`Edit ${a.name}`} title="Edit task" disabled={!canEdit||busy} onClick={()=>open('activity-edit',a)}>Edit</button>
   </div>
  </article>};
 return <>
  <p className={'plan-forecast '+tone}>{variance==null?'No finish forecast yet.':<>Forecast finish <b>{dateLabel(board.forecast_finish)}</b> · {variance>0?`${variance} days late`:variance===0?'on target':`${Math.abs(variance)} days early`}</>}</p>
  {soon.length>0&&<div className="week-warning" role="status"><Siren size={18}/><div><b>{soon.length} {soon.length===1?'item':'items'} due within a week</b><ul>{soon.slice(0,4).map(w=><li key={w.key}>{w.title} · {w.days<0?`overdue ${-w.days}d`:w.days===0?'today':w.days===1?'tomorrow':`in ${w.days} days`}</li>)}{soon.length>4&&<li>and {soon.length-4} more</li>}</ul></div></div>}
  <div className="toolbar">
   <Choices label="Schedule views" value={current} onChange={setView} options={[{value:'all',label:'To do'},{value:'lookahead',label:'Lookahead'},{value:'calendar',label:'Calendar'},{value:'inspections',label:'Inspections'},{value:'complete',label:'Done'}]}/>
   <span className="toolbar-actions"><button aria-label="Project dates" title="Project dates" disabled={!canEdit||busy} onClick={()=>open('profile')}><CalendarDays size={18}/></button><button disabled={!canEdit||busy} onClick={()=>open('plan')}><Sparkles size={18}/>Build</button><button className="primary" disabled={!canEdit||busy} onClick={()=>open('activity-new')}><Plus size={18}/>Task</button></span>
  </div>
  {['all','lookahead','calendar','complete'].includes(current)&&<div className="filter-bar" role="search" aria-label="Filter the schedule">
   <input type="search" value={q} onChange={e=>setQ(e.target.value)} placeholder="Search tasks, e.g. drywall" aria-label="Search tasks"/>
   {trades.length>0&&<select value={trade} onChange={e=>setTrade(e.target.value)} aria-label="Trade"><option value="all">All trades</option>{trades.map(t=><option key={t}>{t}</option>)}</select>}
   {current!=='complete'&&<select value={status} onChange={e=>setStatus(e.target.value)} aria-label="Status">{STATUS_LABEL.filter(([k])=>k!=='complete').map(([k,l])=><option key={k} value={k}>{l}</option>)}</select>}
   {current==='lookahead'&&<select value={weeks} onChange={e=>setWeeks(Number(e.target.value))} aria-label="Weeks ahead">{WEEKS.map(w=><option key={w} value={w}>{w}-week lookahead</option>)}</select>}
   {filterActive&&<button className="ghost small" onClick={()=>{setQ('');setTrade('all');setStatus('all')}}>Clear</button>}
  </div>}
  {current==='calendar'?<ScheduleCalendar board={{...board,activities:filtered}} open={open} warnings={warnings}/>:current==='lookahead'?<div className="lookahead">
   {Array.from({length:weeks},(_,w)=>{const rows=ahead.filter(a=>weekOf(a)===w),start=addDays(asOf,w*7);return <section key={w} className="look-week"><h3>{w===0?'This week':`Week of ${dateLabel(start)}`}<small>{rows.length} {rows.length===1?'task':'tasks'} · {dateLabel(start)} – {dateLabel(addDays(start,6))}</small></h3>
    <div className="list">{rows.map(activityRow)}{!rows.length&&<p className="muted look-empty">Nothing scheduled.</p>}</div></section>})}
  </div>:current==='inspections'?<>
   <div className="list">{board.inspections.map((i:Row)=><button className="row-card" key={i.id} onClick={()=>open('inspection-detail',i)}><span className="row-icon"><Search size={20}/></span><span className="row-main"><b>{i.data.name}</b><small>{i.data.scheduled_date?dateLabel(i.data.scheduled_date):'Needs appointment'}</small></span><StatusChip label={i.status} tone={i.status==='passed'?'blue':'amber'}/></button>)}
   {!board.inspections.length&&<div className="empty"><span className="empty-art"><Search size={30}/></span><h3>No inspections</h3></div>}
   <button className="fab" disabled={!canEdit||busy} onClick={()=>open('inspection')}><Plus size={18}/>Inspection</button></div>
  </>:<div className="list">{shown.map(activityRow)}
   {!shown.length&&<div className="empty"><span className="empty-art">{filterActive?<Search size={30}/>:<PartyPopper size={30}/>}</span><h3>{filterActive?'No tasks match':current==='complete'?'Nothing finished yet':'All done here'}</h3></div>}
  </div>}
 </>;
}

export function ProcurementView({items,packages,canEdit,busy,open}:{items:Row[],packages:Row[],canEdit:boolean,busy:boolean,open:(kind:string,row?:Row|null)=>void}){
 const [view,setView]=useState('conflicts');
 const conflicts=items.filter(i=>i.late&&i.status!=='delivered'),incoming=items.filter(i=>i.status!=='delivered');
 const received=packages.filter(p=>p.status==='received');
 const deliveredWithoutPackages=items.filter(i=>i.status==='delivered'&&!packages.some(p=>p.data.procurement_id===i.id));
 const shown=[...(view==='conflicts'?conflicts:incoming)].sort((a,b)=>day(a.schedule_need_date)-day(b.schedule_need_date));
 return <>
  <div className="toolbar"><Choices label="Procurement views" value={view} onChange={setView} options={[{value:'conflicts',label:`Late ${conflicts.length}`},{value:'incoming',label:`Coming ${incoming.length}`},{value:'received',label:`Received ${received.length+deliveredWithoutPackages.length}`}]}/><span className="toolbar-actions"><button className="primary" disabled={!canEdit||busy} onClick={()=>open('purchase')}><Plus size={18}/>Add</button></span></div>
  {view==='received'?<div className="list">{received.map(p=><button key={p.id} className="row-card" onClick={()=>open('delivery',{item:items.find(i=>i.id===p.data.procurement_id),packages:packages.filter(x=>x.data.procurement_id===p.data.procurement_id)})}><span className="row-icon"><PackageCheck size={20}/></span><span className="row-main"><b>{p.data.label}</b><small>{items.find(i=>i.id===p.data.procurement_id)?.name||'Package'}</small></span><ArrowRight size={18}/></button>)}
   {deliveredWithoutPackages.map(item=><button className="row-card" key={item.id} onClick={()=>open('delivery',{item,packages:[]})}><span className="row-icon"><PackageCheck size={20}/></span><span className="row-main"><b>{item.name}</b><small>{item.vendor||'Delivered'}</small></span><ArrowRight size={18}/></button>)}
   {!received.length&&!deliveredWithoutPackages.length&&<div className="empty"><span className="empty-art"><Package size={30}/></span><h3>Nothing received yet</h3></div>}</div>
  :<div className="list">{shown.map(item=>{
   const linked=packages.filter(p=>p.data.procurement_id===item.id),late=daysBetween(item.expected_delivery_date,item.schedule_need_date);
   return <button className={'row-card delivery '+(item.late?'late':'')} key={item.id} onClick={()=>open('delivery',{item,packages:linked})}>
    <span className="row-icon">{item.late?<Siren size={20}/>:<Package size={20}/>}</span>
    <span className="row-main"><b>{item.name}</b><small>{item.vendor||'No vendor'}</small>
     <span className="dates"><span>{dateLabel(item.expected_delivery_date)}</span><ArrowRight size={14}/><span>need {dateLabel(item.schedule_need_date)}</span></span></span>
    {item.late?<span className="chip prio high">{late&&late>0?`${late}d late`:'Late'}</span>:linked.length>0?<span className="chip">{linked.filter(p=>p.status==='received').length}/{linked.length} in</span>:<span className="chip">On track</span>}
   </button>})}
   {!shown.length&&<div className="empty"><span className="empty-art">{view==='conflicts'?<PartyPopper size={30}/>:<Package size={30}/>}</span><h3>{view==='conflicts'?'No late deliveries':'Nothing incoming'}</h3></div>}</div>}
 </>;
}
