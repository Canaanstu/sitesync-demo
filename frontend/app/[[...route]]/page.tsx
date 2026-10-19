import { Workspace } from '../../components/workspace';
import { Landing } from '../../components/landing';
import demo from '../../lib/demo-data.json';

// The static GitHub Pages build must list every route up front. Normal builds render on demand.
export async function generateStaticParams() {
  if (process.env.NEXT_PUBLIC_STATIC_DEMO !== 'true') return [];
  const ids = (demo['GET /projects'] as { id: string }[]).map(p => p.id);
  const sections = ['schedule', 'procurement', 'rfi', 'agents', 'more', 'records', 'documents', 'settings', 'ai', 'risks'];
  return [
    { route: [] }, { route: ['launch'] },
    ...['login', 'dashboard', 'projects', 'integrations', 'settings', 'tutorial'].map(r => ({ route: [r] })),
    ...ids.flatMap(id => [{ route: ['projects', id] }, ...sections.map(s => ({ route: ['projects', id, s] }))]),
  ];
}
export default async function Page({params}:{params:Promise<{route?:string[]}>}) { const {route}=await params; return !route?.length||route[0]==='launch'?<Landing/>:<Workspace/> }
