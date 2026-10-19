'use client';
import {useEffect,useRef} from 'react';
import {Hammer} from 'lucide-react';
import {useGame} from '../lib/game';

export const FLOOR_XP=40,MAX_FLOORS=12;
const H=26,W=120;
const SIDES:[string,string,number][]=[['f','translateZ(60px)',0],['r','rotateY(90deg) translateZ(60px)',.22],['b','rotateY(180deg) translateZ(60px)',.12],['l','rotateY(-90deg) translateZ(60px)',.32]];

// Faces are direct children of the stage (one flat 3D context): no nested contexts, filters or culling.
function Floor({i,ghost=false}:{i:number,ghost?:boolean}){
 return <>{SIDES.map(([k,t,sh])=><div key={k} className={'tw-face '+(ghost?'ghost':'solid')} style={{width:W,height:H,left:-W/2,top:-(i+1)*H,transform:t,['--sh' as string]:sh,animationDelay:(ghost?0:i*70)+'ms'} as React.CSSProperties}/>)}</>;
}

// A CSS-3D building that gains a floor every FLOOR_XP experience points. Drag to turn it.
export function Tower({xp,compact=false}:{xp?:number,compact?:boolean}={}){
 const g=useGame(),total=xp??g.xp,floors=Math.min(MAX_FLOORS,Math.floor(total/FLOOR_XP)),done=floors>=MAX_FLOORS;
 const toNext=done?0:FLOOR_XP-(total%FLOOR_XP);
 const stage=useRef<HTMLDivElement>(null),angle=useRef(-32),drag=useRef<{x:number,a:number}|null>(null);
 useEffect(()=>{
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;let raf=0;
  const tick=()=>{if(!drag.current&&!reduce)angle.current+=.18;if(stage.current)stage.current.style.setProperty('--ry',angle.current+'deg');raf=requestAnimationFrame(tick)};
  raf=requestAnimationFrame(tick);return()=>cancelAnimationFrame(raf);
 },[]);
 const crane=floors*H+90;
 return <section className={'tower-card'+(compact?' compact':'')} aria-label={`Your tower: ${floors} of ${MAX_FLOORS} floors`}>
  <div className="tower-scene" onPointerDown={e=>{drag.current={x:e.clientX,a:angle.current};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(drag.current)angle.current=drag.current.a+(e.clientX-drag.current.x)*.6}} onPointerUp={()=>{drag.current=null}} onPointerCancel={()=>{drag.current=null}}>
   <div className="tw-stage" ref={stage} style={{['--k' as string]:Math.min(1,(compact?160:250)/(floors*H+120))} as React.CSSProperties}>
    <div className="tw-plane tw-ground"/><div className="tw-plane tw-base"/>
    {Array.from({length:floors},(_,i)=><Floor key={i} i={i}/>)}
    {!done&&<Floor i={floors} ghost/>}
    {floors>0&&<div className="tw-plane tw-roof" style={{top:-floors*H-W/2}}/>}
    {done&&<><div className="tw-pole" style={{top:-floors*H-70}}/><div className="tw-pole cross" style={{top:-floors*H-70}}/><span className="tw-beacon" style={{top:-floors*H-74}}/></>}
    {!done&&<><div className="tw-crane" style={{top:-crane,height:crane,transform:'translateX(88px) translateZ(20px)'}}/><div className="tw-crane" style={{top:-crane,height:crane,transform:'translateX(88px) translateZ(20px) rotateY(90deg)'}}/></>}
   </div>
  </div>
  <div className="tower-info">
   <div className="tower-title"><Hammer size={18}/><b>{done?'Tower complete':`Floor ${floors} of ${MAX_FLOORS}`}</b></div>
   <div className="bar" role="progressbar" aria-label="Progress to next floor" aria-valuemin={0} aria-valuemax={FLOOR_XP} aria-valuenow={done?FLOOR_XP:FLOOR_XP-toNext}><b style={{width:(done?100:(FLOOR_XP-toNext)/FLOOR_XP*100)+'%'}}/></div>
   <small>{done?'Roof, antenna and beacon unlocked.':`${toNext} XP to the next floor`}</small>
  </div>
 </section>;
}
