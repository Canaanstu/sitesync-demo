'use client';
import {useState} from 'react';
import {Row} from '../lib/api';
import {ActivityChips,ChoiceField,DateField} from './field-controls';

export function ProcurementEditor({item,submittals,activities,canEdit,busy,onDirty,onSave}:{item:Row|null,submittals:Row[],activities:Row[],canEdit:boolean,busy:boolean,onDirty:()=>void,onSave:(data:Row)=>Promise<void>}){
 const [query,setQuery]=useState(''),[submittalId,setSubmittalId]=useState(item?.submittal_id||''),[lead,setLead]=useState(String(item?.lead_time_days??''));
 const sub=submittals.find(s=>s.id===submittalId);
 function selectSub(id:string){setSubmittalId(id);}
 return <form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);onSave({...Object.fromEntries(f),submittal_id:submittalId||null,lead_time_days:lead===''?null:Number(lead),expected_delivery_date:f.get('expected_delivery_date')||null,required_on_site_date:f.get('required_on_site_date')||null,activity_ids:f.getAll('activity_ids')})}}>
 <fieldset disabled={!canEdit||busy} className="procurement-fields" onChange={onDirty}>
 <label>Material / equipment<input name="name" defaultValue={item?.name||''} required minLength={2}/></label>
 <label>Vendor<input name="vendor" defaultValue={item?.vendor||''}/></label>
 <ChoiceField label="Order status" name="status" options={['not released','ordered','in transit','delivered']} defaultValue={item?.status||'not released'}/>
 <div className="ops-two"><DateField label="Arriving on" name="expected_delivery_date" defaultValue={item?.expected_delivery_date||''}/><DateField label="Needed on site" name="required_on_site_date" defaultValue={item?.required_on_site_date||''}/></div>
 <details className="fold-inline"><summary>More details</summary>
 <label>Vendor email<input type="email" name="vendor_email" defaultValue={item?.raw_json?.vendor_email||''}/></label>
 <fieldset className="field-choices"><legend>Linked submittal</legend><label>Find a project submittal<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search number or title"/></label>
 <div className="submittal-options"><label className="checkbox"><input type="radio" name="submittal-choice" checked={!submittalId} onChange={()=>selectSub('')}/>No submittal linked</label>{submittals.filter(s=>s.id===submittalId||`${s.number||''} ${s.title}`.toLowerCase().includes(query.toLowerCase())).map(s=><label className="checkbox" key={s.id}><input type="radio" name="submittal-choice" checked={s.id===submittalId} onChange={()=>selectSub(s.id)}/>{s.number?`${s.number} · `:''}{s.title} — {s.status||'Status not confirmed'}</label>)}</div>
 {!submittals.length&&<p>No submittals available in this project. Sync an authorized source to bring them in.</p>}
 </fieldset>
 {sub&&<section className="panel procurement-evidence" aria-label="Linked submittal evidence"><h3>{sub.number} · {sub.title}</h3><p><b>Approval:</b> {sub.status||'Not confirmed'}</p><p><b>Responsible reviewer:</b> {sub.ball_in_court||'Not assigned'}</p><p><b>Due:</b> {sub.due_date||'Not confirmed'}</p><p><b>Recorded lead time:</b> {sub.lead_time_days==null?'Not confirmed':`${sub.lead_time_days} calendar days`}</p>{sub.description&&<p>{sub.description}</p>}<p>Source: linked project submittal. Review approval before releasing materials.</p>{sub.lead_time_days!=null&&<button type="button" onClick={()=>{setLead(String(sub.lead_time_days));onDirty()}}>Use submittal lead time</button>}</section>}
 <label>Lead time (calendar days)<input name="lead_time_days" type="number" min={0} max={3650} value={lead} onChange={e=>setLead(e.target.value)} placeholder="Not confirmed"/></label><p>Leave blank if unknown. Choosing a submittal does not overwrite a confirmed lead time.</p>
 <ActivityChips activities={activities.map(a=>({id:a.id,name:a.name}))} selected={item?.raw_json?.activity_ids||[]}/><label>Notes<textarea name="notes" defaultValue={item?.notes||''}/></label></details>
 {canEdit&&<button className="primary" disabled={busy}>{busy?'Saving…':'Save'}</button>}
 </fieldset></form>;
}
