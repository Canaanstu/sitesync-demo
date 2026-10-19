// Hammer and nails, drawn to match lucide's 24px stroke style.
export function HammerNails({size=18}:{size?:number}){
 return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
  <path d="m13 6 3-3 4 4-3 3"/><path d="m9.5 9.5 4 4"/><path d="M15 8 4.5 18.5"/><path d="M11 5l4 4"/>
  <path d="M14 20h1.5M17 20h1.5M20 20h1"/><path d="M15 20v-2.5M18 20v-2.5"/>
 </svg>;
}
