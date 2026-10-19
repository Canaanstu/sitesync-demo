// Hammer and nails, drawn to match lucide's 24px stroke style.
export function HammerNails({size=18}:{size?:number}){
 return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
  <path d="m13 6 3-3 4 4-3 3"/><path d="m9.5 9.5 4 4"/><path d="M15 8 4.5 18.5"/><path d="M11 5l4 4"/>
  <path d="M14 20h1.5M17 20h1.5M20 20h1"/><path d="M15 20v-2.5M18 20v-2.5"/>
 </svg>;
}

// Three people: the crew. Same 24px stroke style as lucide.
export function CrewIcon({size=22}:{size?:number}){
 return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
  <circle cx="12" cy="7" r="3"/><path d="M6.5 20v-2.5a3.5 3.5 0 0 1 3.5-3.5h4a3.5 3.5 0 0 1 3.5 3.5V20"/>
  <circle cx="4.5" cy="9.5" r="2"/><path d="M1.5 18v-1.2a2.8 2.8 0 0 1 2.8-2.8"/>
  <circle cx="19.5" cy="9.5" r="2"/><path d="M22.5 18v-1.2a2.8 2.8 0 0 0-2.8-2.8"/>
 </svg>;
}
