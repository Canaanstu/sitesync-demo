'use client';
import Link from 'next/link';
import {useEffect} from 'react';
import {useQueries} from '@tanstack/react-query';
import {ArrowRight,Bot,CalendarDays,Construction,Search,CircleHelp,FileText,Flame,Mail,MessageSquare,Package,Pin,Receipt,Target,ClipboardList,Check,Pointer,PenLine,Trophy} from 'lucide-react';
import type {ReactNode} from 'react';
import {api,Row} from '../lib/api';
import {Tower} from './tower';
import {Ring} from './game-ui';
import {DAILY_GOAL,award,readGame,useGame} from '../lib/game';

export const CAT:Record<string,{icon:ReactNode,label:string}>={
 rfi:{icon:<CircleHelp size={20}/>,label:'RFI'},submittal:{icon:<ClipboardList size={20}/>,label:'Submittal'},email_followup:{icon:<Mail size={20}/>,label:'Email'},email:{icon:<Mail size={20}/>,label:'Email'},
 rfp:{icon:<MessageSquare size={20}/>,label:'Pricing'},change_order:{icon:<Receipt size={20}/>,label:'Change'},co:{icon:<Receipt size={20}/>,label:'Change'},procurement:{icon:<Package size={20}/>,label:'Delivery'},schedule:{icon:<CalendarDays size={20}/>,label:'Schedule'}
};
export const xpFor=(severity:string)=>severity==='critical'||severity==='high'?50:severity==='medium'?30:15;
export const levelOf=(severity:string)=>['critical','high'].includes(severity)?'high':severity==='medium'?'medium':'low';

// Kept for the assistant drawer.
export function CompletionRing({value}:{value:number|null|undefined,label?:string}){return <Ring value={value} size={72} stroke={9} label="Project completion"/>}
export function PriorityChip({value}:{value:string}){const l=levelOf(value),n=l==='high'?3:l==='medium'?2:1;return <span className={'chip prio '+l}><span className="bars" aria-hidden="true">{[1,2,3].map(i=><i key={i} className={i<=n?'on':''}/>)}</span>{l==='high'?'High':l==='medium'?'Medium':'Low'}<span className="sr-only"> priority</span></span>}
export function TypeChip({value}:{value:string}){const c=CAT[value]||{icon:<Pin size={20}/>,label:value.replaceAll('_',' ')};return <span className="chip type">{c.icon}{c.label}</span>}

export function nextStep(r:Row){
 const evidence=r.evidence||{},sources=r.source_records||[],name=(type:string)=>sources.find((s:Row)=>s.type===type)?.label;
 if(r.category==='rfi')return `Ask the reviewer to answer ${name('rfis')||'the open RFI'}${r.due_date?' by '+r.due_date:''}. Confirm whether ${name('schedule')||'the linked work'} must wait.`;
 if(r.category==='submittal')return `Get a committed return date for ${name('submittals')||'the submittal'} and confirm approval before releasing materials.`;
 if(r.category==='schedule')return `Confirm a delivery date for ${name('procurement')||'the delayed material'} and review resequencing ${name('schedule')||'the affected work'}${evidence.days_late?` (${evidence.days_late} days late)`:''}.`;
 if(r.category==='procurement')return `Ask the supplier to confirm release and delivery of ${name('procurement')||'this material'}. Compare it with the required-on-site date.`;
 if(r.category==='email_followup')return `Read ${name('emails')||'the email'}, confirm the constraint with the sender, and link it to the affected activity.`;
 if(r.category==='change_order'||r.category==='co')return 'Confirm scope, cost and schedule impact with the project manager, then prepare a change-order draft.';
 if(r.category==='rfp')return 'Confirm scope and due date, then prepare the pricing request for review.';
 return 'Review the linked records, confirm the impact with the responsible person, and agree on a due date.';
}

export function QuestCard({risk,onOpen,index=0}:{risk:Row,onOpen:()=>void,index?:number}){
 const c=CAT[risk.category]||{icon:<Pin size={20}/>,label:'Item'},lvl=levelOf(risk.severity);
 return <button className={'quest '+lvl} style={{animationDelay:index*50+'ms'}} onClick={onOpen}>
  <span className="quest-icon" aria-hidden="true">{c.icon}</span>
  <span className="quest-body"><b>{risk.title}</b><span className="quest-meta"><PriorityChip value={risk.severity}/><small>{c.label}{risk.due_date?` · due ${new Date(risk.due_date.slice(0,10)+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})}`:''}</small></span></span>
  <span className="quest-reward">+{xpFor(risk.severity)}<small>XP</small></span>
 </button>;
}

const greeting=()=>{const h=new Date().getHours();return h<12?'Good morning':h<18?'Good afternoon':'Good evening'};

export function ProjectTile({p,i}:{p:Row,i:number}){
 return <Link href={'/projects/'+p.id} className={'tile tone-'+i%4}>
  <Ring value={p.completion_percent} size={84} stroke={11} label={p.name.split('|')[0]+' completion'}/>
  <b>{p.name.split('|')[0]}</b>
  <span className="tile-meta">{p.risk_count>0?<><span className="chip">{p.risk_count} to do</span>{p.high_risks>0&&<span className="chip prio high"><span className="bars" aria-hidden="true"><i className="on"/><i className="on"/><i className="on"/></span>{p.high_risks} high</span>}</>:<span className="chip prio done"><Check size={14}/>All clear</span>}</span>
 </Link>;
}

