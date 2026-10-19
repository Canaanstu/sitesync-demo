'use client';
import {useEffect,useRef,useState} from 'react';
import Link from 'next/link';
import {ArrowRight,Bot,CalendarDays,Check,CircleHelp,ClipboardList,Mail,Package,Plus,Search,ShieldCheck,Trophy,Flame} from 'lucide-react';
import {BlueprintIcon} from './icons';
import {Logo} from './logo';
import {Splash} from './splash';
import {Tower} from './tower';
import {PriorityChip} from './project-hub';
import {api} from '../lib/api';

// Illustrative sample items for the interactive preview. Nothing here is real project data.
const SAMPLE=[
 {t:'Lighting controls may miss the required date',cat:'Delivery',level:'high',icon:Package,next:'Ask the supplier to confirm release and delivery. Compare it with the date the work needs it.',xp:50},
 {t:'RFI 042 may affect ceiling close',cat:'RFI',level:'high',icon:CircleHelp,next:'Ask the reviewer for an answer and confirm whether the ceiling work must wait.',xp:50},
 {t:'Millwork ship date slipped five days',cat:'Email',level:'medium',icon:Mail,next:'Confirm the new date with the sender and link it to the install activity.',xp:30},
 {t:'Electrical rough-in inspection needs a date',cat:'Inspection',level:'low',icon:Search,next:'Record the appointment so it stops holding the next activity.',xp:15},
];

function useReveal(){
 useEffect(()=>{
  const els=[...document.querySelectorAll<HTMLElement>('.reveal')];
  if(!('IntersectionObserver' in window)){els.forEach(e=>e.classList.add('in'));return}
  const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.15});
  els.forEach(e=>io.observe(e));return()=>io.disconnect();
 },[]);
}

function LiveDemo({cta}:{cta:{href:string,label:string}}){
 const [done,setDone]=useState<number[]>([]),[open,setOpen]=useState<number|null>(null),[pop,setPop]=useState('');
 const xp=160+done.reduce((n,i)=>n+80,0),cleared=done.length===SAMPLE.length;
 function finish(i:number){setDone(d=>[...d,i]);setPop(`+${SAMPLE[i].xp} XP`);setTimeout(()=>setPop(''),1400);setOpen(SAMPLE.findIndex((_,n)=>n!==i&&!done.includes(n)));}
 return <div className="live" id="live">
  <Tower xp={xp} compact/>
  {pop&&<div className="live-pop" aria-live="polite">{pop}</div>}
  <div className="live-quests" role="list" aria-label="Sample tasks">
   {SAMPLE.map((q,i)=>{const isDone=done.includes(i),isOpen=open===i&&!isDone;return <div role="listitem" key={q.t} className={'live-quest '+q.level+(isDone?' done':'')}>
    <button className="live-row" aria-expanded={isOpen} disabled={isDone} onClick={()=>setOpen(isOpen?null:i)}><span className="row-icon">{isDone?<Check size={20}/>:<q.icon size={20}/>}</span><span className="row-main"><b>{q.t}</b><span className="quest-meta"><PriorityChip value={q.level}/><small>{q.cat}</small></span></span><span className="quest-reward">+{q.xp}<small>XP</small></span></button>
    {isOpen&&<div className="live-detail"><p>{q.next}</p><div className="ops-actions"><button className="primary small" onClick={()=>finish(i)}><Check size={14}/>Mark done</button></div></div>}
   </div>})}
  </div>
  <div className="live-foot">{cleared?<><b>Tower complete.</b><Link className="button primary" href={cta.href}>{cta.label}<ArrowRight size={16}/></Link></>:<small>Illustrative preview. Tap a task, mark it done, and watch the tower grow.</small>}{done.length>0&&!cleared&&<button className="ghost small" onClick={()=>{setDone([]);setOpen(null)}}>Reset</button>}</div>
 </div>;
}

const FAQ:[string,string][]=[
 ['Is SiteSync available now?','Yes. Create a free account and try it with sample projects. Your workspace is private to you. SiteSync is in beta, so use fictional or test information.'],
 ['Do we need to replace Procore?','No. SiteSync is designed to sit alongside the tools your team already uses. Connections to Procore and Microsoft 365 are planned and will be confirmed per company.'],
 ['Will it send emails or make decisions for us?','No. SiteSync prepares recommendations and drafts. Your team reviews the wording and recipients, and approves before anything leaves.'],
 ['Does trying it commit us to anything?','No. Trying it is free. Any beta scope, pricing, permissions and data-handling terms would be agreed separately before real project data is involved.'],
];
const FEATURES=[
 {icon:CalendarDays,t:'Plan',d:'Daily work plan with blockers, progress and a forecast against turnover.'},
 {icon:Package,t:'Materials',d:'Deliveries checked against the date the work needs them.'},
 {icon:CircleHelp,t:'RFIs',d:'Start from a field photo and review a coordinated draft.'},
 {icon:Search,t:'Inspections',d:'Hold points tied to the activities they block.'},
 {icon:Bot,t:'Crew',d:'A short daily list of what to chase first.'},
 {icon:ShieldCheck,t:'Evidence first',d:'Every item links to the records behind it.'},
];

