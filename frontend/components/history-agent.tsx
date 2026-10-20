'use client';
import {useEffect,useRef,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {History,Send,Sparkles,Check,ArrowRight} from 'lucide-react';
import {api,Row} from '../lib/api';

type Turn={role:'user'|'assistant',content:string,data?:Row};
const short=(name:string)=>name.split('|')[0].trim();

export function HistoryAgent({projects}:{projects:Row[]}){
 const [pid,setPid]=useState(''),[turns,setTurns]=useState<Turn[]>([]),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),end=useRef<HTMLDivElement>(null);
 const overview=useQuery({queryKey:['history-overview',pid],queryFn:()=>api<Row>(`/history/overview${pid?`?project_id=${pid}`:''}`)});
 useEffect(()=>{end.current?.scrollIntoView({block:'nearest',behavior:'smooth'})},[turns,busy]);
 const total=overview.data?.total||0,archive=(overview.data?.projects||[]) as Row[];
 async function send(q=text){
  const question=q.trim();if(question.length<3||busy)return;
  setText('');setError('');setBusy(true);setTurns(t=>[...t,{role:'user',content:question}]);
  try{
   const r=await api<Row>('/history/ask',{question,project_id:pid||null,messages:turns.slice(-6).map(t=>({role:t.role,content:t.content}))});
   setTurns(t=>[...t,{role:'assistant',content:r.answer,data:r}]);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="hist-agent">
  <div className="hist-top"><div><h1>History</h1><p className="muted">Ask what happened on past projects, and what it means for the one you’re starting.</p></div>
   <label className="hist-for">Planning for<select value={pid} onChange={e=>{setPid(e.target.value);setTurns([]);setError('')}}><option value="">No specific project</option>{projects.map(p=><option key={p.id} value={p.id}>{short(p.name)}</option>)}</select></label></div>
  <div className="chips">{overview.isLoading?<span className="chip">Reading the archive…</span>:total?<><span className="chip"><History size={13}/>{total} past records</span>{archive.slice(0,4).map(p=><span className="chip" key={p.project}>{p.project}</span>)}{archive.length>4&&<span className="chip">+{archive.length-4} more</span>}</>:<span className="chip warn">No past records yet</span>}</div>
  {!overview.isLoading&&!total&&<section className="panel hist-empty"><b>Nothing to learn from yet</b><p className="muted">Open a past project, go to its Records page and choose <b>Import Excel</b> to bring in old schedules, delivery logs, RFIs and submittals. Then ask questions here. Past projects stay private to your company.</p></section>}
  <div className="hist-thread" aria-live="polite">
   {!turns.length&&!!total&&<div className="hist-suggest"><small className="muted">Try asking</small>{(overview.data?.suggestions||[]).map((s:string)=><button key={s} onClick={()=>send(s)}><Sparkles size={14}/>{s}<ArrowRight size={14}/></button>)}</div>}
   {turns.map((t,i)=>t.role==='user'?<div className="hist-msg me" key={i}>{t.content}</div>:<div className="hist-msg bot" key={i}>
    <div className="hist-answer">{t.content}</div>
    {!!t.data?.steps?.length&&<ul className="hist-steps">{(t.data.steps as Row[]).map((s,j)=><li key={j}><Check size={13}/>{s.summary}</li>)}</ul>}
    {!!t.data?.recommended_actions?.length&&<div className="hist-actions"><b>Next steps</b><ul>{(t.data.recommended_actions as string[]).map((a,j)=><li key={j}>{a}</li>)}</ul></div>}
    <div className="chips"><span className={'chip conf '+t.data?.confidence}>{t.data?.confidence} confidence</span>{t.data?.mode==='demo'&&<span className="chip">Keyword mode · no AI model connected</span>}</div>
    {!!t.data?.sources?.length&&<details className="hist-sources"><summary>{t.data.sources.length} source record{t.data.sources.length===1?'':'s'}</summary><ul>{(t.data.sources as Row[]).map(s=><li key={s.id}><b>{s.label}</b> · {s.project} · {s.type}</li>)}</ul></details>}
   </div>)}
   {busy&&<div className="hist-msg bot"><span className="muted">Looking through past projects…</span></div>}
   {error&&<div className="error">{error}</div>}
   <div ref={end}/>
  </div>
  <form className="hist-compose" onSubmit={e=>{e.preventDefault();send()}}><input aria-label="Ask about past projects" value={text} maxLength={1000} placeholder={total?'e.g. How long did switchgear take to arrive?':'Import past records first'} disabled={!total} onChange={e=>setText(e.target.value)}/><button className="primary" disabled={busy||!total||text.trim().length<3} aria-label="Send"><Send size={16}/></button></form>
 </div>
}
