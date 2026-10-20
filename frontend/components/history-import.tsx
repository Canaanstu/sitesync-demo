'use client';
import {useRef,useState} from 'react';
import {FileSpreadsheet,Upload,TriangleAlert,Check} from 'lucide-react';
import {api,Row} from '../lib/api';

type Sheet={sheet:string,headers:string[],kind:string|null,mapping:Record<string,number>,row_count:number,importable?:number,duplicates?:number,skipped?:number,issues?:string[],sample?:Row[],header_row:number};
type Preview={filename:string,sheets:Sheet[],kinds:Record<string,{label:string,ident:string[],fields:Record<string,{label:string,type:string}>}>};

export function HistoryImport({projectId,onDone}:{projectId:string,onDone:(message:string)=>void}){
 const input=useRef<HTMLInputElement>(null),[file,setFile]=useState<File|null>(null),[preview,setPreview]=useState<Preview|null>(null),[complete,setComplete]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[drag,setDrag]=useState(false);
 const planOf=(sheets:Sheet[])=>Object.fromEntries(sheets.map(s=>[s.sheet,{kind:s.kind,mapping:s.mapping}]));
 function form(f:File,plan:unknown,assume:boolean){const d=new FormData();d.set('file',f);d.set('plan',JSON.stringify(plan));d.set('assume_complete',String(assume));return d}
 async function analyze(f:File,plan:unknown,assume:boolean){setBusy(true);setError('');try{setPreview(await api<Preview>(`/projects/${projectId}/import/preview`,form(f,plan,assume)))}catch(e){setError((e as Error).message);if(!preview)setFile(null)}finally{setBusy(false)}}
 function pick(f?:File){if(!f)return;if(!/\.(xlsx|xls|csv)$/i.test(f.name)){setError('Choose an Excel (.xlsx) or CSV file.');return}setFile(f);setPreview(null);analyze(f,{},complete)}
 function change(sheet:string,patch:Partial<Sheet>){if(!file||!preview)return;analyze(file,planOf(preview.sheets.map(s=>s.sheet===sheet?{...s,...patch}:s)),complete)}
 function toggleComplete(v:boolean){setComplete(v);if(file&&preview)analyze(file,planOf(preview.sheets),v)}
 async function commit(){if(!file||!preview)return;setBusy(true);setError('');try{const r=await api<{message:string}>(`/projects/${projectId}/import`,form(file,planOf(preview.sheets),complete));onDone(r.message)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const ready=preview?.sheets.filter(s=>s.kind&&(s.importable||0)>0)||[],total=ready.reduce((n,s)=>n+(s.importable||0),0);
 return <div className="hist-import">
  {error&&<div className="error">{error}</div>}
  {!preview&&<div className="file-drop" data-dragging={drag} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);pick(e.dataTransfer.files[0])}}><FileSpreadsheet size={28} aria-hidden="true"/><b>{busy?'Reading '+(file?.name||'file')+'…':'Drop a spreadsheet from Procore, P6, or Excel'}</b><p>We find the headers, match the columns, and show you what will come in before anything is saved.</p><input ref={input} className="file-input-accessible" tabIndex={-1} aria-label="Choose a spreadsheet" type="file" accept=".xlsx,.xls,.csv" onChange={e=>pick(e.target.files?.[0])}/><button type="button" disabled={busy} onClick={()=>input.current?.click()}><Upload size={15}/>Choose a file</button><small className="muted">.xlsx or .csv · 15 MB max · every sheet is read</small></div>}
  {preview&&<>
   <p className="muted"><b>{preview.filename}</b> · {preview.sheets.length} sheet{preview.sheets.length===1?'':'s'}. Check each one, then import.</p>
   {preview.sheets.map(s=>{const spec=s.kind?preview.kinds[s.kind]:null;return <section className="import-sheet" key={s.sheet}>
    <div className="import-head"><div><b>{s.sheet}</b><small className="muted"> · {s.row_count} rows · headers on row {s.header_row}</small></div>
     <select aria-label={`What is in ${s.sheet}`} value={s.kind||''} disabled={busy} onChange={e=>change(s.sheet,{kind:e.target.value||null,mapping:undefined as never})}><option value="">Skip this sheet</option>{Object.entries(preview.kinds).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select></div>
    {spec&&<>
     <div className="chips"><span className="chip"><Check size={13}/>{s.importable} will import</span>{!!s.duplicates&&<span className="chip">{s.duplicates} repeated rows merged</span>}{!!s.skipped&&<span className="chip warn"><TriangleAlert size={13}/>{s.skipped} skipped</span>}</div>
     {!!s.issues?.length&&<details className="import-issues"><summary>{s.issues.length}{s.issues.length>=25?'+':''} notes</summary><ul>{s.issues.map((x,i)=><li key={i}>{x}</li>)}</ul></details>}
     <details className="import-map"><summary>Match columns</summary><div className="map-grid">{Object.entries(spec.fields).map(([f,d])=><label key={f}>{d.label}{spec.ident.includes(f)&&<em> *</em>}<select value={s.mapping[f]??''} disabled={busy} onChange={e=>{const m={...s.mapping};if(e.target.value==='')delete m[f];else m[f]=Number(e.target.value);change(s.sheet,{mapping:m})}}><option value="">Not in this file</option>{s.headers.map((h,i)=>h?<option key={i} value={i}>{h}</option>:null)}</select></label>)}</div></details>
     {!!s.sample?.length&&<div className="import-sample"><table><thead><tr>{Object.keys(spec.fields).filter(f=>s.mapping[f]!==undefined).map(f=><th key={f}>{spec.fields[f].label}</th>)}</tr></thead><tbody>{s.sample.map((r,i)=><tr key={i}>{Object.keys(spec.fields).filter(f=>s.mapping[f]!==undefined).map(f=><td key={f}>{Array.isArray(r[f])?(r[f] as string[]).join(', '):String(r[f]??'')}</td>)}</tr>)}</tbody></table></div>}
    </>}
    {!spec&&<small className="muted">Skipped. Pick what this sheet holds to bring it in.</small>}
   </section>})}
   <label className="check-row"><input type="checkbox" checked={complete} disabled={busy} onChange={e=>toggleComplete(e.target.checked)}/>These are finished jobs. Treat blank status as done, so old records don’t raise risks.</label>
   <div className="modal-actions"><button type="button" disabled={busy} onClick={()=>{setPreview(null);setFile(null)}}>Choose another file</button><button className="primary" disabled={busy||!total} onClick={commit}>{busy?'Working…':`Import ${total} record${total===1?'':'s'}`}</button></div>
   <small className="muted">Re-importing an updated copy of the same sheet updates records instead of duplicating them.</small>
  </>}
 </div>
}
