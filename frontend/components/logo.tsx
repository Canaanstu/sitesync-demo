const BUILDINGS='M9 28V18h10v10m4-4V10h12v14m5 4V16h14v12';

export function Logo({size=38}:{size?:number}){return <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="SiteSync SS buildings"><rect width="64" height="64" rx="14" fill="#67b7eb"/><path d={BUILDINGS} fill="none" stroke="white" strokeWidth="3"/><text x="32" y="51" textAnchor="middle" fill="white" fontSize="29" fontWeight="800" fontFamily="Arial">SS</text></svg>}

// Same artwork as Logo, drawn as outlines first and filled in afterwards (see .splash in app.css).
export function AnimatedLogo({size=120}:{size?:number}){return <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="SiteSync" style={{overflow:'visible'}}>
 <rect className="l-rect" x="1" y="1" width="62" height="62" rx="13" pathLength={1}/>
 <path className="l-bld" d={BUILDINGS} pathLength={1}/>
 <text className="l-ss" x="32" y="51" textAnchor="middle" fontSize="29" fontWeight="800" fontFamily="Arial">SS</text>
</svg>}
