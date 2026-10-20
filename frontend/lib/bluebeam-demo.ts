type Row=Record<string,any>;
const catalog=[
 {id:'sample-studio-sage',name:'Sage and Sound',files:[['A101','A101 - Lower Level Plan.pdf','C','Architectural'],['E201','E201 - Sauna Electrical Coordination.pdf','B','Electrical'],['M101','M101 - Mechanical Plan.pdf','A','Mechanical']]},
 {id:'sample-studio-alo',name:'Alo Yoga',files:[['A101','A101 - Retail Floor Plan.pdf','D','Architectural'],['E101','E101 - Lighting Control Plan.pdf','C','Electrical'],['A501','A501 - Millwork Details.pdf','B','Architectural']]}
];
// Session-only sample state, matching the rest of the static demo. Never stores credentials.
let owner:string|null=null,lastSynced:string|null=null;
export function bluebeamDemo(data:Row,path:string,method:string,body:Row,authenticated:boolean):any{
 if(!authenticated)throw new Error('Sign in to explore the Bluebeam sample.');
 const me=data['GET /me'],admin=['owner','admin'].includes(me.role),manage=admin&&(!owner||owner===me.id);
 const action=path.slice('/integrations/bluebeam/'.length);
 if(method==='GET'&&action==='status')return {status:owner?'sample connected':'disconnected',demo_mode:true,connection_owner:owner?me.full_name:null,can_manage:manage,scopes:['read_prime (simulated)'],region:'US (sample)',last_synced_at:lastSynced};
 if(method==='GET'&&action==='projects'){if(!owner)throw new Error('Connect the Bluebeam sample before importing.');return catalog.map(p=>({id:p.id,name:p.name,file_count:p.files.length,demo:true}))}
 if(!manage)throw new Error('Only the connection owner or a company administrator can manage this sample.');
 if(method==='POST'&&action==='connect'){owner=me.id;return {message:'Sample connected. No Bluebeam account was contacted.'}}
 if(method==='DELETE'&&action==='connection'){owner=null;return {message:'Sample disconnected. Previously imported metadata remains in Project documents. No external grant existed.'}}
 if(method==='POST'&&action==='sync'){
  if(!owner)throw new Error('Connect the Bluebeam sample before importing.');
  if(!(data['GET /projects']||[]).some((p:Row)=>p.id===body.project_id))throw new Error('SiteSync project not found.');
  const studio=catalog.find(p=>p.id===body.studio_project_id);if(!studio)throw new Error('Studio sample project not found.');
  const key=`GET /projects/${body.project_id}/documents`,docs:Row[]=data[key]||[];lastSynced=new Date().toISOString();
  const records=studio.files.map(([fileId,filename,revision,discipline])=>{
   const external=`bluebeam:${studio.id}:${fileId}`;let doc=docs.find(d=>d.source_external_id===external);
   if(!doc){doc={id:`sample-bluebeam-${body.project_id}-${studio.id}-${fileId}`,project_id:body.project_id,source_external_id:external,created_at:lastSynced};docs.push(doc)}
   Object.assign(doc,{filename,file_type:'pdf',revision,is_current:true,raw_text:'',raw_json:{provider:'bluebeam',studio_project_id:studio.id,studio_project_name:studio.name,file_id:fileId,discipline,last_synced_at:lastSynced,metadata_only:true,demo:true}});
   data[`GET /projects/${body.project_id}/sources/documents/${doc.id}`]=doc;
   return {id:doc.id,filename,revision,discipline,source_id:external,demo:true};
  });data[key]=docs;
  return {message:`${records.length} sample file records refreshed. Drawing contents were not downloaded.`,last_synced_at:lastSynced,records,project_id:body.project_id};
 }
 throw new Error('Unsupported Bluebeam sample action.');
}
