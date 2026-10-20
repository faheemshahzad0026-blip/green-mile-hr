import {allocateEmployeeCode} from './employee-codes';
export const onboardingDocumentTypes=['Emirates ID','Passport','Insurance'];
export function prepareInitialDocuments(input:any,clean:(kind:string,data:any)=>any,date:string){
 if(input===undefined)return [];if(!Array.isArray(input)||input.length>3)throw Error('Add at most one Emirates ID, passport and health insurance record.');const seen=new Set<string>();
 return input.map((raw:any)=>{if(!raw||!onboardingDocumentTypes.includes(raw.type)||seen.has(raw.type))throw Error('Choose each initial document type only once.');seen.add(raw.type);
 const d=clean('documents',{...raw,employee:'pending',status:raw.expiry<date?'Expired':'Valid',reminderDays:30});if(raw.type==='Insurance'&&!d.provider)throw Error('Health insurance provider is required.');return d;});
}
export async function saveNewEmployee(db:any,bucket:any,owner:string,data:any,documents:any[],now:string){
 if(!bucket)throw Error('Private backup storage is required before adding an employee.');
 const prior=(await db.prepare('SELECT * FROM hr_records WHERE owner=? ORDER BY id LIMIT 10001').bind(owner).all()).results;if(prior.length>10000)throw Error('Workspace exceeds the current backup limit.');
 await bucket.put(`employee-onboarding-backups/${owner}/${crypto.randomUUID()}.json`,JSON.stringify({version:1,backedUpAt:now,records:prior}),{httpMetadata:{contentType:'application/json'}});
 const statements=[db.prepare("INSERT INTO hr_records(owner,kind,data,created_at,updated_at) VALUES(?,'employees',?,?,?) RETURNING *").bind(owner,JSON.stringify(data),now,now),allocateEmployeeCode(db,owner),db.prepare("INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT owner,'CREATE','employees',CAST(id AS TEXT),? FROM hr_records WHERE owner=? AND kind='employees' ORDER BY id DESC LIMIT 1").bind(now,owner)];
 for(const doc of documents){statements.push(db.prepare("INSERT INTO hr_records(owner,kind,data,created_at,updated_at) SELECT ?,'documents',json_set(?,'$.employee',CAST(id AS TEXT)),?,? FROM hr_records WHERE owner=? AND kind='employees' ORDER BY id DESC LIMIT 1 RETURNING *").bind(owner,JSON.stringify(doc),now,now,owner));statements.push(db.prepare("INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT owner,'CREATE','documents',CAST(id AS TEXT),? FROM hr_records WHERE owner=? AND kind='documents' ORDER BY id DESC LIMIT 1").bind(now,owner));}
 // Employee, public number and linked documents commit together, or all roll back.
 const results=await db.batch(statements),employee=results[0].results[0],rows=[employee,...documents.map((_,i)=>results[3+i*2].results[0])];
 return {rows,employeeId:Number(employee.id),code:String(results[1].results[0].code)};
}
