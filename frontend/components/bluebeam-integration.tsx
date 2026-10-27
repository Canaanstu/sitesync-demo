'use client';
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {FileStack,X} from 'lucide-react';
import {api,Row} from '../lib/api';
import {useDialog} from '../lib/use-dialog';
import './bluebeam.css';

export function BluebeamIntegration({projects,canManage}:{projects:Row[];canManage:boolean}){
 const cache=useQueryClient(),[open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[studio,setStudio]=useState(''),[target,setTarget]=useState(''),[result,setResult]=useState<Row|null>(null);
 const status=useQuery({queryKey:['bluebeam-status'],queryFn:()=>api<Row>('/integrations/bluebeam/status')});
 const connected=status.data?.status==='sample connected';
 const catalog=useQuery({queryKey:['bluebeam-projects'],queryFn:()=>api<Row[]>('/integrations/bluebeam/projects'),enabled:open&&connected});
 const dialog=useDialog(open?'bluebeam':'',()=>setOpen(false),busy);
 // Pick the obvious choices for people: the only project, and the sample Studio project whose name matches it.
 useEffect(()=>{if(!target&&projects.length===1)setTarget(projects[0].id)},[projects,target]);
 useEffect(()=>{
  if(studio||!catalog.data?.length)return;
  const name=(projects.find(p=>p.id===target)?.name||'').toLowerCase();
  const match=catalog.data.find(c=>name.includes(String(c.name).toLowerCase()))||(catalog.data.length===1?catalog.data[0]:undefined);
  if(match)setStudio(match.id);
 },[catalog.data,target,projects,studio]);
 const allowed=canManage&&status.data?.can_manage&&status.data?.demo_mode;
 async function run(action:()=>Promise<void>){setBusy(true);setError('');try{await action();await cache.invalidateQueries({queryKey:['bluebeam-status']})}catch(e){setError(e instanceof Error?e.message:'Unable to complete this action. Try again.')}finally{setBusy(false)}}
 return <><article className="tile static bluebeam-card"><FileStack aria-hidden="true"/><b>Bluebeam Studio</b><span className="chip">{status.isPending?'Checking…':status.isError?'Unavailable':connected?'Sample connected':'Not connected'}</span><p>Read-only project files and drawing revisions.</p><small>Simulated demo · No Bluebeam account is connected. No PDFs are downloaded.</small>{status.isError?<button onClick={()=>status.refetch()}>Retry connection status</button>:<button className="primary" disabled={status.isPending} onClick={()=>{setOpen(true);setError('')}}>{connected?'Manage sample files':'Explore sample connection'}</button>}</article>
 {open&&<div className="modal-backdrop" onClick={dialog.backdrop}><section className="modal large bluebeam-dialog" ref={dialog.ref} role="dialog" aria-modal="true" aria-labelledby="bluebeam-title" tabIndex={-1} onClick={e=>e.stopPropagation()}><div className="modal-heading"><h2 id="bluebeam-title">Bluebeam Studio preview</h2><button aria-label="Close Bluebeam preview" disabled={busy} onClick={dialog.requestClose}><X/></button></div><p className="bluebeam-note">Sample data only. This demonstrates read-only file metadata. Live Bluebeam authorization is not configured; drawing contents and markups are not imported.</p>
 {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 {!status.data?.demo_mode&&<p>Sample connections are disabled on this deployment.</p>}
 {!connected?<button className="primary" disabled={busy||!allowed} onClick={()=>run(async()=>{const r=await api<Row>('/integrations/bluebeam/connect',{});setNotice(r.message)})}>{busy?'Connecting sample…':'Connect sample data'}</button>:<>
 <p>Connected by {status.data?.connection_owner||'your administrator'} · US sample · Read-only</p><p>Last metadata refresh: {status.data?.last_synced_at?new Date(status.data.last_synced_at).toLocaleString():'Not refreshed yet'}</p>
 <fieldset disabled={busy||!allowed}><legend>1. Pick the Studio project (we pre-select the best match)</legend><div className="bluebeam-choices">{catalog.isPending?<p role="status">Loading sample projects…</p>:catalog.isError?<button onClick={()=>catalog.refetch()}>Retry sample projects</button>:(catalog.data||[]).map(p=><button key={p.id} aria-pressed={studio===p.id} onClick={()=>{setStudio(p.id);setResult(null)}}>{p.name}<small>{p.file_count} sample drawing records</small></button>)}</div></fieldset>
 <fieldset disabled={busy||!allowed}><legend>2. Pick the SiteSync project to add the files to</legend><div className="bluebeam-choices">{projects.map(p=><button key={p.id} aria-pressed={target===p.id} onClick={()=>{setTarget(p.id);setResult(null)}}>{p.name}</button>)}</div>{!projects.length&&<p>Create a SiteSync project first.</p>}</fieldset>
 <button className="primary" disabled={busy||!allowed||!studio||!target} onClick={()=>run(async()=>{const r=await api<Row>('/integrations/bluebeam/sync',{project_id:target,studio_project_id:studio});setResult(r);setNotice(r.message);await cache.invalidateQueries({queryKey:['records']})})}>{busy?'Refreshing sample metadata…':'Import / refresh sample files'}</button>
 {result&&<div className="bluebeam-results"><h3>Imported sample metadata</h3>{result.records.map((r:Row)=><div key={r.id}><b>{r.filename}</b><small>Revision {r.revision} · {r.discipline} · Sample ID: {r.source_id}</small></div>)}<Link className="button" href={`/projects/${result.project_id}/documents`} onClick={()=>setOpen(false)}>View in Project documents</Link><p>Refreshing the same files updates their metadata without creating duplicates.</p></div>}
 <hr/><button disabled={busy||!allowed} onClick={()=>run(async()=>{const r=await api<Row>('/integrations/bluebeam/connection',undefined,'DELETE');setNotice(r.message);setResult(null);setStudio('');cache.removeQueries({queryKey:['bluebeam-projects']})})}>Disconnect sample</button><small>Previously imported metadata stays in Project documents.</small></>}
 {!canManage&&<p>Viewers can look but not connect. Ask a teammate with edit access.</p>}{canManage&&connected&&!status.data?.can_manage&&<p>Only the person who connected the sample can refresh or disconnect it.</p>}
 </section></div>}</>;
}
