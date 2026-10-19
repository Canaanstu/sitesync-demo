'use client';
import {useEffect,useState} from 'react';

// Lightweight, per-browser progress, kept separately for each signed-in person so teammates sharing a computer
// do not share a tower. It rewards real actions (resolving an item, advancing work, receiving a delivery).
// It never changes project data and is not shared between people.
const LEGACY_KEY='sitesync:game';
let KEY=LEGACY_KEY;
// Called once the signed-in person is known. Progress saved before per-person keys existed moves to the first person who signs in.
export function setGameUser(id:string){
 const next=LEGACY_KEY+':'+id;
 try{
  if(localStorage.getItem(next)===null&&localStorage.getItem(LEGACY_KEY)!==null){localStorage.setItem(next,localStorage.getItem(LEGACY_KEY)!);localStorage.removeItem(LEGACY_KEY)}
 }catch{}
 if(KEY===next)return;
 KEY=next;
 window.dispatchEvent(new Event('sitesync:game-user'));
}
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
  const reload=()=>setGame(readGame());
  window.addEventListener('sitesync:xp',on);
  window.addEventListener('sitesync:game-user',reload);
  return()=>{window.removeEventListener('sitesync:xp',on);window.removeEventListener('sitesync:game-user',reload)};
 },[]);
 return {...game,level:Math.floor(game.xp/XP_PER_LEVEL)+1,levelProgress:(game.xp%XP_PER_LEVEL)/XP_PER_LEVEL};
}
export const DAILY_GOAL=3;
