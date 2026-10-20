import {today} from './hr';
import {prepareEmployeeLetter} from './employee-letters';
export const certificateTypes=['Salary certificate','Employment certificate','NOC'];
export async function requestCertificate(db:any,owner:string,employee:any,b:any,date:string,now:string){
 const type=String(b.type||''),purpose=String(b.purpose||'').trim(),recipient=String(b.recipient||'To whom it may concern').trim();
 if(!certificateTypes.includes(type))throw Error('Choose a supported certificate type.');if(!purpose||purpose.length>1000)throw Error('Enter a purpose of up to 1000 characters.');if(!recipient||recipient.length>300)throw Error('Enter a recipient of up to 300 characters.');
 const key='certificate:'+employee+':'+type;const d={employee:String(employee),type,date,recipient,purpose,status:'Pending',reviewNote:'',body:'',signatory:'',signatoryTitle:''};
 const rows=await db.batch([db.prepare("INSERT INTO hr_records(owner,kind,data,natural_key,created_at,updated_at) SELECT ?,'certificateRequests',?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM hr_records WHERE owner=? AND kind='certificateRequests' AND json_extract(data,'$.employee')=? AND json_extract(data,'$.type')=? AND json_extract(data,'$.status')='Pending') RETURNING id").bind(owner,JSON.stringify(d),null,now,now,owner,String(employee),type),db.prepare("INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT ?,'REQUEST','certificateRequests',CAST(last_insert_rowid() AS TEXT),? WHERE changes()>0").bind(owner,now)]);
 if(!rows[0].results.length)throw Error('A pending request of this type already exists.');return {ok:true,status:'Pending',id:rows[0].results[0].id};
}
export async function reviewCertificate(db:any,bucket:any,owner:string,id:number,input:any,now:string){
 const raw:any=await db.prepare("SELECT * FROM hr_records WHERE owner=? AND kind='certificateRequests' AND id=?").bind(owner,id).first();if(!raw)throw Error('Request no longer exists.');const previous=JSON.parse(raw.data);if(previous.status!=='Pending')throw Error('Reviewed certificate requests are locked.');
 for(const key of ['employee','type','date','recipient','purpose'])if(String(input[key]||'')!==String(previous[key]||''))throw Error('Employee request details cannot be changed during review.');
 if(!['Pending','Rejected','Issued'].includes(input.status))throw Error('Invalid review status.');
 const reviewed={...previous,...Object.fromEntries(['status','reviewNote','body','signatory','signatoryTitle'].map(k=>[k,String(input[k]||'')])),...(input.status!=='Pending'?{reviewedAt:now}:{})};
 let letter:any=null;if(input.status==='Issued'){
  const employee:any=await db.prepare("SELECT r.data,c.code FROM hr_records r JOIN employee_code_registry c ON c.employee_id=r.id WHERE r.owner=? AND r.kind='employees' AND r.id=?").bind(owner,Number(previous.employee)).first();if(!employee)throw Error('Employee details are unavailable.');
  letter=prepareEmployeeLetter({...previous,date:today(),type:previous.type,body:reviewed.body,signatory:reviewed.signatory,signatoryTitle:reviewed.signatoryTitle,certificateRequestId:id,issuedAt:now}, {...JSON.parse(employee.data),code:String(employee.code)});
 }
 if(!bucket)throw Error('Private backup storage is required before reviewing a request.');await bucket.put('certificate-request-backups/'+owner+'/'+id+'/'+crypto.randomUUID()+'.json',JSON.stringify(raw));
 const naturalKey='certificate-request:'+id,stmts:any[]=[];
 if(letter)stmts.push(db.prepare("INSERT INTO hr_records(owner,kind,data,natural_key,created_at,updated_at) SELECT ?,'letters',?,?,?,? FROM hr_records WHERE owner=? AND kind='certificateRequests' AND id=? AND data=? RETURNING id").bind(owner,JSON.stringify(letter),naturalKey,now,now,owner,id,raw.data));
 stmts.push(db.prepare("UPDATE hr_records SET data="+(letter?"json_set(?, '$.issuedLetterId', (SELECT id FROM hr_records WHERE owner=? AND kind='letters' AND natural_key=?))":"?")+",updated_at=? WHERE owner=? AND kind='certificateRequests' AND id=? AND data=? RETURNING id").bind(JSON.stringify(reviewed),...(letter?[owner,naturalKey]:[]),now,owner,id,raw.data));
 stmts.push(db.prepare("INSERT INTO hr_audit(owner,action,kind,record_id,at) SELECT ?,?,'certificateRequests',?,? WHERE changes()>0").bind(owner,input.status==='Issued'?'ISSUE':input.status==='Rejected'?'REJECT':'UPDATE',String(id),now));
 const result=await db.batch(stmts);if(!result[letter?1:0].results.length)throw Error('Request changed. Refresh and retry.');
 return (await db.prepare("SELECT * FROM hr_records WHERE owner=? AND (id=? OR (kind='letters' AND natural_key=?))").bind(owner,id,naturalKey).all()).results;
}
export async function ownCertificate(db:any,owner:string,employee:any,id:number){
 const request:any=await db.prepare("SELECT data FROM hr_records WHERE owner=? AND kind='certificateRequests' AND id=? AND CAST(json_extract(data,'$.employee') AS TEXT)=? AND json_extract(data,'$.status')='Issued'").bind(owner,id,String(employee)).first();if(!request)throw Error('Issued certificate is unavailable.');
 const d=JSON.parse(request.data);const letter:any=await db.prepare("SELECT id,data FROM hr_records WHERE owner=? AND kind='letters' AND id=? AND CAST(json_extract(data,'$.employee') AS TEXT)=? AND json_extract(data,'$.certificateRequestId')=?").bind(owner,Number(d.issuedLetterId),String(employee),id).first();if(!letter)throw Error('Issued certificate is unavailable.');const setting:any=await db.prepare("SELECT data FROM hr_records WHERE owner=? AND kind='settings' LIMIT 1").bind(owner).first();const c=setting?JSON.parse(setting.data):{},l=JSON.parse(letter.data);
 return {letter:{id:letter.id,...Object.fromEntries(['type','date','recipient','purpose','body','employeeCode','employeeName','signatory','signatoryTitle'].map(k=>[k,l[k]||'']))},company:{name:'Green Mile Recycling LLC',location:c.location||'',phone:c.phone||'',email:c.email||''}};
}
