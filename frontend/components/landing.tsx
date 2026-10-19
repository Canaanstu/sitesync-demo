'use client';
import {useState,useEffect} from 'react';
import Link from 'next/link';
import {ArrowRight,Check,ShieldCheck,Package,CalendarDays,FileText,Clock3,Mail,LoaderCircle,Plus} from 'lucide-react';
import {Logo} from './logo';
import {api} from '../lib/api';
import './landing.css';

export function Landing(){
 const [ephemeral,setEphemeral]=useState(false);
 useEffect(()=>{api('/health').then(h=>setEphemeral(!!h.ephemeral_demo)).catch(()=>{})},[]);
 const [interest,setInterest]=useState('demo'),[busy,setBusy]=useState(false),[done,setDone]=useState(false),[error,setError]=useState('');
 const [scrolled,setScrolled]=useState(false),[emailError,setEmailError]=useState(''),[consentError,setConsentError]=useState(''),[faqs,setFaqs]=useState<boolean[]>([true,false,false,false]);
 useEffect(()=>{const update=()=>setScrolled(window.scrollY>8);update();window.addEventListener('scroll',update,{passive:true});return()=>window.removeEventListener('scroll',update)},[]);
 const validateEmail=(value:string)=>!value.trim()?'Enter your company email.':/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())?'':'Enter a valid email, such as you@company.com.';
 function choose(mode:string){setInterest(mode);setDone(false);setError('');setEmailError('');setConsentError('')}
 return <div className="landing"><a className="landing-skip" href="#main">Skip to content</a><header className={'landing-nav '+(scrolled?'is-scrolled':'')}><Link className="brand" href="/" aria-label="SiteSync home"><Logo/>SiteSync</Link><nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#questions">Questions</a><Link className="landing-button dark" href="/signup">Try it now <ArrowRight size={18}/></Link></nav></header>
 <main id="main"><section className="landing-hero"><div className="hero-copy"><span className="launch-label"><span/>FREE TO TRY</span><h1>Less chasing.<br/>More building.</h1><p>Project information is everywhere.<br/>Your next step shouldn’t be.</p><p className="hero-description">SiteSync is being built to connect your project updates, flag potential delays, and help your team decide what to do next.</p><div className="landing-actions"><Link className="landing-button dark" href="/signup">Try it now <ArrowRight size={20}/></Link><Link className="landing-text-link" href="/login">Sign in</Link></div></div>
 <div className="landing-preview" aria-label="Illustrative SiteSync project preview"><div className="preview-top"><span><Logo/><b>Your next steps</b></span><small>ILLUSTRATIVE PREVIEW</small></div><div className="preview-alert"><span className="preview-chip"><Package size={16}/>Delivery conflict</span><h3>Equipment arrives after installation starts.</h3><div className="preview-dates"><span>Work starts<b>MON, OCT 19</b></span><ArrowRight size={20}/><span>Delivery expected<b>THU, OCT 22</b></span></div><p>Next step: confirm the supplier’s delivery date and review the installation sequence.</p><div className="preview-evidence"><FileText size={16}/>Schedule + supplier update</div></div><div className="preview-bottom"><ShieldCheck size={21}/><span><b>You approve the next step.</b><small>Drafts stay drafts until reviewed.</small></span><Check size={21}/></div></div></section>
 <section className="landing-tools"><p><strong>Designed to work with Procore and Microsoft 365 / Outlook. Planned connections. Availability and company authorization will be confirmed for each beta.</strong></p></section>
 <section className="landing-section" id="how-it-works"><div className="landing-section-title"><span className="landing-eyebrow">A CLEARER DAILY WORKFLOW</span><h2>From scattered updates<br/>to a clear next step.</h2><p>We’re starting with the coordination work that takes you away from the job.</p></div><div className="landing-three">{[
 {icon:FileText,n:'01',title:'Bring the facts together',text:'Connect approved project records and updates, with links back to the information behind each recommendation.'},
 {icon:CalendarDays,n:'02',title:'See what could hold up work',text:'Review delivery conflicts, unanswered questions, and inspection prerequisites alongside the work they affect.'},
 {icon:ShieldCheck,n:'03',title:'Review. Approve. Move forward.',text:'Prepare the follow-up without starting from a blank page. Your team reviews the wording and recipients before anything is sent.'}
 ].map(x=><article key={x.n}><div><x.icon size={26}/><span className="step-number">{x.n}</span></div><h3>{x.title}</h3><p>{x.text}</p><div className="step-snippet" aria-label="Illustrative workflow snippet">{x.n==='01'?<><span><FileText size={17}/>Schedule record</span><span><Mail size={17}/>Supplier update</span><small>Linked evidence</small></>:x.n==='02'?<><span className="snippet-alert"><Package size={17}/>Delivery conflict</span><span>Install Monday <ArrowRight size={16}/> Arrives Thursday</span><small>Review the affected work</small></>:<><span><FileText size={17}/>Follow-up draft</span><span><ShieldCheck size={17}/>Awaiting your review</span><small>Nothing sent automatically</small></>}</div></article>)}</div></section>
 <section className="landing-invite"><div><span className="landing-eyebrow">BUILT WITH CONTRACTORS</span><h2>Help shape what<br/>comes next.</h2></div><div><p>We’re looking for commercial construction teams to help us understand where coordination breaks down—and evaluate an early version of SiteSync when it’s ready.</p><p>Start with a conversation. Explore a focused beta on a workflow that matters to your team.</p><Link className="landing-button dark" href="/signup">Try it now <ArrowRight size={19}/></Link></div></section>
 <section className="landing-section landing-faq" id="questions"><div><span className="landing-eyebrow">GOOD QUESTIONS</span><h2>Before you sign up.</h2></div><div>{[
 ['Is SiteSync available now?','Yes. Create a free account and try it with sample projects. Your workspace is private to you; use fictional or test information while SiteSync is in beta.'],
 ['Do we need to replace Procore?','Our approach is to work with the tools your team already uses. Planned connections and supported data will be confirmed before beta onboarding.'],
 ['Will it send emails or make decisions for us?','SiteSync is designed to prepare recommendations and drafts. Your team reviews and approves before anything is sent.'],
 ['Does signing up commit us to a purchase?','No. Any beta scope, pricing, permissions, and data-handling terms would be agreed separately before participation.']
 ].map(([q,a],i)=><div className="faq-item" key={q}><h3><button type="button" id={'faq-question-'+i} aria-expanded={faqs[i]} aria-controls={'faq-answer-'+i} onClick={()=>setFaqs(f=>f.map((v,n)=>n===i?!v:v))}>{q}<Plus size={19} aria-hidden="true"/></button></h3><div id={'faq-answer-'+i} role="region" aria-labelledby={'faq-question-'+i} hidden={!faqs[i]}><p>{a}</p></div></div>)}</div></section>
</main>
 <footer className="landing-footer"><Link className="brand" href="/"><Logo/>SiteSync</Link><span>Evidence first. People in control.</span><small>Independent product in development. No affiliation with or endorsement by Procore or Microsoft is implied.</small></footer></div>;
}

