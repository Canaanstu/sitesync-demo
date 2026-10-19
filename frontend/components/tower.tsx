'use client';
import {useEffect,useRef} from 'react';
import {Hammer} from 'lucide-react';
import {useGame} from '../lib/game';

export const FLOOR_XP=40;
type Part={w:number,x:number,d?:number,r?:number};

// Each finished building resets the tower and unlocks a taller, more complicated Singapore landmark.
const NAMES=['HDB block','The Interlace','Marina Bay Sands','Supertree Grove','Burj Al Arab','Cayan Tower','Burj Khalifa','Singapore–Dubai skyline'];
export const sizeOf=(level:number)=>Math.min(40,12+4*level);
// Taller buildings get shorter floors so every design fits the same card.
const floorH=(level:number)=>[26,26,26,26,22,19,16,15][Math.min(level,7)];
export const nameOf=(level:number)=>NAMES[Math.min(level,NAMES.length-1)];

// Walk the total through each building in turn: how many are finished and how far into the current one.
export function buildingFor(xp:number){
 let left=Math.floor(Math.max(0,xp)/FLOOR_XP),level=0;
 while(left>=sizeOf(level)){left-=sizeOf(level);level++}
 return {level,floors:left,size:sizeOf(level),name:nameOf(level)};
}

// The footprint(s) of floor i for a given building. Each part is a box: width w, depth d, centred x across.
function partsAt(level:number,i:number,size:number):Part[]{
 // HDB block: the long public-housing slab that most Singaporeans live in.
 if(level===0)return [{w:150,x:0,d:56}];
 // The Interlace: horizontal slabs stacked and shifted like a jumbled stack of blocks.
 if(level===1)return [{w:104,x:[-38,30,-18,40,-4,-34,22][Math.floor(i/3)%7],d:60}];
 // Marina Bay Sands: three slender towers carrying the SkyPark, a ship-shaped deck on top.
 if(level===2)return i<size-3?[-80,0,80].map(x=>({w:36,x,d:70})):[{w:236,x:0,d:52}];
 // Gardens by the Bay: Supertrees of different heights, each ending in a wide canopy.
 if(level===3)return [{x:-72,h:size-8},{x:0,h:size},{x:72,h:size-4}].filter(t=>i<t.h).map(t=>({w:i>=t.h-2?74:26,x:t.x,d:i>=t.h-2?74:26}));
 // Burj Al Arab: a sail-shaped hotel, wide at the base and narrowing up, with its mast on the leading edge.
 if(level===4){const w=104-Math.round(i/size*60);return [{w,x:-52+w/2+8,d:34},{w:16,x:-46,d:30}]}
 // Cayan Tower: a slim tower whose floors twist a quarter turn from bottom to top.
 if(level===5)return [{w:78,x:0,d:78,r:Math.round(i/size*90)}];
 // Burj Khalifa: a tapering core in setback tiers, with wings that step away at different heights and a thin spire.
 if(level===6){const t=Math.floor(i/(size/8)),core=i>=size-4?9:70-t*7;return [{w:core,x:0,d:core},...(i<size*.75&&i<size-4?[{w:22,x:-(core/2+10),d:34}]:[]),...(i<size*.55?[{w:22,x:core/2+10,d:34}]:[])]}
 // The skyline: a crowned tower, a tapering centrepiece and a SkyPark-topped tower side by side.
 const crowned=i>=size-8&&i<size-6,taper=70-Math.floor(i/size*38);
 return [...(i<size-6?[{w:crowned?72:48,x:-84,d:crowned?72:48}]:[]),{w:taper,x:0,d:taper},...(i<size-11?[{w:50,x:84,d:50}]:i<size-8?[{w:96,x:84,d:50}]:[])];
}

function sides(w:number,d:number,r:number):[string,string,number,number][]{
 const t=`rotateY(${r}deg) `;
 return [['f',t+`translateZ(${d/2}px)`,0,w],['r',t+`rotateY(90deg) translateZ(${w/2}px)`,.22,d],['b',t+`rotateY(180deg) translateZ(${d/2}px)`,.12,w],['l',t+`rotateY(-90deg) translateZ(${w/2}px)`,.32,d]];
}

// Faces are direct children of the stage (one flat 3D context): no nested contexts, filters or culling.
function Floor({i,part,h,ghost=false,drop=false}:{i:number,part:Part,h:number,ghost?:boolean,drop?:boolean}){
 return <>{sides(part.w,part.d??part.w,part.r??0).map(([k,t,sh,fw],n)=><div key={k} className={'tw-face '+(ghost?'ghost':'solid')+(drop?' drop':'')} style={{width:fw,height:h,left:-fw/2,top:-(i+1)*h,transform:`translateX(${part.x}px) ${t}`,['--sh' as string]:sh,animationDelay:(drop?n*60:0)+'ms'} as React.CSSProperties}/>)}</>;
}

