// Fixed scope for this owner-private Site. Never accept owner, prefix or cutoff from a caller.
export const RETENTION_OWNER='AqZFcZ9dWqrHoW7mZTOxsOp0CdAW72kqEOhk22jopuKqa0NHD1NqyN';
export function selfieMonthCutoff(now=new Date()){
 const month=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Dubai',year:'numeric',month:'2-digit'}).formatToParts(now),year=month.find(p=>p.type==='year')!.value,mm=month.find(p=>p.type==='month')!.value;
 return {month:`${year}-${mm}`,cutoff:new Date(`${year}-${mm}-01T00:00:00+04:00`)};
}
export async function ensureSelfieRetention(db:any){
 await db.prepare('CREATE TABLE IF NOT EXISTS hr_selfie_retention(owner TEXT PRIMARY KEY,cursor TEXT,run_month TEXT,last_completed_at TEXT,last_scan_at TEXT,deleted_total INTEGER NOT NULL DEFAULT 0,lease_token TEXT,lease_until TEXT)').run();
 await db.prepare('CREATE TABLE IF NOT EXISTS hr_selfie_delete_queue(owner TEXT NOT NULL,object_key TEXT NOT NULL,PRIMARY KEY(owner,object_key))').run();
 await db.prepare('INSERT OR IGNORE INTO hr_selfie_retention(owner) VALUES(?)').bind(RETENTION_OWNER).run();
}
export async function selfieRetentionStatus(db:any){await ensureSelfieRetention(db);return await db.prepare('SELECT last_completed_at,last_scan_at,deleted_total FROM hr_selfie_retention WHERE owner=?').bind(RETENTION_OWNER).first();}
export async function cleanExpiredSelfies(db:any,bucket:any,clock=new Date()){
 if(!bucket||!db)throw Error('Private storage is unavailable.');await ensureSelfieRetention(db);
 const now=clock.toISOString(),leaseUntil=new Date(clock.getTime()+120000).toISOString(),token=crypto.randomUUID(),{month,cutoff}=selfieMonthCutoff(clock);
 const state:any=await db.prepare('UPDATE hr_selfie_retention SET lease_token=?,lease_until=? WHERE owner=? AND (lease_until IS NULL OR lease_until<?) RETURNING cursor,run_month').bind(token,leaseUntil,RETENTION_OWNER,now).first();
 if(!state)return {busy:true,hasMore:true};
 try{
  const prefix=`selfies/${RETENTION_OWNER}/`,cursor=state.run_month===month?state.cursor:null;
  const page=await bucket.list({prefix,limit:500,...(cursor?{cursor}:{})});
  const expired=page.objects.filter((o:any)=>{const uploaded=new Date(o.uploaded).getTime();return typeof o.key==='string'&&o.key.startsWith(prefix)&&/^\d+\/\d{4}-\d{2}-\d{2}\/(in|out)-[a-f0-9-]+\.jpg$/.test(o.key.slice(prefix.length))&&Number.isFinite(uploaded)&&uploaded<cutoff.getTime();}).map((o:any)=>o.key);
  if(expired.length)await db.prepare('INSERT OR IGNORE INTO hr_selfie_delete_queue(owner,object_key) SELECT ?,value FROM json_each(?)').bind(RETENTION_OWNER,JSON.stringify(expired)).run();
  const pending=(await db.prepare('SELECT object_key FROM hr_selfie_delete_queue WHERE owner=? ORDER BY object_key LIMIT 500').bind(RETENTION_OWNER).all()).results.map((r:any)=>r.object_key);
  if(pending.length){
   // Durable queue survives either object deletion or database failure. Missing objects are safe to retry.
   await bucket.delete(pending);
   const keys=JSON.stringify(pending),inKeys="json_extract(data,'$.checkInSelfie') IN (SELECT value FROM json_each(?))",outKeys="json_extract(data,'$.checkOutSelfie') IN (SELECT value FROM json_each(?))";
   await db.batch([
    db.prepare(`UPDATE hr_records SET data=json_set(CASE WHEN ${outKeys} THEN json_remove(CASE WHEN ${inKeys} THEN json_remove(data,'$.checkInSelfie') ELSE data END,'$.checkOutSelfie') ELSE CASE WHEN ${inKeys} THEN json_remove(data,'$.checkInSelfie') ELSE data END END,'$.selfiesDeletedAt',?),updated_at=? WHERE owner=? AND kind='attendance' AND (${inKeys} OR ${outKeys})`).bind(keys,keys,keys,now,now,RETENTION_OWNER,keys,keys),
    db.prepare("INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT owner,'SELFIE_RETENTION','attendance',CAST(id AS TEXT),? FROM hr_records WHERE owner=? AND kind='attendance' AND updated_at=? AND json_extract(data,'$.selfiesDeletedAt')=?").bind(now,RETENTION_OWNER,now,now),
    db.prepare('DELETE FROM hr_selfie_delete_queue WHERE owner=? AND object_key IN (SELECT value FROM json_each(?))').bind(RETENTION_OWNER,keys),
    db.prepare('UPDATE hr_selfie_retention SET deleted_total=deleted_total+? WHERE owner=? AND lease_token=?').bind(pending.length,RETENTION_OWNER,token)
   ]);
  }
  const remaining:any=await db.prepare('SELECT COUNT(*) AS n FROM hr_selfie_delete_queue WHERE owner=?').bind(RETENTION_OWNER).first();
  const hasMore=!!page.truncated||Number(remaining.n)>0;
  await db.prepare('UPDATE hr_selfie_retention SET cursor=?,run_month=?,last_scan_at=?,last_completed_at=CASE WHEN ? THEN last_completed_at ELSE ? END WHERE owner=? AND lease_token=?').bind(page.truncated?page.cursor:null,month,now,hasMore?1:0,now,RETENTION_OWNER,token).run();
  return {busy:false,month,cutoff:cutoff.toISOString(),scanned:page.objects.length,deleted:pending.length,hasMore};
 }finally{await db.prepare('UPDATE hr_selfie_retention SET lease_token=NULL,lease_until=NULL WHERE owner=? AND lease_token=?').bind(RETENTION_OWNER,token).run();}
}
