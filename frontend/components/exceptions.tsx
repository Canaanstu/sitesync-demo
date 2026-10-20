'use client';
import {useState} from 'react';
import Link from 'next/link';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {AlertTriangle,Check,ChevronDown,CircleCheck,Settings2,ArrowUpRight,Play,Square} from 'lucide-react';
import {api,Row} from '../lib/api';

const short=(name:string)=>(name||'').split('|')[0].trim();
const day=(v?:string)=>v?new Date(String(v).slice(0,10)+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'}):'';
const rel=(d?:number|null)=>d==null?'':d<0?`${-d} day${d===-1?'':'s'} overdue`:d===0?'today':`in ${d} day${d===1?'':'s'}`;
const TYPE:Record<string,string>={procurement:'Material',schedule:'Activity',rfis:'RFI',submittals:'Submittal',emails:'Email'};
const LEVEL:Record<string,string>={high:'High',medium:'Medium',low:'Low'};
const val=(v:unknown)=>/^\d{4}-\d{2}-\d{2}/.test(String(v))?day(String(v)):String(v);

/** The three layers behind one exception: why it was flagged, what it is based on, what it affects. */
export function TraceLayers({trace}:{trace:Row}){
 const w=trace.why,ev=(trace.evidence||[]) as Row[],af=trace.affects||{},work=(af.activities||[]) as Row[],insp=(af.inspections||[]) as Row[];
 return <div className="trace">
  {w&&<section className="trace-layer"><h4><span>1</span>Why this was flagged</h4><p><b>{w.label}.</b> {w.what}</p><p className="muted"><b>It clears when:</b> {w.clears_when}</p><ol className="trace-steps">{(w.steps as string[]).map((s,i)=><li key={i}>{s}</li>)}</ol></section>}
  <section className="trace-layer"><h4><span>2</span>What it is based on</h4>{ev.length?ev.map(e=><div className="trace-rec" key={e.id}><div className="trace-rec-head"><b>{e.label||'Record'}</b><small>{TYPE[e.type]||e.type}</small></div>{e.missing?<small className="muted">This record was removed.</small>:<dl>{(e.facts as Row[]).map(f=><div key={f.label}><dt>{f.label}</dt><dd>{val(f.value)}</dd></div>)}</dl>}</div>):<p className="muted">No records are attached.</p>}</section>
  <section className="trace-layer"><h4><span>3</span>What it affects</h4><ul className="trace-impact">{((af.summary||[]) as string[]).map((s,i)=><li key={i}>{s}</li>)}</ul>
   {work.length>0&&<div className="trace-work">{work.map(a=><div key={a.id} className={'trace-act'+(a.days_until_start!=null&&a.days_until_start<=7?' soon':'')}><div><b>{a.name}</b><small>{[a.trade,a.start_date&&`starts ${day(a.start_date)}`,rel(a.days_until_start)].filter(Boolean).join(' · ')}</small></div><span className="trace-pct">{Math.round(a.percent_complete)}%</span></div>)}</div>}
   {insp.length>0&&<div className="trace-work">{insp.map(i=><div key={i.id} className="trace-act"><div><b>Inspection: {i.name}</b><small>{i.scheduled_date?`scheduled ${day(i.scheduled_date)}`:'not booked yet'}</small></div></div>)}</div>}
  </section>
  {trace.rule_settings&&Object.keys(trace.rule_settings).length>0&&<p className="muted trace-note">Thresholds for this check can be changed in the project’s Settings under Rules.</p>}
 </div>
}

/** "Why am I seeing this?" inside a task, loaded only when opened. */
export function RiskWhy({projectId,riskId}:{projectId:string,riskId:string}){
 const [open,setOpen]=useState(false);
 const q=useQuery({queryKey:['trace',projectId,riskId],queryFn:()=>api<Row>(`/projects/${projectId}/risks/${riskId}/trace`),enabled:open});
 return <details className="why-fold" onToggle={e=>setOpen((e.currentTarget as HTMLDetailsElement).open)}><summary>Why am I seeing this?</summary>{q.isLoading&&<p className="muted">Tracing…</p>}{q.error&&<p className="error">{(q.error as Error).message}</p>}{q.data&&<TraceLayers trace={q.data}/>}</details>
}

export function ExceptionsView({projects}:{projects:Row[]}){
 const qc=useQueryClient(),[only,setOnly]=useState('all'),[level,setLevel]=useState('all'),[open,setOpen]=useState<string[]>([]),[busy,setBusy]=useState(''),[error,setError]=useState('');
 const data=useQuery({queryKey:['exceptions'],queryFn:()=>api<Row>('/exceptions'),refetchInterval:30000});
 const all=(data.data?.items||[]) as Row[],items=all.filter(r=>(only==='all'||r.project_id===only)&&(level==='all'||r.severity===level));
 const counts=data.data?.counts||{high:0,medium:0,low:0};
 const toggle=(id:string)=>setOpen(o=>o.includes(id)?o.filter(x=>x!==id):[...o,id]);
 async function act(r:Row,action:string){setBusy(r.id+action);setError('');try{await api(`/projects/${r.project_id}/risks/${r.id}/${action}`,{});await qc.invalidateQueries()}catch(e){setError((e as Error).message)}finally{setBusy('')}}
 return <div className="exceptions">
  <div className="exc-head"><div><h1>Exceptions</h1><p className="muted">Everything SiteSync thinks needs a decision, most urgent first. Open one to see why it was flagged, what it is based on and what it puts at risk.</p></div></div>
  <div className="exc-summary" role="group" aria-label="Filter by priority">{(['all','high','medium','low'] as const).map(l=><button key={l} className={'exc-stat '+l+(level===l?' active':'')} aria-pressed={level===l} onClick={()=>setLevel(l)}><b>{l==='all'?all.length:counts[l]||0}</b><span>{l==='all'?'All open':LEVEL[l]}</span></button>)}</div>
  <div className="filter-row" role="group" aria-label="Filter by project"><button className={'chip-filter'+(only==='all'?' active':'')} onClick={()=>setOnly('all')}>All projects</button>{projects.map(p=><button key={p.id} className={'chip-filter'+(only===p.id?' active':'')} onClick={()=>setOnly(p.id)}>{short(p.name)}</button>)}</div>
  {error&&<div className="error">{error}</div>}
  {data.isLoading&&<p className="muted" role="status">Checking every project…</p>}
  {data.data&&!items.length&&<section className="panel exc-empty"><CircleCheck size={28}/><b>{all.length?'Nothing matches those filters':'No open exceptions'}</b><p className="muted">{all.length?'Try another project or priority.':'Every check is passing across your projects. SiteSync re-checks whenever dates, statuses or records change.'}</p></section>}
  <div className="exc-list">{items.map(r=>{const isOpen=open.includes(r.id),working=r.status==='in_progress';return <article key={r.id} className={'exc '+r.severity+(isOpen?' open':'')}>
   <button className="exc-row" aria-expanded={isOpen} onClick={()=>toggle(r.id)}>
    <span className={'exc-dot '+r.severity} aria-hidden="true"/>
    <span className="exc-main"><b>{r.title}</b><span className="exc-meta"><span className="chip">{short(r.project_name)}</span><span className="chip">{r.trace?.why?.label||'Check'}</span>{r.due_date&&<span className="chip">Due {day(r.due_date)}</span>}{working&&<span className="chip working">{r.evidence?.in_progress_by?`${String(r.evidence.in_progress_by).split(' ')[0]} is on it`:'In progress'}</span>}<span className="chip sr-or-small">{LEVEL[r.severity]} priority</span></span></span>
    <ChevronDown size={18} className="exc-chev" aria-hidden="true"/>
   </button>
   {isOpen&&<div className="exc-body"><TraceLayers trace={r.trace}/>
    <div className="exc-actions">
     <button className="primary" disabled={!!busy} onClick={()=>act(r,working?'reopen':'start')}>{working?<><Square size={14}/>Stop working</>:<><Play size={14}/>Start working</>}</button>
     <button className="success" disabled={!!busy} onClick={()=>act(r,'resolve')}><Check size={14}/>Done</button>
     <button disabled={!!busy} onClick={()=>act(r,'dismiss')}>Not an issue</button>
     <Link className="button" href={`/projects/${r.project_id}`}>Open project<ArrowUpRight size={14}/></Link>
     <Link className="button" href={`/projects/${r.project_id}/settings`}><Settings2 size={14}/>Rule settings</Link>
    </div></div>}
  </article>})}</div>
 </div>
}

const FIELD_HELP:Record<string,string>={released_statuses:'Comma separated, e.g. ordered, released, delivered',keywords:'Comma separated words or phrases'};

/** Per-project switches and thresholds for every check, so each firm can run the checks its own way. */
export function RulesPanel({projectId,canEdit}:{projectId:string,canEdit:boolean}){
 const qc=useQueryClient(),guide=useQuery({queryKey:['rules-guide'],queryFn:()=>api<Row>('/rules/guide')}),cfg=useQuery({queryKey:['rules',projectId],queryFn:()=>api<Row>(`/projects/${projectId}/rules`)});
 const [draft,setDraft]=useState<Row|null>(null),[busy,setBusy]=useState(false),[msg,setMsg]=useState('');
 const config=draft||cfg.data?.config;
 if(!guide.data||!config)return <section className="panel form-panel rules-panel"><h2>Rules</h2><p className="muted">Loading…</p></section>;
 const set=(rule:string,key:string,value:unknown)=>setDraft({...config,[rule]:{...config[rule],[key]:value}});
 const list=(v:unknown)=>Array.isArray(v)?v.join(', '):'';
 const toList=(t:string)=>t.split(',').map(x=>x.trim()).filter(Boolean);
 async function save(body:Row){setBusy(true);setMsg('');try{const r=await api<Row>(`/projects/${projectId}/rules`,body,'PUT');setDraft(null);qc.setQueryData(['rules',projectId],r);await qc.invalidateQueries({predicate:q=>q.queryKey[0]!=='rules'});setMsg('Saved. Your tasks were re-checked with the new settings.')}catch(e){setMsg((e as Error).message)}finally{setBusy(false)}}
 const build=(c:Row)=>({...Object.fromEntries(Object.entries(guide.data!.rules as Row).map(([k,g])=>[k,Object.fromEntries(['enabled',...(g.settings as string[])].map(s=>[s,c[k][s]]))])),warn_days:Number(c.warn_days)});
 return <section className="panel form-panel rules-panel"><h2>Rules</h2><p className="muted">SiteSync runs these checks every time something changes. Turn any off, change how early it warns, or how urgent it is. Changes apply to this project only.</p>
  <label className="rule-global">{guide.data.labels.warn_days}<input type="number" min={1} max={60} value={config.warn_days} disabled={!canEdit} onChange={e=>setDraft({...config,warn_days:e.target.value})}/></label>
  {Object.entries(guide.data.rules as Row).map(([key,g])=><details className="rule-card" key={key}>
   <summary><span className="rule-title">{g.label}</span><label className="switch" onClick={e=>e.stopPropagation()}><input type="checkbox" checked={!!config[key].enabled} disabled={!canEdit} onChange={e=>set(key,'enabled',e.target.checked)} aria-label={`${g.label} is on`}/><span>{config[key].enabled?'On':'Off'}</span></label></summary>
   <p className="muted">{g.what}</p>
   <div className="rule-fields">{(g.settings as string[]).map(s=><label key={s}>{guide.data!.labels[s]}
    {s==='severity'?<select value={config[key][s]} disabled={!canEdit} onChange={e=>set(key,s,e.target.value)}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
     :Array.isArray(config[key][s])?<input value={list(config[key][s])} placeholder={FIELD_HELP[s]} disabled={!canEdit} onChange={e=>set(key,s,toList(e.target.value))}/>
     :<input type="number" min={0} value={config[key][s]} disabled={!canEdit} onChange={e=>set(key,s,Number(e.target.value))}/>}</label>)}</div>
  </details>)}
  {msg&&<p className={msg.startsWith('Saved')?'notice':'error'} role="status">{msg}</p>}
  <div className="modal-actions"><button disabled={busy||!canEdit} onClick={()=>cfg.data&&save(build(cfg.data.defaults))}>Reset to defaults</button><button className="primary" disabled={busy||!canEdit||!draft} onClick={()=>save(build(config))}>{busy?'Saving…':'Save rules'}</button></div>
 </section>
}

/** What the system does, in plain words. Opened from the help button. */
export function HowItWorks({onClose}:{onClose?:()=>void}){
 const guide=useQuery({queryKey:['rules-guide'],queryFn:()=>api<Row>('/rules/guide')});
 return <div className="how">
  <section><h4>The basics</h4><ol className="trace-steps"><li><b>Pick a task.</b> Tasks are problems SiteSync found in your materials, schedule, RFIs and submittals.</li><li><b>Review and act.</b> Open it to see why it was flagged, then draft the email or RFI. Nothing sends without you.</li><li><b>Clear it.</b> Mark it done, or “not an issue” if the check was wrong.</li></ol></section>
  <section><h4>How SiteSync finds things to fix</h4><p className="muted">It re-checks the whole project whenever a date, status or record changes. Each check below becomes a task when it fires. Tap one to see exactly what it looks at.</p>
   {guide.isLoading&&<p className="muted">Loading…</p>}
   {guide.data&&Object.entries(guide.data.rules as Row).map(([k,g])=><details className="rule-card" key={k}><summary><span className="rule-title">{g.label}</span></summary><p>{g.what}</p><p className="muted"><b>Clears when:</b> {g.clears_when}</p></details>)}</section>
  <section><h4>How records get connected</h4><ul className="trace-impact"><li>A material is tied to schedule work by the links you set on the <b>Materials</b> tab.</li><li>With no link, SiteSync suggests a match from shared words in the names, like “lighting controls” and “lighting installation”. Treat name matches as suggestions and confirm them.</li><li>Dates are never guessed. If a date is missing, the check simply skips that item.</li></ul></section>
  <section><h4>What happens to a task</h4><ul className="trace-impact"><li><b>Open</b>: nobody has picked it up.</li><li><b>In progress</b>: someone pressed Start working. The whole crew sees who.</li><li><b>Done</b> or <b>Not an issue</b>: stays closed, even if SiteSync re-checks.</li><li>If the cause goes away (say the order is placed), SiteSync closes the task itself. If the problem comes back, it reopens.</li></ul></section>
  <section><h4>Make it work your way</h4><ul className="trace-impact"><li><b>Settings, then Rules</b> lets each project turn checks off, change priorities, and set how many days ahead to warn.</li><li><b>Dashboard, then Exceptions</b> shows every open task across all projects, with the reasoning behind each.</li><li><b>Dashboard, then History</b> answers questions from past projects you import from Excel.</li></ul></section>
  {onClose&&<div className="modal-actions"><button className="primary" onClick={onClose}>Got it</button></div>}
 </div>
}
