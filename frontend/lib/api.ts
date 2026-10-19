export type Row = Record<string, any>;
export async function api<T = Row>(path:string, body?:unknown, method?:string):Promise<T> {
  // Static GitHub Pages build: recorded demo data in the browser instead of the FastAPI backend.
  if(process.env.NEXT_PUBLIC_STATIC_DEMO==='true'){const {mockApi}=await import('./mock-api');return mockApi(path,body,method) as Promise<T>}
  // A request that never answers would leave a dialog stuck in its "working" state, so every call has a deadline.
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),body instanceof FormData?120000:30000);
  let response:Response,raw:string;
  try{
    response=await fetch('/api'+path,{method:method||(body ? 'POST':'GET'),credentials:'include',signal:ctl.signal,headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body instanceof FormData?body:body?JSON.stringify(body):undefined});
    raw=await response.text();
  }catch(e){
    throw new Error((e as Error).name==='AbortError'?'SiteSync took too long to answer. Please try again.':'Could not reach SiteSync. Check your connection and try again.');
  }finally{clearTimeout(timer)}
  let data;
  try { data = raw ? JSON.parse(raw) : {}; }
  catch { throw new Error(response.ok ? 'The server returned an unreadable response. Please retry.' : 'SiteSync could not reach the server. Please retry in a moment.'); }
  if(!response.ok) {
    if(response.status===401 && !path.includes('/auth/login') && typeof window!=='undefined'){
      // Remember where the person was heading (an emailed invite link, for example) so sign-in can return them there.
      try{if(!/^\/(login|signup|forgot|reset|verify)/.test(location.pathname))sessionStorage.setItem('sitesync:next',location.pathname+location.search)}catch{}
      window.location.href=(process.env.NEXT_PUBLIC_BASE_PATH||'')+'/login/';
    }
    const detail=Array.isArray(data.detail)?data.detail.map((e:Row)=>String(e.msg||'Invalid input').replace(/^Value error, /,'')).join(' '):data.detail;
    throw new Error(typeof detail==='string'?detail:'Please check your input and try again.');
  }
  return data;
}
