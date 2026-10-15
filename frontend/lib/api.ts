export type Row = Record<string, any>;
export async function api<T = Row>(path:string, body?:unknown, method?:string):Promise<T> {
  const response = await fetch('/api'+path,{method:method||(body ? 'POST':'GET'),credentials:'include',headers:body instanceof FormData?{}:{'Content-Type':'application/json'},body:body instanceof FormData?body:body?JSON.stringify(body):undefined});
  const raw = await response.text();
  let data;
  try { data = raw ? JSON.parse(raw) : {}; }
  catch { throw new Error(response.ok ? 'The server returned an unreadable response. Please retry.' : 'SiteSync could not reach the server. Please retry in a moment.'); }
  if(!response.ok) {
    if(response.status===401 && !path.includes('/auth/login') && typeof window!=='undefined') window.location.href='/login';
    const detail=Array.isArray(data.detail)?data.detail.map((e:Row)=>String(e.msg||'Invalid input').replace(/^Value error, /,'')).join(' '):data.detail;
    throw new Error(typeof detail==='string'?detail:'Please check your input and try again.');
  }
  return data;
}