type Jump={key:string,title:string,sub:string,count?:number,href:string,icon:ReactNode,weight:number};

// Direct links into the screens people use most, built from live project data.
function useJumps(projects:Row[]):Jump[]{
 const boards=useQueries({queries:projects.flatMap(p=>[
  {queryKey:['ops-board',p.id],queryFn:()=>api(`/projects/${p.id}/ops/board`),refetchInterval:60000},
  {queryKey:['ops-procurement',p.id],queryFn:()=>api(`/projects/${p.id}/ops/procurement`),refetchInterval:60000}])});
 const jumps:Jump[]=[];
 projects.forEach((p,i)=>{
  const board=boards[i*2].data as Row|undefined,proc=boards[i*2+1].data as Row|undefined,name=p.name.split('|')[0],base='/projects/'+p.id;
  const city=board?.project?.settings?.city||p.settings?.city;
  const inspections=(board?.inspections||[]).filter((x:Row)=>x.status!=='passed').length;
  const blocked=board?.blocked?.length||0,today=board?.today?.length||0;
  const late=(proc?.items||[]).filter((x:Row)=>x.late&&x.status!=='delivered').length;
  if(inspections)jumps.push({key:p.id+'i',title:`${(city||name).split(',')[0]} inspections`,sub:name,count:inspections,href:`${base}/schedule?view=inspections`,icon:<Search size={20}/>,weight:3});
  if(blocked)jumps.push({key:p.id+'b',title:'Blocked work',sub:name,count:blocked,href:`${base}/schedule?view=blocked`,icon:<Construction size={20}/>,weight:4});
  if(today)jumps.push({key:p.id+'t',title:'Today’s schedule',sub:name,count:today,href:`${base}/schedule?view=today`,icon:<CalendarDays size={20}/>,weight:2});
  if(late)jumps.push({key:p.id+'l',title:'Late deliveries',sub:name,count:late,href:`${base}/procurement`,icon:<Package size={20}/>,weight:5});
  jumps.push({key:p.id+'c',title:'Crew plan',sub:name,href:`${base}/agents`,icon:<Bot size={20}/>,weight:1});
 });
 return jumps.sort((a,b)=>b.weight-a.weight).slice(0,8);
}

export function DailyOverview({projects,name}:{projects:Row[],name?:string}){
 const g=useGame(),total=projects.reduce((n,p)=>n+p.risk_count,0),high=projects.reduce((n,p)=>n+p.high_risks,0);
 const jumps=useJumps(projects);
 // One small reward per day for opening the app; it also keeps the streak alive.
 useEffect(()=>{if(readGame().lastDay!==new Date().toLocaleDateString('en-CA'))award(10,'Daily check-in')},[]);
 return <>
  <div className="home-grid">
   <section className="hero">
    <div><h1>{greeting()}{name?`, ${name.split(' ')[0]}`:''}</h1>
     <p className="hero-sub">{total?<><b>{total}</b> to tackle{high>0&&<> · <b>{high}</b> high priority</>}</>:'Nothing waiting.'}</p></div>
    <div className="goal"><Target size={20}/><span>Daily goal</span>
     <div className="bar" role="progressbar" aria-label="Daily goal" aria-valuemin={0} aria-valuemax={DAILY_GOAL} aria-valuenow={Math.min(DAILY_GOAL,g.doneToday)}><b style={{width:Math.min(100,g.doneToday/DAILY_GOAL*100)+'%'}}/></div>
     <strong>{Math.min(g.doneToday,DAILY_GOAL)}/{DAILY_GOAL}</strong>
     {g.doneToday>=DAILY_GOAL&&<span className="chip streak"><Flame size={14}/>Goal hit</span>}
    </div>
   </section>
   <Tower/>
  </div>
  {jumps.length>0&&<><div className="section-title"><h2>Jump to</h2></div>
   <div className="jumps">{jumps.map(j=><Link key={j.key} href={j.href} className="jump"><span className="row-icon">{j.icon}</span><span className="row-main"><b>{j.title}</b><small>{j.sub}</small></span>{j.count!=null&&<span className="chip prio high">{j.count}</span>}<ArrowRight size={16}/></Link>)}</div></>}
 </>;
}

export function ProjectDirectory({projects}:{projects:Row[]}){
 return <><h1>Projects</h1><div className="tiles">{projects.map((p,i)=><ProjectTile key={p.id} p={p} i={i}/>)}</div>{!projects.length&&<div className="empty"><span className="empty-art"><Trophy size={30}/></span><h3>No projects yet</h3></div>}</>;
}

export function Tutorial(){
 const steps:[ReactNode,string,string][]=[[<Pointer size={26} key="a"/>,'Pick a quest','Open a project. Tap a card.'],[<PenLine size={26} key="b"/>,'Review the draft','Edit it. Nothing sends without you.'],[<Trophy size={26} key="c"/>,'Clear it','Earn XP. Keep your streak.']];
 return <><h1>How it works</h1><div className="steps">{steps.map(([e,t,d],i)=><div className="step" key={String(t)}><span className="step-n">{i+1}</span><span className="step-emoji">{e}</span><b>{t}</b><small>{d}</small></div>)}</div><Link className="btn primary" href="/dashboard">Let’s go <ArrowRight size={18}/></Link></>;
}