// A CSS-3D building that gains a floor every FLOOR_XP experience points. Drag to turn it.
// `view` forces a specific building and floor count (used to play the finish-and-reset celebration).
export function Tower({xp,compact=false,view}:{xp?:number,compact?:boolean,view?:{level:number,floors:number}}={}){
 const g=useGame(),b=buildingFor(xp??g.xp),level=view?.level??b.level,size=sizeOf(level),H=floorH(level),floors=Math.min(size,view?view.floors:b.floors),done=floors>=size;
 const toNext=done?0:FLOOR_XP-(Math.max(0,xp??g.xp)%FLOOR_XP);
 // Floors above the last count this component rendered are new, so they drop into place instead of just appearing.
 const seen=useRef({floors,level}),fresh=seen.current.level===level?Math.min(seen.current.floors,floors):0;
 useEffect(()=>{seen.current={floors,level}},[floors,level]);
 const stage=useRef<HTMLDivElement>(null),angle=useRef(-32),drag=useRef<{x:number,a:number}|null>(null);
 useEffect(()=>{
  const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;let raf=0;
  const tick=()=>{if(!drag.current&&!reduce)angle.current+=.18;if(stage.current)stage.current.style.setProperty('--ry',angle.current+'deg');raf=requestAnimationFrame(tick)};
  raf=requestAnimationFrame(tick);return()=>cancelAnimationFrame(raf);
 },[]);
 const built=Array.from({length:floors},(_,i)=>partsAt(level,i,size));
 const next=done?[]:partsAt(level,floors,size);
 // A roof goes on every part whose footprint ends at that floor.
 const roofs=built.flatMap((parts,i)=>parts.filter(p=>!(built[i+1]||[]).some(q=>q.w===p.w&&q.x===p.x&&q.d===p.d)).map(p=>({...p,i})));
 const reach=Math.max(...Array.from({length:size},(_,i)=>Math.max(...partsAt(level,i,size).map(p=>Math.abs(p.x)+p.w/2))));
 const crane=floors*H+90;
 return <section className={'tower-card'+(compact?' compact':'')} aria-label={`Your tower: ${nameOf(level)}, ${floors} of ${size} floors`}>
  <div className="tower-scene" onPointerDown={e=>{drag.current={x:e.clientX,a:angle.current};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(drag.current)angle.current=drag.current.a+(e.clientX-drag.current.x)*.6}} onPointerUp={()=>{drag.current=null}} onPointerCancel={()=>{drag.current=null}}>
   <div className="tw-stage" ref={stage} style={{['--k' as string]:Math.min(1,(compact?160:250)/(Math.max(floors,12)*H+120),(compact?150:230)/Math.max(120,reach*2))} as React.CSSProperties}>
    <div className="tw-plane tw-ground"/><div className="tw-plane tw-base" style={{left:-reach-10,top:-reach-10,width:reach*2+20,height:reach*2+20}}/>
    {built.map((parts,i)=>parts.map((p,n)=><Floor key={`${level}-${i}-${n}`} i={i} part={p} h={H} drop={i>=fresh}/>))}
    {next.map((p,n)=><Floor key={'g'+n} i={floors} part={p} h={H} ghost/>)}
    {roofs.map(r=><div key={`r${r.i}-${r.x}-${r.w}`} className="tw-plane tw-roof" style={{left:r.x-r.w/2,top:-(r.i+1)*H-(r.d??r.w)/2,width:r.w,height:r.d??r.w,transform:`rotateX(90deg) rotateZ(${-(r.r??0)}deg)`}}/>)}
    {done&&partsAt(level,size-1,size).map((p,n)=><span key={'t'+n}><div className="tw-pole" style={{left:p.x-1.5,top:-floors*H-70}}/><div className="tw-pole cross" style={{left:p.x-1.5,top:-floors*H-70}}/><span className="tw-beacon" style={{left:p.x-5,top:-floors*H-74}}/></span>)}
    {!done&&<><div className="tw-crane" style={{top:-crane,height:crane,transform:`translateX(${reach+28}px) translateZ(20px)`}}/><div className="tw-crane" style={{top:-crane,height:crane,transform:`translateX(${reach+28}px) translateZ(20px) rotateY(90deg)`}}/></>}
   </div>
  </div>
  <div className="tower-info">
   <div className="tower-title"><Hammer size={18}/><b>{done?`${nameOf(level)} complete`:`${nameOf(level)} · floor ${floors} of ${size}`}</b></div>
   <div className="bar" role="progressbar" aria-label="Progress to next floor" aria-valuemin={0} aria-valuemax={FLOOR_XP} aria-valuenow={done?FLOOR_XP:FLOOR_XP-toNext}><b style={{width:(done?100:(FLOOR_XP-toNext)/FLOOR_XP*100)+'%'}}/></div>
   <small>{done?'Roof, antenna and beacon unlocked.':`${toNext} XP to the next floor`}{level>0&&!done?` · Building ${level+1}`:''}</small>
  </div>
 </section>;
}
