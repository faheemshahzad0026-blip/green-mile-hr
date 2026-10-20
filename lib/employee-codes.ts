// Public employee numbers are independent of internal HR record IDs.
// Registry entries survive employee deletion so numbers are never reused.
let ready:Promise<void>|null=null;
export async function ensureEmployeeCodes(db:any){if(!ready){ready=(async()=>{
 await db.prepare('CREATE TABLE IF NOT EXISTS employee_code_registry(employee_id INTEGER PRIMARY KEY,code INTEGER NOT NULL UNIQUE)').run();
 await db.prepare("INSERT INTO employee_code_registry(employee_id,code) SELECT id,(SELECT COALESCE(MAX(code)+1,10000) FROM employee_code_registry)+ROW_NUMBER() OVER(ORDER BY id)-1 FROM hr_records WHERE kind='employees' AND id NOT IN (SELECT employee_id FROM employee_code_registry) ORDER BY id").run();
 })().catch(e=>{ready=null;throw e});}await ready;}
export async function employeeCodesFor(db:any){await ensureEmployeeCodes(db);const rows=await db.prepare('SELECT employee_id,code FROM employee_code_registry').all();return new Map<number,string>(rows.results.map((r:any)=>[Number(r.employee_id),String(r.code)]));}
export function allocateEmployeeCode(db:any,owner:string){return db.prepare("INSERT INTO employee_code_registry(employee_id,code) SELECT id,(SELECT COALESCE(MAX(code)+1,10000) FROM employee_code_registry) FROM hr_records WHERE owner=? AND kind='employees' ORDER BY id DESC LIMIT 1 RETURNING code").bind(owner);}
