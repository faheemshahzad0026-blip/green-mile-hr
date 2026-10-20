import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../../hr-auth';
import {getChatGPTUser as platformUser} from '../../chatgpt-auth';
import {RETENTION_OWNER,selfieRetentionStatus,cleanExpiredSelfies} from '../../../lib/selfie-retention';
export const dynamic='force-dynamic';
const reply=(body:any,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
export async function GET(){const user=await getChatGPTUser();if(!user||user.userId!==RETENTION_OWNER)return reply({error:'Sign in to your administrator account.'},401);return reply({policy:'Previous-month attendance selfies only',timezone:'Asia/Dubai',...await selfieRetentionStatus(env.DB!)});}
// Unattended writer: the confirmed owner-private Site boundary authenticates service callers.
// No arbitrary deletion controls are accepted. Before changing Site sharing, replace this with explicit service authorization.
export async function POST(request:Request){
 const user=await platformUser();if(user&&user.userId!==RETENTION_OWNER)return reply({error:'Not authorized.'},403);
 const origin=request.headers.get('Origin');if(origin&&origin!==new URL(request.url).origin)return reply({error:'Invalid request origin.'},403);
 try{const b:any=await request.json();if(b.action!=='monthlySelfieCleanup'||Object.keys(b).some(k=>k!=='action'))return reply({error:'Invalid maintenance request.'},400);return reply(await cleanExpiredSelfies(env.DB!,env.BUCKET));}catch{return reply({error:'Selfie cleanup could not finish. Retry; the deletion queue is preserved.'},500);}
}
