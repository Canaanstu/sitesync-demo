'use client';
import Link from 'next/link';
import {useEffect,useRef,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {Bell} from 'lucide-react';
import {api,Row} from '../lib/api';

export const whenText=(w:Row)=>w.days<0?`Overdue ${-w.days}d`:w.days===0?'Due today':w.days===1?'Due tomorrow':`Due in ${w.days} days`;
const KIND:Record<string,string>={work:'Work',inspection:'Inspection',delivery:'Delivery',task:'Task'};
const hrefFor=(w:Row)=>`/projects/${w.project_id}${w.section==='overview'?'':'/'+w.section}`;

// Everything due within a week across the projects this person can open.
export function Notifications(){
 const [open,setOpen]=useState(false),box=useRef<HTMLDivElement>(null);
 const list=useQuery({queryKey:['notifications'],queryFn:()=>api<Row[]>('/notifications'),refetchInterval:60000}).data||[];
 const late=list.filter(w=>w.overdue).length;
 useEffect(()=>{
  if(!open)return;
  const away=(e:MouseEvent)=>{if(!box.current?.contains(e.target as Node))setOpen(false)},key=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false)};
  document.addEventListener('mousedown',away);document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('mousedown',away);document.removeEventListener('keydown',key)};
 },[open]);
 return <div className="notif" ref={box}>
  <button className="icon" aria-label={list.length?`Notifications, ${list.length} due within a week`:'Notifications'} aria-expanded={open} aria-haspopup="true" onClick={()=>setOpen(!open)}><Bell size={18}/>{list.length>0&&<i className={late?'late':''}>{list.length>9?'9+':list.length}</i>}</button>
  {open&&<div className="notif-panel" role="region" aria-label="Due within a week">
   <h2>Due within a week</h2>
   {list.map(w=><Link key={w.project_id+w.key} href={hrefFor(w)} className={'notif-item'+(w.overdue?' late':'')} onClick={()=>setOpen(false)}><b>{w.title}</b><small>{KIND[w.kind]} · {w.project_name} · <span>{whenText(w)}</span></small></Link>)}
   {!list.length&&<p className="muted">Nothing due in the next 7 days.</p>}
  </div>}
 </div>;
}

// Pinned at the top of crew chat so the whole crew sees what is coming up.
export function WeekAhead({projectId}:{projectId:string}){
 const list=useQuery({queryKey:['warnings',projectId],queryFn:()=>api<Row[]>(`/projects/${projectId}/warnings`),refetchInterval:60000}).data||[];
 const [more,setMore]=useState(false);
 if(!list.length)return null;
 const shown=more?list:list.slice(0,3);
 return <div className="week-ahead" role="status"><b>Due within a week</b>
  <ul>{shown.map(w=><li key={w.key} className={w.overdue?'late':''}><span>{w.title}</span><small>{whenText(w)}</small></li>)}</ul>
  {list.length>3&&<button className="ghost small" onClick={()=>setMore(!more)}>{more?'Show less':`Show ${list.length-3} more`}</button>}</div>;
}
