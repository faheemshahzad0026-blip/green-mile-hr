import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../../hr-auth';
import {demoPreview,cleanDemo} from '../../../lib/demo-cleanup';
export const dynamic='force-dynamic';
const reply=(body:any,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
export async function GET(){const user=await getChatGPTUser();if(!user)return reply({error:'Sign in to your administrator account.'},401);try{const {rows,...preview}=await demoPreview(env.DB!,user.userId);return reply(preview);}catch(e:any){return reply({error:e.message},409);}}
export async function POST(request:Request){const user=await getChatGPTUser();if(!user)return reply({error:'Sign in to your administrator account.'},401);if(request.headers.get('Origin')!==new URL(request.url).origin)return reply({error:'Invalid request origin.'},403);try{const b:any=await request.json();if(b.action!=='clearReviewedDemo'||typeof b.revision!=='string')return reply({error:'Invalid cleanup request.'},400);return reply(await cleanDemo(env.DB!,env.BUCKET,user.userId,b.revision));}catch(e:any){return reply({error:e.message||'Cleanup failed. Refresh to check the saved state.'},409);}}
