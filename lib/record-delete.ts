import {digest} from './admin-password';
import {modules} from './hr';
type Row={id:number;owner:string;kind:string;data:string;natural_key:string|null;created_at:string;updated_at:string};
export function deletionScope(rows:Row[],id:number,kind:string){
 const target=rows.find(r=>r.id===id&&r.kind===kind);if(!target||!modules[kind])throw Error('Record no longer exists. Refresh the list.');
 const parsed=rows.map(r=>({...JSON.parse(r.data),id:r.id,kind:r.kind})),byId=new Map(parsed.map(r=>[r.id,r])),edges=new Map<number,Set<number>>();
 const link=(parent:any,child:number,parentKind:string)=>{const p=byId.get(Number(parent));if(p?.kind!==parentKind)return;let children=edges.get(p.id);if(!children)edges.set(p.id,children=new Set());children.add(child);};
 const departments=new Map<string,number[]>(),attendance=new Map<string,number>();
 for(const r of parsed){if(r.kind==='departments')departments.set(r.name,[...(departments.get(r.name)||[]),r.id]);if(r.kind==='attendance')attendance.set(`${r.employee}:${r.date}`,r.id);}
 for(const r of parsed){
  if(r.employee!==undefined)link(r.employee,r.id,'employees');
  if(r.kind==='employees')for(const dep of departments.get(r.department)||[])link(dep,r.id,'departments');
  if(r.kind==='notificationReads'){const [k,id]=String(r.notificationKey||'').split(':');link(id,r.id,k);}
  if(r.kind==='announcementReads')link(r.announcementId,r.id,'announcements');
  if(r.kind==='documentRenewals')link(r.document,r.id,'documents');
  if(r.kind==='documents')for(const h of r.renewalHistory||[])link(h.renewalId,r.id,'documentRenewals');
  if(r.kind==='letters')link(r.certificateRequestId,r.id,'certificateRequests');
  if(r.kind==='certificateRequests')link(r.issuedLetterId,r.id,'letters');
  if(r.kind==='attendance')link(r.correctionRequestId,r.id,'corrections');
  if(r.kind==='corrections')link(attendance.get(`${r.employee}:${r.date}`),r.id,'attendance');
  if(r.kind==='finalSettlements'){link(r.resignation,r.id,'resignations');for(const salary of r.salaryRows||[])link(salary.id,r.id,'payroll');}
  if(r.kind==='payroll')link(r.finalSettlementId,r.id,'finalSettlements');
  if(['payroll','finalSettlements'].includes(r.kind))for(const loan of r.loanRecoveries||[])link(loan.loanId,r.id,'adjustments');
 }
 const removed=new Set([id]),queue=[id];for(let n=0;n<queue.length;n++)for(const child of edges.get(queue[n])||[])if(!removed.has(child)){removed.add(child);queue.push(child);}
 return rows.filter(r=>removed.has(r.id));
}
async function snapshot(db:any,owner:string){const rows=(await db.prepare('SELECT * FROM hr_records WHERE owner=? ORDER BY id LIMIT 10001').bind(owner).all()).results as Row[];if(rows.length>10000)throw Error('Workspace requires a larger reviewed export before deletion.');return rows;}
export async function deletionPreview(db:any,owner:string,id:number,kind:string){
 if(!Number.isSafeInteger(id)||id<1)throw Error('Invalid record.');
 const rows=await snapshot(db,owner),selected=deletionScope(rows,id,kind),revision=await digest(JSON.stringify({owner,id,kind,rows}));
 const employees=new Map(rows.filter(r=>r.kind==='employees').map(r=>[String(r.id),JSON.parse(r.data).name]));
 return {revision,count:selected.length,items:selected.map(r=>{const d=JSON.parse(r.data);return {id:r.id,kind:r.kind,module:modules[r.kind]?.title||r.kind,label:d.name||d.title||d.subject||d.type||d.month||d.date||d.notificationKey||'',employee:employees.get(String(d.employee))||'',status:d.status||''};}),financial:selected.some(r=>['payroll','finalSettlements','adjustments'].includes(r.kind)),rows,selected};
}
export async function deleteReviewedRecords(db:any,bucket:any,owner:string,id:number,kind:string,revision:string){
 const plan=await deletionPreview(db,owner,id,kind);if(plan.revision!==revision)throw Error('Records changed. Reload the deletion preview and review the updated list.');if(!bucket)throw Error('Private backup storage is unavailable. Nothing was deleted.');
 await db.prepare('CREATE TABLE IF NOT EXISTS hr_record_delete_runs(token TEXT PRIMARY KEY,owner TEXT NOT NULL,backup_key TEXT NOT NULL,completed_at TEXT NOT NULL)').run();
 const now=new Date().toISOString(),token=crypto.randomUUID(),backupKey=`record-deletion-backups/${owner}/${token}.json`;
 const employeeIds=plan.selected.filter(r=>r.kind==='employees').map(r=>r.id);
 const blockedEmployeeIds=[...new Set([...employeeIds,...plan.selected.filter(r=>r.kind==='finalSettlements'&&['Approved','Paid'].includes(JSON.parse(r.data).status)).map(r=>Number(JSON.parse(r.data).employee))])];
 const accounts=(await db.prepare('SELECT * FROM mobile_accounts WHERE owner=?').bind(owner).all()).results;
 await bucket.put(backupKey,JSON.stringify({version:1,backedUpAt:now,target:{id,kind},deletedIds:plan.selected.map(r=>r.id),records:plan.rows,mobileAccounts:accounts,filesRetained:true}),{httpMetadata:{contentType:'application/json'}});
 // Claim and every mutation share one D1 transaction. A changed workspace makes the entire operation a no-op.
 const claim=db.prepare(`INSERT INTO hr_record_delete_runs(token,owner,backup_key,completed_at) SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM hr_records WHERE owner=?)=? AND NOT EXISTS(SELECT 1 FROM json_each(?) e LEFT JOIN hr_records r ON r.owner=? AND r.id=json_extract(e.value,'$.id') WHERE r.id IS NULL OR r.kind<>json_extract(e.value,'$.kind') OR r.data<>json_extract(e.value,'$.data') OR r.created_at<>json_extract(e.value,'$.created_at') OR r.updated_at<>json_extract(e.value,'$.updated_at') OR COALESCE(r.natural_key,'')<>COALESCE(json_extract(e.value,'$.natural_key'),''))`).bind(token,owner,backupKey,now,owner,plan.rows.length,JSON.stringify(plan.rows),owner);
 const gate='EXISTS(SELECT 1 FROM hr_record_delete_runs WHERE token=? AND owner=?)',ids=JSON.stringify(plan.selected.map(r=>r.id)),employees=JSON.stringify(employeeIds),blocked=JSON.stringify(blockedEmployeeIds);
 const result=await db.batch([claim,
 db.prepare(`INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT owner,'DELETE',kind,CAST(id AS TEXT),? FROM hr_records WHERE owner=? AND id IN (SELECT value FROM json_each(?)) AND ${gate}`).bind(now,owner,ids,token,owner),
 db.prepare(`DELETE FROM mobile_sessions WHERE owner=? AND employee_id IN (SELECT value FROM json_each(?)) AND ${gate}`).bind(owner,blocked,token,owner),
 db.prepare(`UPDATE mobile_accounts SET enabled=0,updated_at=? WHERE owner=? AND employee_id IN (SELECT value FROM json_each(?)) AND ${gate}`).bind(now,owner,blocked,token,owner),
 db.prepare(`DELETE FROM mobile_accounts WHERE owner=? AND employee_id IN (SELECT value FROM json_each(?)) AND ${gate}`).bind(owner,employees,token,owner),
 db.prepare(`DELETE FROM hr_records WHERE owner=? AND id IN (SELECT value FROM json_each(?)) AND ${gate}`).bind(owner,ids,token,owner)]);
 if(!result[0].meta.changes)throw Error('Records changed while backing up. Nothing was deleted. Reload and review again.');
 return {ok:true,deletedIds:plan.selected.map(r=>r.id),backedUp:true};
}
