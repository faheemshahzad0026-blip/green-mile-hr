import {pinDigest,randomToken,equal} from './mobile-security';
export async function changeEmployeePIN(db:any,owner:string,employee:number,b:any,now:string,tokenHash:string){
 if(!/^\d{6}$/.test(b.oldPin||'')||!/^\d{6}$/.test(b.newPin||''))throw Error('Enter a 6-digit current and new PIN.');
 if(b.newPin!==b.confirmPin)throw Error('New PIN and confirmation do not match.');
 if(b.oldPin===b.newPin)throw Error('Choose a different new PIN.');
 const account=await db.prepare('SELECT * FROM mobile_accounts WHERE owner=? AND employee_id=? AND enabled=1').bind(owner,employee).first();if(!account)throw Error('Employee access is disabled.');
 if(account.locked_until&&account.locked_until>now)throw Error('Too many attempts. Try again after 15 minutes.');
 const actual=await pinDigest(b.oldPin,account.salt);
 if(!equal(actual,account.pin_hash)){await db.prepare("UPDATE mobile_accounts SET failed=CASE WHEN locked_until IS NOT NULL AND locked_until<=? THEN 1 ELSE failed+1 END,locked_until=CASE WHEN failed>=4 AND (locked_until IS NULL OR locked_until>?) THEN ? ELSE NULL END WHERE owner=? AND employee_id=? AND enabled=1 AND pin_hash=? AND salt=? AND (locked_until IS NULL OR locked_until<=?)").bind(now,now,new Date(Date.parse(now)+15*60000).toISOString(),owner,employee,account.pin_hash,account.salt,now).run();throw Error('Current PIN is incorrect.');}
 const salt=randomToken(),hash=await pinDigest(b.newPin,salt);
 const result=await db.batch([
 db.prepare("UPDATE mobile_accounts SET salt=?,pin_hash=?,failed=0,locked_until=NULL,updated_at=? WHERE owner=? AND employee_id=? AND enabled=1 AND pin_hash=? AND salt=? AND (locked_until IS NULL OR locked_until<=?) AND EXISTS(SELECT 1 FROM mobile_sessions WHERE owner=? AND employee_id=? AND token_hash=? AND expires>?) RETURNING employee_id").bind(salt,hash,now,owner,employee,account.pin_hash,account.salt,now,owner,employee,tokenHash,now),
 db.prepare('DELETE FROM mobile_sessions WHERE owner=? AND employee_id=? AND EXISTS(SELECT 1 FROM mobile_accounts WHERE owner=? AND employee_id=? AND salt=? AND pin_hash=? AND updated_at=?)').bind(owner,employee,owner,employee,salt,hash,now),
 db.prepare("INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT owner,'EMPLOYEE_PIN_CHANGE','employees',CAST(employee_id AS TEXT),? FROM mobile_accounts WHERE owner=? AND employee_id=? AND salt=? AND pin_hash=? AND updated_at=?").bind(now,owner,employee,salt,hash,now)
 ]);if(!result[0].results.length)throw Error('Access changed. Sign in again or ask HR to reset your PIN.');return {ok:true,signInAgain:true};
}
