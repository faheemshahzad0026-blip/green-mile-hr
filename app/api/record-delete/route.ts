import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../../hr-auth';
import {deletionPreview,deleteReviewedRecords} from '../../../lib/record-delete';
export const dynamic='force-dynamic';
const reply=(body:any,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
export async function GET(request:Request){const user=await getChatGPTUser();if(!user)return reply({error:'Sign in to your administrator account.'},401);try{const p=new URL(request.url).searchParams,{rows,selected,...preview}=await deletionPreview(env.DB!,user.userId,Number(p.get('id')),p.get('kind')||'');return reply(preview);}catch(e:any){return reply({error:e.message},409);}}
export async function POST(request:Request){const user=await getChatGPTUser();if(!user)return reply({error:'Sign in to your administrator account.'},401);if(request.headers.get('Origin')!==new URL(request.url).origin)return reply({error:'Invalid request origin.'},403);try{const b:any=await request.json();if(b.confirm!==true||typeof b.revision!=='string'||typeof b.kind!=='string')return reply({error:'Review and confirm the deletion first.'},400);return reply(await deleteReviewedRecords(env.DB!,env.BUCKET,user.userId,Number(b.id),b.kind,b.revision));}catch(e:any){return reply({error:e.message||'Could not delete records. Refresh to check the saved state.'},409);}}
