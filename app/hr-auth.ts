import {cookies} from 'next/headers';
import {env} from 'cloudflare:workers';
import {getChatGPTUser as platformUser} from './chatgpt-auth';
import {digest,ensureAdminLogin,SESSION_COOKIE} from '../lib/admin-password';
export async function getChatGPTUser(){const user=await platformUser();if(!user)return null;if(!env.DB)throw Error("Database unavailable");await ensureAdminLogin(env.DB);const token=(await cookies()).get(SESSION_COOKIE)?.value;if(!token)return null;const session=await env.DB.prepare('SELECT owner FROM hr_admin_sessions WHERE token_hash=? AND owner=? AND expires>?').bind(await digest(token),user.userId,new Date().toISOString()).first();return session?user:null;}
export async function loginConfigured(owner:string){if(!env.DB)throw Error("Database unavailable");await ensureAdminLogin(env.DB);return !!await env.DB.prepare('SELECT owner FROM hr_admin_login WHERE owner=?').bind(owner).first();}
