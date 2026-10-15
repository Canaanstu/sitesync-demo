import './globals.css';
import { Providers } from '../components/providers';
export const metadata = {title:'SiteSync | Construction Intelligence', description:'See the risks ahead. Connect your project information and keep work moving.'};
export default function Layout({children}:{children:React.ReactNode}) {
  return <html lang="en">
    {/* Browser extensions such as Grammarly add body attributes before hydration.
        Limit suppression to this element; application children still report mismatches. */}
    <body suppressHydrationWarning><Providers>{children}</Providers></body>
  </html>;
}
