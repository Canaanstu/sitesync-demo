'use client';
import {useEffect,useState} from 'react';

// Lightweight, per-browser progress. It rewards real actions (resolving an item, advancing work,
// receiving a delivery). It never changes project data and is not shared between people.
const KEY='sitesync:game';
export const XP_PER_LEVEL=200;
export type Game={xp:number,streak:number,lastDay:string,doneToday:number,day:string};
const day=()=>new Date().toLocaleDateString('en-CA');
const fresh=():Game=>({xp:0,streak:0,lastDay:'',doneToday:0,day:day()});

export function readGame():Game{
 try{
  const g={...fresh(),...JSON.parse(localStorage.getItem(KEY)||'{}')} as Game;
  if(g.day!==day()){g.day=day();g.doneToday=0;}
  return g;
 }catch{return fresh()}
}
export function award(xp:number,label='Nice work'){
 const g=readGame(),today=day();
 if(g.lastDay!==today){
  const yesterday=new Date(Date.now()-864e5).toLocaleDateString('en-CA');
  g.streak=g.lastDay===yesterday?g.streak+1:1;g.lastDay=today;
 }
 g.xp+=xp;g.doneToday+=1;
 const before=Math.floor((g.xp-xp)/XP_PER_LEVEL);
 try{localStorage.setItem(KEY,JSON.stringify(g))}catch{}
 window.dispatchEvent(new CustomEvent('sitesync:xp',{detail:{xp,label,before:g.xp-xp,game:g,levelUp:Math.floor(g.xp/XP_PER_LEVEL)>before}}));
}
export function useGame(){
 const [game,setGame]=useState<Game>(fresh());
 useEffect(()=>{
  setGame(readGame());
  const on=(e:Event)=>setGame((e as CustomEvent).detail.game);
  window.addEventListener('sitesync:xp',on);
  return()=>window.removeEventListener('sitesync:xp',on);
 },[]);
 return {...game,level:Math.floor(game.xp/XP_PER_LEVEL)+1,levelProgress:(game.xp%XP_PER_LEVEL)/XP_PER_LEVEL};
}
export const DAILY_GOAL=3;
