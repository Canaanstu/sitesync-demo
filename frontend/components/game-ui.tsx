'use client';
import {useEffect,useState} from 'react';
import {Flame,Star} from 'lucide-react';
import {useGame} from '../lib/game';

const COLORS=['#1474a2','#0b3f5e','#0b2a3d','#8fc1db','#1474a2'];

export function Ring({value,size=96,stroke=12,children,label}:{value:number|null|undefined,size?:number,stroke?:number,children?:React.ReactNode,label?:string}){
 const pct=value==null?0:Math.min(100,Math.max(0,value)),r=(size-stroke)/2,c=2*Math.PI*r;
 return <div className="pring" style={{width:size,height:size}} role="img" aria-label={`${label||'Progress'}: ${value==null?'not set':Math.round(pct)+' percent'}`}>
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true"><circle cx={size/2} cy={size/2} r={r} className="ring-track" strokeWidth={stroke}/><circle cx={size/2} cy={size/2} r={r} className="ring-fill" strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c*(1-pct/100)} transform={`rotate(-90 ${size/2} ${size/2})`}/></svg>
  <span>{children??(value==null?'–':Math.round(pct)+'%')}</span>
 </div>;
}

export function GameBar(){
 const g=useGame();
 return <div className="game-bar" aria-label={`Level ${g.level}, ${g.xp} experience points, ${g.streak} day streak`}>
  <span className="chip streak" title="Day streak"><Flame size={16}/>{g.streak}</span>
  <span className="chip level" title={`${g.xp} XP`}><Star size={16}/>Lv {g.level}<i><b style={{width:g.levelProgress*100+'%'}}/></i></span>
 </div>;
}

type Pop={id:number,text:string,levelUp:boolean};
export function Celebrations(){
 const [pops,setPops]=useState<Pop[]>([]),[bits,setBits]=useState<{id:number,x:number,c:string,d:number,r:number}[]>([]);
 useEffect(()=>{
  const on=(e:Event)=>{
   const d=(e as CustomEvent).detail,id=Date.now()+Math.random();
   setPops(p=>[...p,{id,text:`+${d.xp} XP`,levelUp:d.levelUp}]);
   if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)setBits(b=>[...b,...Array.from({length:d.levelUp?44:22},(_,i)=>({id:id+i/100,x:Math.random()*100,c:COLORS[i%5],d:Math.random()*.3,r:Math.random()*720-360}))]);
   setTimeout(()=>{setPops(p=>p.filter(x=>x.id!==id));setBits(b=>b.filter(x=>Math.floor(x.id)!==Math.floor(id)))},2200);
  };
  window.addEventListener('sitesync:xp',on);return()=>window.removeEventListener('sitesync:xp',on);
 },[]);
 return <div className="celebrate" aria-live="polite">{bits.map(b=><i key={b.id} className="confetti" style={{left:b.x+'%',background:b.c,animationDelay:b.d+'s','--spin':b.r+'deg'} as React.CSSProperties}/>)}{pops.map(p=><div key={p.id} className="xp-pop">{p.levelUp?'Level up':p.text}</div>)}</div>;
}
