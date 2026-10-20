import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../../hr-auth';
import {adminRequestNotifications} from '../../../lib/admin-notifications';
import {ensureEmployeeCodes} from '../../../lib/employee-codes';
export const dynamic='force-dynamic';
export async function GET(){const user=await getChatGPTUser();const headers={'Cache-Control':'no-store'};if(!user)return Response.json({error:'Sign in to your administrator account.'},{status:401,headers});try{await ensureEmployeeCodes(env.DB!);return Response.json(await adminRequestNotifications(env.DB!,user.userId),{headers});}catch{return Response.json({error:'Could not refresh employee requests.'},{status:503,headers});}}
