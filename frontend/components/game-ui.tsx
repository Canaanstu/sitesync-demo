'use client';
import {useEffect,useState} from 'react';
import {createPortal} from 'react-dom';
import {Flame,Star,X} from 'lucide-react';
import {useGame} from '../lib/game';
import {Tower,buildingFor,FLOOR_XP} from './tower';

const COLORS=['#1474a2','#0b3f5e','#0b2a3d','#8fc1db','#1474a2'];

export function Ring({value,size=96,stroke=12,children,label}:{value:number|null|undefined,size?:number,stroke?:number,children?:React.ReactNode,label?:string}){
 const pct=value==null?0:Math.min(100,Math.max(0,value)),r=(size-stroke)/2,c=2*Math.PI*r;
 return <div className="pring" style={{width:size,height:size}} role="img" aria-label={`${label||'Progress'}: ${value==null?'not set':Math.round(pct)+' percent'}`}>
  <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true"><circle cx={size/2} cy={size/2} r={r} className="ring-track" strokeWidth={stroke}/><circle cx={size/2} cy={size/2} r={r} className="ring-fill" strokeWidth={stroke} strokeDasharray={c} strokeDashoffset={c*(1-pct/100)} transform={`rotate(-90 ${size/2} ${size/2})`}/></svg>
  <span>{children??(value==null?'–':Math.round(pct)+'%')}</span>
 </div>;
}

export function GameBar(){
 const g=useGame(),[open,setOpen]=useState(false);
 useEffect(()=>{if(!open)return;const k=(e:KeyboardEvent)=>{if(e.key==='Escape')setOpen(false)};window.addEventListener('keydown',k);return()=>window.removeEventListener('keydown',k)},[open]);
 return <><div className="game-bar" aria-label={`Level ${g.level}, ${g.xp} experience points, ${g.streak} day streak`}>
  <span className="chip streak" title="Day streak"><Flame size={16}/>{g.streak}</span>
  <button className="chip level" title="See your building" aria-haspopup="dialog" onClick={()=>setOpen(true)}><Star size={16}/>Lv {g.level}<i><b style={{width:g.levelProgress*100+'%'}}/></i></button>
 </div>
 {open&&createPortal(<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setOpen(false)}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="tower-title"><div className="modal-heading"><h2 id="tower-title">Your building</h2><button aria-label="Close" onClick={()=>setOpen(false)}><X size={20}/></button></div><p className="muted">Finish tasks to earn XP. Every {FLOOR_XP} XP adds a floor. You have {g.xp} XP.</p><Tower/></section></div>,document.querySelector('.gx')||document.body)}</>;
}

// Shows the tower for a few seconds after a reward and lets the new floor drop in, so finishing a task visibly builds it.
// When a reward finishes a building, it is shown complete and then replaced by the next, more complicated one.
export const BUILD_MS=3600,FINISH_MS=6600;
function TowerBuild({before,after}:{before:number,after:number}){
 const from=buildingFor(before),to=buildingFor(after),finished=to.level>from.level;
 const [view,setView]=useState<{level:number,floors:number}>({level:from.level,floors:from.floors}),[caption,setCaption]=useState('');
 useEffect(()=>{
  const timers:ReturnType<typeof setTimeout>[]=[];
  if(finished){
   timers.push(setTimeout(()=>{setView({level:from.level,floors:from.size});setCaption(`${from.name} complete`)},450));
   timers.push(setTimeout(()=>{setView({level:to.level,floors:to.floors});setCaption(`New building: ${to.name}`)},3200));
  }else{
   timers.push(setTimeout(()=>{setView({level:to.level,floors:to.floors});if(to.floors>from.floors)setCaption(`Floor ${to.floors} built`)},450));
  }
  return()=>timers.forEach(clearTimeout);
 },[]);
 return <div className="tower-pop" style={{animationDuration:(finished?FINISH_MS:BUILD_MS)+'ms'}} aria-hidden="true"><Tower view={view} compact/>{caption&&<b className="tower-built">{caption}</b>}</div>;
}

type Pop={id:number,text:string,levelUp:boolean};
export function Celebrations(){
 const [pops,setPops]=useState<Pop[]>([]),[bits,setBits]=useState<{id:number,x:number,c:string,d:number,r:number}[]>([]),[build,setBuild]=useState<{id:number,before:number,after:number}|null>(null);
 useEffect(()=>{
  const on=(e:Event)=>{
   const d=(e as CustomEvent).detail,id=Date.now()+Math.random();
   setPops(p=>[...p,{id,text:`+${d.xp} XP`,levelUp:d.levelUp}]);
   if(d.label!=='Daily check-in'){setBuild({id,before:d.before,after:d.game.xp});setTimeout(()=>setBuild(b=>b?.id===id?null:b),buildingFor(d.game.xp).level>buildingFor(d.before).level?FINISH_MS:BUILD_MS)}
   if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)setBits(b=>[...b,...Array.from({length:d.levelUp?44:22},(_,i)=>({id:id+i/100,x:Math.random()*100,c:COLORS[i%5],d:Math.random()*.3,r:Math.random()*720-360}))]);
   setTimeout(()=>{setPops(p=>p.filter(x=>x.id!==id));setBits(b=>b.filter(x=>Math.floor(x.id)!==Math.floor(id)))},2200);
  };
  window.addEventListener('sitesync:xp',on);return()=>window.removeEventListener('sitesync:xp',on);
 },[]);
 return <div className="celebrate" aria-live="polite">{build&&<TowerBuild key={build.id} before={build.before} after={build.after}/>}{bits.map(b=><i key={b.id} className="confetti" style={{left:b.x+'%',background:b.c,animationDelay:b.d+'s','--spin':b.r+'deg'} as React.CSSProperties}/>)}{pops.map(p=><div key={p.id} className="xp-pop">{p.levelUp?'Level up':p.text}</div>)}</div>;
}
