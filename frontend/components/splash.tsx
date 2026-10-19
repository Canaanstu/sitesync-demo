'use client';
import {useEffect,useState} from 'react';
import {AnimatedLogo} from './logo';

// Plays once per browser session: the logo is outlined, filled in, then "SiteSync" types out.
// Click or Escape skips it; reduced-motion users get a very short version.
export function Splash(){
 const [show,setShow]=useState(true);
 useEffect(()=>{
  try{if(sessionStorage.getItem('sitesync:splash')){setShow(false);return}}catch{}
  const done=()=>{try{sessionStorage.setItem('sitesync:splash','1')}catch{};setShow(false)};
  const t=setTimeout(done,4500);
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape')done()};
  window.addEventListener('keydown',key);
  return()=>{clearTimeout(t);window.removeEventListener('keydown',key)};
 },[]);
 if(!show)return null;
 const skip=()=>{try{sessionStorage.setItem('sitesync:splash','1')}catch{};setShow(false)};
 return <div className="splash" role="presentation" onClick={skip}>
  <div className="splash-inner"><AnimatedLogo/>
   <div className="splash-word" aria-hidden="true">{[...'SiteSync'].map((c,i)=><span key={i} style={{animationDelay:2.35+i*0.09+'s'}}>{c}</span>)}<i className="caret"/></div></div>
 </div>;
}
