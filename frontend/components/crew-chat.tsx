'use client';
import {useEffect,useRef,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {FileText,MessagesSquare,Paperclip,Pencil,Send,Trash2,X} from 'lucide-react';
import {api,Row} from '../lib/api';
import {WeekAhead} from './notifications';

const clock=(v:string)=>{const d=new Date(v),today=new Date().toDateString()===d.toDateString();return d.toLocaleString('en-US',today?{hour:'numeric',minute:'2-digit'}:{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})};
const size=(n:number)=>n>1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
const mentioned=(text:string,people:Row[])=>people.filter(p=>text.includes('@'+p.name)).map(p=>p.id);
// Highlight each "@Name" that belongs to someone on the project.
function Body({text,people,mine}:{text:string,people:Row[],mine:boolean}){
 if(!text)return null;
 const names=people.map(p=>'@'+p.name).sort((a,b)=>b.length-a.length);
 if(!names.length)return <p>{text}</p>;
 const parts=text.split(new RegExp('('+names.map(n=>n.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')'));
 return <p>{parts.map((t,i)=>names.includes(t)?<span key={i} className={'mention'+(mine?' on-dark':'')}>{t}</span>:t)}</p>;
}
function Attachment({projectId,file}:{projectId:string,file:Row}){
 const href=`/api/projects/${projectId}/chat/files/${file.id}`;
 return file.content_type.startsWith('image/')
  ?<a className="chat-photo" href={href} target="_blank" rel="noreferrer"><img src={href} alt={file.filename} loading="lazy"/></a>
  :<a className="chat-file" href={href} download={file.filename}><FileText size={18}/><span><b>{file.filename}</b><small>{size(file.size)}</small></span></a>;
}

export function CrewChat({projectId,meId,admin}:{projectId:string,meId:string,admin:boolean}){
 const [text,setText]=useState(''),[file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[editing,setEditing]=useState<string|null>(null),[draft,setDraft]=useState(''),[confirm,setConfirm]=useState<string|null>(null),[pick,setPick]=useState(0);
 const end=useRef<HTMLDivElement>(null),input=useRef<HTMLTextAreaElement>(null),picker=useRef<HTMLInputElement>(null),cache=useQueryClient();
 const chat=useQuery({queryKey:['chat',projectId],queryFn:()=>api<Row[]>(`/projects/${projectId}/chat`),refetchInterval:5000});
 const people=useQuery({queryKey:['chat-people',projectId],queryFn:()=>api<Row[]>(`/projects/${projectId}/chat/members`)}).data||[];
 const list=chat.data||[],last=list[list.length-1]?.id;
 useEffect(()=>{end.current?.scrollIntoView({block:'end'})},[last]);
 // Opening the chat (and any message arriving while it is open) counts as reading it.
 useEffect(()=>{if(chat.isSuccess&&document.visibilityState==='visible')api(`/projects/${projectId}/chat/read`,{}).then(()=>cache.invalidateQueries({queryKey:['chat-unread',projectId]})).catch(()=>{})},[last,chat.isSuccess,projectId,cache]);
 // "@" followed by letters at the end of the text opens the name picker.
 const query=/(?:^|\s)@([\w ]{0,30})$/.exec(text),options=query?people.filter(p=>p.id!==meId&&p.name.toLowerCase().startsWith(query[1].toLowerCase())).slice(0,5):[];
 function choose(p:Row){setText(text.replace(/@([\w ]{0,30})$/,'@'+p.name+' '));setPick(0);input.current?.focus()}
 async function refreshAll(){await cache.invalidateQueries({queryKey:['chat',projectId]})}
 async function send(e?:React.FormEvent){e?.preventDefault();const body=text.trim();if((!body&&!file)||busy)return;setBusy(true);setError('');
  try{const f=new FormData();f.set('body',body);f.set('mentions',mentioned(body,people).join(','));if(file)f.set('file',file);await api(`/projects/${projectId}/chat`,f);setText('');setFile(null);await refreshAll()}
  catch(err){setError((err as Error).message)}finally{setBusy(false)}}
 async function saveEdit(m:Row){const body=draft.trim();if(!body||busy)return;setBusy(true);setError('');try{await api(`/projects/${projectId}/chat/${m.id}`,{body,mentions:mentioned(body,people)},'PATCH');setEditing(null);await refreshAll()}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
 async function remove(m:Row){setBusy(true);setError('');try{await api(`/projects/${projectId}/chat/${m.id}`,undefined,'DELETE');setConfirm(null);await refreshAll()}catch(err){setError((err as Error).message)}finally{setBusy(false)}}
 function key(e:React.KeyboardEvent){
  if(options.length){if(e.key==='ArrowDown'){e.preventDefault();setPick((pick+1)%options.length);return}if(e.key==='ArrowUp'){e.preventDefault();setPick((pick+options.length-1)%options.length);return}if(e.key==='Enter'||e.key==='Tab'){e.preventDefault();choose(options[pick]||options[0]);return}if(e.key==='Escape'){e.preventDefault();setText(text.replace(/@([\w ]{0,30})$/,''));return}}
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
 }
 function attach(f?: File){if(!f)return;if(f.size>5*1024*1024){setError('Attachments can be up to 5 MB.');return}setError('');setFile(f)}
 return <section className="crew-chat">
  <WeekAhead projectId={projectId}/>
  <div className="chat-scroll" role="log" aria-live="polite" aria-label="Crew messages">
   {!list.length&&!chat.isLoading&&<div className="empty"><span className="empty-art"><MessagesSquare size={30}/></span><h3>No messages yet</h3><p>Say hello to everyone on this project. Type @ to mention someone.</p></div>}
   {list.map((m,i)=>{const mine=m.user_id===meId,first=i===0||list[i-1].user_id!==m.user_id,hit=m.mentions?.includes(meId),can=mine||admin;
    return <div key={m.id} className={'chat-msg'+(mine?' mine':'')+(hit?' tagged':'')}>
     {first&&<small>{mine?'You':m.author} · {clock(m.created_at)}</small>}
     {editing===m.id
      ?<div className="chat-edit"><textarea aria-label="Edit message" value={draft} maxLength={2000} rows={2} autoFocus onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();saveEdit(m)}if(e.key==='Escape')setEditing(null)}}/><span><button className="ghost-btn" onClick={()=>setEditing(null)}>Cancel</button><button className="primary" disabled={busy||!draft.trim()} onClick={()=>saveEdit(m)}>Save</button></span></div>
      :<div className="chat-bubble">
        {(m.body||!m.files?.length)&&<div className="chat-text"><Body text={m.body} people={people} mine={mine}/></div>}
        {m.files?.map((f:Row)=><Attachment key={f.id} projectId={projectId} file={f}/>)}
        {(m.edited_at||can)&&<span className="chat-meta">{m.edited_at&&<em>edited</em>}
         {confirm===m.id?<><button onClick={()=>remove(m)} disabled={busy}>Delete?</button><button onClick={()=>setConfirm(null)} aria-label="Keep message"><X size={13}/></button></>
          :<>{mine&&m.body&&<button onClick={()=>{setEditing(m.id);setDraft(m.body);setConfirm(null)}} aria-label="Edit message"><Pencil size={13}/></button>}{can&&<button onClick={()=>setConfirm(m.id)} aria-label="Delete message"><Trash2 size={13}/></button>}</>}
        </span>}
       </div>}
    </div>})}
   <div ref={end}/>
  </div>
  {error&&<p className="form-error" role="alert">{error}</p>}
  <form className="chat-compose" onSubmit={send}>
   {file&&<div className="chat-attached"><Paperclip size={14}/><span>{file.name} · {size(file.size)}</span><button type="button" aria-label="Remove attachment" onClick={()=>setFile(null)}><X size={14}/></button></div>}
   {options.length>0&&<ul className="mention-list" role="listbox" aria-label="Mention a teammate">{options.map((p,i)=><li key={p.id} role="option" aria-selected={i===pick}><button type="button" className={i===pick?'on':''} onMouseDown={e=>{e.preventDefault();choose(p)}}>@{p.name}</button></li>)}</ul>}
   <div className="chat-row">
    <input ref={picker} type="file" hidden accept=".png,.jpg,.jpeg,.gif,.webp,.pdf,.txt,.csv,.docx,.xlsx" onChange={e=>{attach(e.target.files?.[0]);e.target.value=''}}/>
    <button type="button" className="icon" aria-label="Attach a photo or file" onClick={()=>picker.current?.click()}><Paperclip size={19}/></button>
    <textarea ref={input} aria-label="Message the crew" rows={1} value={text} maxLength={2000} placeholder="Message the crew — @ to mention" onChange={e=>{setText(e.target.value);setPick(0)}} onKeyDown={key}/>
    <button className="primary" disabled={busy||(!text.trim()&&!file)}><Send size={16}/><span className="sr-only">Send</span></button>
   </div>
  </form>
 </section>
}
