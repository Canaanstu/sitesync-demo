'use client';
import {useEffect,useState} from 'react';
import {Moon,Sun} from 'lucide-react';

export function ThemeToggle(){
 const [dark,setDark]=useState(false);
 useEffect(()=>{setDark(document.documentElement.dataset.theme==='dark')},[]);
 const flip=()=>{const next=dark?'light':'dark';document.documentElement.dataset.theme=next;try{localStorage.setItem('sitesync:theme',next)}catch(e){}setDark(!dark)};
 return <button className="icon" aria-label={dark?'Switch to light mode':'Switch to dark mode'} title={dark?'Light mode':'Dark mode'} onClick={flip}>{dark?<Sun size={18}/>:<Moon size={18}/>}</button>;
}
