'use client';

export function Ring({value,size=96,stroke=12,children,label}:{value:number|null|undefined,size?:number,stroke?:number,children?:React.ReactNode,label?:string}){
 const pct=value==null?0:Math.min(100,Math.max(0,value)),r=(size-stroke)/2,c=2*Math.PI*r;
 return <div className="pring" style={{width:size,height:size}} role="img" aria-label={`${label||'Progress'}: ${value==null?'not set':Math.round(pct)+' percent'}`}>
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true"><circle cx={size/2} cy={size/2} r={r} className="ring-track" strokeWidth={stroke}/><circle cx={size/2} cy={size/2} r={r} className="ring-fill" strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c*(1-pct/100)} transform={`rotate(-90 ${size/2} ${size/2})`}/></svg>
  <span>{children??(value==null?'–':Math.round(pct)+'%')}</span>
 </div>;
}
