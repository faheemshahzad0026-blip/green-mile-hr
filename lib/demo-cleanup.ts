import {digest} from './admin-password';
// One historical demo only. Future employees and production data are never eligible.
const DEMO_IDS=[1,2,3,4,5,6,8,9,10,11,12,13,14,15,17,19,21,23,24,25,26,27,29,30,31,32,33,34];
const EMPLOYEES=[{id:2,name:'Faheem'},{id:8,name:'Ali'},{id:12,name:'Muhammad'}];
const PLAN='green-mile-demo-2026-10-18';
export async function ensureCleanup(db:any){await db.prepare('CREATE TABLE IF NOT EXISTS hr_demo_cleanup_runs(owner TEXT NOT NULL,plan TEXT NOT NULL,token TEXT NOT NULL,backup_key TEXT NOT NULL,completed_at TEXT NOT NULL,PRIMARY KEY(owner,plan))').run();}
export async function demoPreview(db:any,owner:string){
 await ensureCleanup(db);
 const completed=await db.prepare('SELECT completed_at FROM hr_demo_cleanup_runs WHERE owner=? AND plan=?').bind(owner,PLAN).first();
 if(completed)return {completed:true,completedAt:completed.completed_at};
 const rows=(await db.prepare("SELECT * FROM hr_records WHERE owner=? AND kind<>'settings' ORDER BY id LIMIT 10001").bind(owner).all()).results;
 if(rows.length!==DEMO_IDS.length||rows.some((r:any,i:number)=>r.id!==DEMO_IDS[i]||r.created_at>'2026-10-18T12:11:00.000Z')||EMPLOYEES.some(e=>{const r=rows.find((r:any)=>r.id===e.id);return r?.kind!=='employees'||JSON.parse(r.data).name!==e.name;}))throw Error('The workspace has changed from the reviewed demo. Cleanup is unavailable; no records were removed.');
 const revision=await digest(JSON.stringify(rows));
 return {completed:false,revision,employees:EMPLOYEES.map(e=>e.name),count:rows.length,groups:rows.reduce((a:any,r:any)=>(a[r.kind]=(a[r.kind]||0)+1,a),{}),rows};
}
export async function cleanDemo(db:any,bucket:any,owner:string,revision:string){
 const preview=await demoPreview(db,owner);if(preview.completed)return {ok:true,alreadyCompleted:true};
 if(!revision||revision!==preview.revision)throw Error('Demo records changed. Reload the preview before cleaning.');
 if(!bucket)throw Error('Private backup storage is unavailable. Nothing was deleted.');
 const now=new Date().toISOString(),token=crypto.randomUUID(),backupKey=`demo-cleanup-backups/${owner}/${token}.json`;
 const accounts=(await db.prepare('SELECT * FROM mobile_accounts WHERE owner=? AND employee_id IN (2,8,12)').bind(owner).all()).results;
 const audit=(await db.prepare('SELECT * FROM hr_audit WHERE owner=? ORDER BY id DESC LIMIT 10001').bind(owner).all()).results;
 // Uploaded files are retained in private storage; their keys remain in this snapshot.
 await bucket.put(backupKey,JSON.stringify({version:1,reason:PLAN,backedUpAt:now,records:preview.rows,mobileAccounts:accounts,audit,filesRetained:true}),{httpMetadata:{contentType:'application/json'}});
 const expected=JSON.stringify(preview.rows);
 const claim=db.prepare(`INSERT OR IGNORE INTO hr_demo_cleanup_runs(owner,plan,token,backup_key,completed_at) SELECT ?,?,?,?,? WHERE (SELECT COUNT(*) FROM hr_records WHERE owner=? AND kind<>'settings')=? AND NOT EXISTS(SELECT 1 FROM json_each(?) e LEFT JOIN hr_records r ON r.owner=? AND r.id=json_extract(e.value,'$.id') WHERE r.id IS NULL OR r.kind<>json_extract(e.value,'$.kind') OR r.data<>json_extract(e.value,'$.data') OR r.created_at<>json_extract(e.value,'$.created_at') OR r.updated_at<>json_extract(e.value,'$.updated_at') OR COALESCE(r.natural_key,'')<>COALESCE(json_extract(e.value,'$.natural_key'),''))`).bind(owner,PLAN,token,backupKey,now,owner,DEMO_IDS.length,expected,owner);
 const guard='EXISTS(SELECT 1 FROM hr_demo_cleanup_runs WHERE owner=? AND plan=? AND token=?)';
 const stmts=[claim,
  db.prepare(`INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT owner,'DELETE',kind,CAST(id AS TEXT),? FROM hr_records WHERE owner=? AND id IN (${DEMO_IDS.join(',')}) AND ${guard}`).bind(now,owner,owner,PLAN,token),
  db.prepare(`DELETE FROM mobile_sessions WHERE owner=? AND employee_id IN (2,8,12) AND ${guard}`).bind(owner,owner,PLAN,token),
  db.prepare(`DELETE FROM mobile_accounts WHERE owner=? AND employee_id IN (2,8,12) AND ${guard}`).bind(owner,owner,PLAN,token),
  db.prepare(`DELETE FROM hr_records WHERE owner=? AND id IN (${DEMO_IDS.join(',')}) AND ${guard}`).bind(owner,owner,PLAN,token),
  db.prepare(`INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT ?,'DEMO_CLEANUP','workspace',?,? WHERE ${guard}`).bind(owner,PLAN,now,owner,PLAN,token)];
 const result=await db.batch(stmts);
 if(!result[0].meta.changes)throw Error('The demo changed or cleanup has already run. Refresh to check. No additional records were removed.');
 return {ok:true,deletedCount:DEMO_IDS.length,backedUp:true};
}
