import {env} from 'cloudflare:workers';
import {getChatGPTUser} from '../../chatgpt-auth';
import {digest,ensureAdminLogin,passwordHash,sameHash,SESSION_COOKIE,validPassword,validUsername} from '../../../lib/admin-password';
const json=(body:any,status=200,cookie?:string)=>Response.json(body,{status,headers:{'Cache-Control':'no-store',...(cookie?{'Set-Cookie':cookie}:{})}});
function requestToken(request:Request){return request.headers.get('Cookie')?.split(';').map(x=>x.trim()).find(x=>x.startsWith(SESSION_COOKIE+'='))?.slice(SESSION_COOKIE.length+1);}
async function validSession(db:any,request:Request,owner:string){const token=requestToken(request);return token?await db.prepare('SELECT owner FROM hr_admin_sessions WHERE token_hash=? AND owner=? AND expires>?').bind(await digest(token),owner,new Date().toISOString()).first():null;}
const cookieFor=(token:string)=>`${SESSION_COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800`;
async function failedAttempt(db:any,owner:string){const now=new Date().toISOString();await db.prepare("UPDATE hr_admin_login SET failed=CASE WHEN locked_until<=? THEN 1 ELSE failed+1 END,locked_until=CASE WHEN (CASE WHEN locked_until<=? THEN 0 ELSE failed END)+1>=5 THEN ? ELSE NULL END WHERE owner=?").bind(now,now,new Date(Date.now()+15*60*1000).toISOString(),owner).run();}
export async function GET(request:Request){const user=await getChatGPTUser();if(!user)return json({error:'Please sign in.'},401);try{const db=env.DB;if(!db)throw Error('Database unavailable');await ensureAdminLogin(db);if(!await validSession(db,request,user.userId))return json({error:'Please sign in again.'},401);const account:any=await db.prepare('SELECT username FROM hr_admin_login WHERE owner=?').bind(user.userId).first();return json({username:account?.username||''});}catch{return json({error:'Could not load login settings.'},500);}}
export async function POST(request:Request){
 const user=await getChatGPTUser();if(!user)return json({error:'Please sign in with ChatGPT.'},401);
 const origin=request.headers.get('Origin');if(!origin||origin!==new URL(request.url).origin)return json({error:'Invalid request origin.'},403);
 try{
  const db=env.DB;if(!db)throw Error('Database unavailable');await ensureAdminLogin(db);const body:any=await request.json();
  if(body.action==='logout'){const token=requestToken(request);if(token)await db.prepare('DELETE FROM hr_admin_sessions WHERE token_hash=? AND owner=?').bind(await digest(token),user.userId).run();return json({ok:true},200,`${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`);}
  if(!['setup','login','change','recover'].includes(body.action))return json({error:'Invalid action.'},400);
  const username=String(body.username||'').trim(),password=String(body.password||'');
  if(!validUsername(username)||!validPassword(password))return json({error:'Enter a valid username and a password (up to 128 characters).'},400);
  const account:any=await db.prepare('SELECT * FROM hr_admin_login WHERE owner=?').bind(user.userId).first();
  if(body.action==='change'||body.action==='recover'){
   if(body.action==='change'&&!await validSession(db,request,user.userId))return json({error:'Your session expired. Sign in again.'},401);
   if(body.action==='recover'&&body.confirmRecovery!==true)return json({error:'Confirm recovery using your signed-in ChatGPT account.'},400);
   if(!account)return json({error:'Login is not configured.'},409);
   if(body.action==='change'){
   if(account.locked_until&&account.locked_until>new Date().toISOString())return json({error:'Too many attempts. Try again in 15 minutes.'},429);
   const currentPassword=String(body.currentPassword||'');if(!validPassword(currentPassword))return json({error:'Enter your current password.'},400);
   if(!sameHash(await passwordHash(currentPassword,account.salt),account.password_hash)){await failedAttempt(db,user.userId);return json({error:'Current password is incorrect.'},400);}
   }
   const salt=crypto.randomUUID(),hash=await passwordHash(password,salt),token=crypto.randomUUID()+crypto.randomUUID(),expires=new Date(Date.now()+8*60*60*1000).toISOString();
   const updated=await db.batch([
    db.prepare('UPDATE hr_admin_login SET username=?,salt=?,password_hash=?,failed=0,locked_until=NULL WHERE owner=? AND salt=? AND password_hash=? RETURNING owner').bind(username,salt,hash,user.userId,account.salt,account.password_hash),
    db.prepare('DELETE FROM hr_admin_sessions WHERE owner=? AND EXISTS(SELECT 1 FROM hr_admin_login WHERE owner=? AND salt=?)').bind(user.userId,user.userId,salt),
    db.prepare('INSERT INTO hr_admin_sessions(token_hash,owner,expires) SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM hr_admin_login WHERE owner=? AND salt=?)').bind(await digest(token),user.userId,expires,user.userId,salt)
   ]);
   if(!updated[0].results.length)return json({error:'Login settings changed in another window. Sign in again and retry.'},409);
   return json({ok:true,username},200,cookieFor(token));
  }
  if(body.action==='setup'){
   if(account)return json({error:'Login is already configured. Refresh this page and sign in.'},409);
   const salt=crypto.randomUUID();const result=await db.prepare('INSERT INTO hr_admin_login(owner,username,salt,password_hash) VALUES(?,?,?,?) ON CONFLICT(owner) DO NOTHING').bind(user.userId,username,salt,await passwordHash(password,salt)).run();
   if(!result.meta.changes)return json({error:'Login was already configured. Refresh and sign in.'},409);
  }else{
   if(!account)return json({error:'Refresh this page to set up your login.'},409);
   if(account.locked_until&&account.locked_until>new Date().toISOString())return json({error:'Too many attempts. Try again in 15 minutes.'},429);
   if(username!==account.username||!sameHash(await passwordHash(password,account.salt),account.password_hash)){await failedAttempt(db,user.userId);return json({error:'Incorrect username or password.'},401);}
   await db.prepare('UPDATE hr_admin_login SET failed=0,locked_until=NULL WHERE owner=?').bind(user.userId).run();
  }
  const token=crypto.randomUUID()+crypto.randomUUID();await db.batch([db.prepare('DELETE FROM hr_admin_sessions WHERE owner=? AND expires<=?').bind(user.userId,new Date().toISOString()),db.prepare('INSERT INTO hr_admin_sessions(token_hash,owner,expires) VALUES(?,?,?)').bind(await digest(token),user.userId,new Date(Date.now()+8*60*60*1000).toISOString())]);
  return json({ok:true},200,cookieFor(token));
 }catch{return json({error:'Could not complete your request. Please retry.'},500);}
}
