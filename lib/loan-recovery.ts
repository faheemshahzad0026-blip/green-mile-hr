const cents=(v:any)=>Math.round(Number(v||0)*100);
export const isLoan=(r:any)=>['Loan','Advance'].includes(r?.type);
export function loanBalance(records:any[],loan:any,excludePayroll?:any){
 let paid=0,reserved=0;
 for(const p of records){if(!['payroll','finalSettlements'].includes(p.kind)||String(p.employee)!==String(loan.employee)||String(p.id)===String(excludePayroll)||!['Approved','Paid'].includes(p.status))continue;
  for(const a of Array.isArray(p.loanRecoveries)?p.loanRecoveries:[]){if(String(a.loanId)!==String(loan.id))continue;if(p.status==='Paid')paid+=cents(a.amount);else reserved+=cents(a.amount);}
 }
 const principal=cents(loan.amount);return {recovered:paid/100,reservedRecovery:reserved/100,remainingBalance:Math.max(0,principal-paid)/100,availableBalance:Math.max(0,principal-paid-reserved)/100};
}
export function loanPlan(records:any[],employee:any,month:string,available:any,excludePayroll?:any){
 let budget=Math.max(0,cents(available));const allocations:any[]=[];
 const loans=records.filter(r=>r.kind==='adjustments'&&isLoan(r)&&String(r.employee)===String(employee)&&r.status==='Approved'&&Number(r.monthlyInstallment)>0&&/^\d{4}-(0[1-9]|1[0-2])$/.test(r.recoveryStart||'')&&r.recoveryStart<=month&&String(r.date).slice(0,7)<=month).sort((a,b)=>String(a.date).localeCompare(String(b.date))||Number(a.id)-Number(b.id));
 for(const loan of loans){const balance=loanBalance(records,loan,excludePayroll);const amount=Math.min(budget,cents(loan.monthlyInstallment),cents(balance.availableBalance));if(amount<=0)continue;allocations.push({loanId:loan.id,type:loan.type,amount:amount/100,principal:Number(loan.amount),installment:Number(loan.monthlyInstallment),remainingAfter:Math.round((balance.availableBalance-amount/100)*100)/100});budget-=amount;}
 return {loanRecoveries:allocations,loanRecovery:allocations.reduce((n,a)=>n+cents(a.amount),0)/100};
}
export function validateLoan(d:any,previous:any,records:any[]){
 if(previous&&isLoan(previous)&&d.employee!==previous.employee)throw Error('Existing loan employee is locked. Create a separate loan for another employee.');
 const linked=previous&&records.some(p=>['payroll','finalSettlements'].includes(p.kind)&&String(p.employee)===String(previous.employee)&&(p.loanRecoveries||[]).some((a:any)=>String(a.loanId)===String(previous.id)));
 if(linked&&(!isLoan(d)||d.employee!==previous.employee||d.type!==previous.type||d.date!==previous.date||Number(d.amount)!==Number(previous.amount)||d.recoveryStart!==previous.recoveryStart))throw Error('This loan has payroll history. Its employee, type, principal and start date are locked.');
 if(!isLoan(d))return d;
 if(linked&&d.status==='Pending')throw Error('A loan with payroll history cannot return to Pending.');
 const legacy=previous&&isLoan(previous)&&!previous.recoveryStart&&!Number(previous.monthlyInstallment)&&!d.recoveryStart&&!Number(d.monthlyInstallment);
 if(legacy)return d;
 if(d.status==='Settled'&&loanBalance(records,previous||d).remainingBalance>0)throw Error('Mark salary Paid to record recovery. This loan still has an outstanding balance.');

 if(!legacy){if(!(Number(d.amount)>0)||!(Number(d.monthlyInstallment)>0))throw Error('Enter a positive loan amount and monthly installment.');if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(d.recoveryStart||''))throw Error('Select the first recovery month.');if(d.recoveryStart<String(d.date).slice(0,7))throw Error('Recovery cannot start before the loan date.');}
 return d;
}
// The same employee's payroll/adjustments must not change between calculation and write.
export const recoverySignatureSQL="SELECT COALESCE(group_concat(id || ':' || data,'|'),'') AS signature FROM (SELECT id,data FROM hr_records WHERE owner=? AND kind IN ('payroll','adjustments','finalSettlements') AND CAST(json_extract(data,'$.employee') AS TEXT)=? ORDER BY id)";
export async function recoverySnapshot(db:any,owner:string,employee:any){const rows=await db.prepare("SELECT id,kind,data FROM hr_records WHERE owner=? AND kind IN ('payroll','adjustments','finalSettlements') AND CAST(json_extract(data,'$.employee') AS TEXT)=? ORDER BY id").bind(owner,String(employee)).all();return {raws:rows.results,records:rows.results.map((r:any)=>({id:r.id,kind:r.kind,...JSON.parse(r.data)})),signature:rows.results.map((r:any)=>r.id+':'+r.data).join('|')};}
