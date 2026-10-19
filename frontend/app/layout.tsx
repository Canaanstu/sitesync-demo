import './globals.css';
import './app.css';
import { Providers } from '../components/providers';
export const metadata = {title:'SiteSync | Construction Intelligence', description:'See the risks ahead. Connect your project information and keep work moving.'};
export default function Layout({children}:{children:React.ReactNode}) {
  return <html lang="en" suppressHydrationWarning>
    <head>
      <script dangerouslySetInnerHTML={{__html:"try{var t=localStorage.getItem('sitesync:theme')||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');document.documentElement.dataset.theme=t}catch(e){}"}}/>
      <script dangerouslySetInnerHTML={{__html:"try{if(sessionStorage.getItem('sitesync:splash'))document.documentElement.classList.add('seen-splash')}catch(e){}"}}/>
      <link rel="preconnect" href="https://fonts.googleapis.com"/>
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin=""/>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap"/>
    </head>
    {/* Browser extensions such as Grammarly add body attributes before hydration.
        Limit suppression to this element; application children still report mismatches. */}
    <body suppressHydrationWarning><Providers>{children}</Providers></body>
  </html>;
}
