import { Workspace } from '../../components/workspace';
import { Landing } from '../../components/landing';
export default async function Page({params}:{params:Promise<{route?:string[]}>}) { const {route}=await params; return !route?.length||route[0]==='launch'?<Landing/>:<Workspace/> }