export function Landing(){
 const [scrolled,setScrolled]=useState(false),[faq,setFaq]=useState<number|null>(0),[signup,setSignup]=useState(true);
 useReveal();
 useEffect(()=>{api('/health').then(h=>setSignup(h.signup_open!==false)).catch(()=>{})},[]);
 useEffect(()=>{const on=()=>setScrolled(window.scrollY>8);on();window.addEventListener('scroll',on,{passive:true});return()=>window.removeEventListener('scroll',on)},[]);
 const cta=signup?{href:'/signup',label:'Try it now'}:{href:'/login',label:'Sign in'};
 return <div className="gx site"><Splash/>
  <header className={'site-nav'+(scrolled?' scrolled':'')}><Link href="/" className="brand" aria-label="SiteSync home"><Logo/><span>SiteSync</span></Link>
   <nav aria-label="Main"><a href="#how">How it works</a><a href="#features">What’s inside</a><a href="#faq">Questions</a></nav>
   <div className="site-actions">{signup&&<Link className="ghost-btn" href="/login">Sign in</Link>}<Link className="button primary" href={cta.href}>{cta.label}<ArrowRight size={16}/></Link></div></header>
  <main>
   <section className="site-hero">
    <div className="hero-copy">
     <span className="eyebrow-tag"><i/>Free to try</span>
     <h1>Less chasing.<br/><em>More building.</em></h1>
     <p className="hero-lead">Project information is everywhere. Your next step shouldn’t be.</p>
     <p>SiteSync turns schedule, delivery, RFI and inspection risks into a short list of next steps you can clear. Every draft stays yours to review.</p>
     <div className="hero-cta"><Link className="button primary big" href={cta.href}>{cta.label}<ArrowRight size={18}/></Link>{signup&&<Link className="ghost-btn" href="/login">Sign in</Link>}</div>
     <ul className="hero-points"><li><Check size={16}/>Sample projects ready</li><li><Check size={16}/>Private workspace</li><li><Check size={16}/>You approve every send</li></ul>
    </div>
    <LiveDemo cta={cta}/>
   </section>
   <p className="site-tools">Designed to work alongside Procore and Microsoft 365 / Outlook. Connections are planned; availability and company authorization are confirmed per beta.</p>

   <section className="site-section" id="how">
    <div className="section-head reveal"><span className="eyebrow-tag"><i/>A clearer daily workflow</span><h2>From scattered updates to a clear next step.</h2></div>
    <div className="steps3">{[
     {n:'01',icon:ClipboardList,t:'Bring the facts together',d:'Upload logs and schedules or connect approved records, with links back to the source of every recommendation.'},
     {n:'02',icon:BlueprintIcon,t:'See what could hold up work',d:'Delivery conflicts, unanswered questions and inspection prerequisites show up beside the work they affect.'},
     {n:'03',icon:ShieldCheck,t:'Review. Approve. Move forward.',d:'Get the follow-up drafted, edit it, and approve it. Nothing leaves without you.'},
    ].map((s,i)=><article key={s.n} className="step3 reveal" style={{transitionDelay:i*90+'ms'}}><span className="step-n">{s.n}</span><span className="row-icon"><s.icon size={22}/></span><h3>{s.t}</h3><p>{s.d}</p></article>)}</div>
   </section>

   <section className="site-section" id="features">
    <div className="section-head reveal"><span className="eyebrow-tag"><i/>What’s inside</span><h2>One place for the coordination work.</h2></div>
    <div className="feature-grid">{FEATURES.map((f,i)=><article key={f.t} className="feature reveal" style={{transitionDelay:i*60+'ms'}}><span className="row-icon"><f.icon size={22}/></span><h3>{f.t}</h3><p>{f.d}</p></article>)}</div>
   </section>

   <section className="site-band reveal">
    <div><span className="eyebrow-tag light"><i/>Make it a habit</span><h2>Finish tasks. Earn XP. Build the tower.</h2><p>A daily goal, a streak and a tower that grows floor by floor. Small rewards for the follow-ups that usually slip.</p></div>
    <div className="band-chips"><span><Flame size={18}/>Day streak</span><span><Trophy size={18}/>XP and levels</span><span><BlueprintIcon size={18}/>Daily goal</span></div>
   </section>

   <section className="site-section" id="faq">
    <div className="section-head reveal"><span className="eyebrow-tag"><i/>Good questions</span><h2>Before you start.</h2></div>
    <div className="faq reveal">{FAQ.map(([q,a],i)=><div className="faq-row" key={q}><h3><button aria-expanded={faq===i} aria-controls={'faq-'+i} onClick={()=>setFaq(faq===i?null:i)}>{q}<Plus size={20} aria-hidden="true"/></button></h3>{faq===i&&<p id={'faq-'+i}>{a}</p>}</div>)}</div>
   </section>

   <section className="site-cta reveal"><h2>Ready to try it?</h2><p>Create a free account and your sample projects are waiting.</p><div className="hero-cta"><Link className="button primary big" href={cta.href}>{cta.label}<ArrowRight size={18}/></Link></div></section>
  </main>
  <footer className="site-footer"><Link href="/" className="brand"><Logo size={30}/><span>SiteSync</span></Link><span>Evidence first. People in control.</span><small>Independent product in development. No affiliation with or endorsement by Procore or Microsoft is implied.</small></footer>
 </div>;
}
