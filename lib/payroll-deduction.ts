import {loanPlan} from './loan-recovery';
import {overtimeTotal} from './overtime';
import {monthlyAttendanceLedger} from './attendance-ledger';
export function attendanceDeduction(records:any[],employee:any,month:string,basic:any,allowances:any,currentDay:string){
 const row=monthlyAttendanceLedger(records,month,currentDay).rows.find(r=>String(r.employee.id)===String(employee));
 const shifts=records.filter(r=>r.kind==='shifts'&&String(r.employee)===String(employee)).sort((a,b)=>String(b.effective).localeCompare(String(a.effective))||Number(b.id)-Number(a.id));
 const days=(row?.cells||[]).filter(c=>{if(c.group!=='absent'||c.day>currentDay)return false;if(c.leave&&['Sick','Casual'].includes(c.leave.type))return false;const shift=shifts.find(s=>s.effective<=c.day),weekday=new Date(c.day+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'long',timeZone:'UTC'});return shift?.restDay!==weekday;}).length;
 const gross=Number(basic||0)+Number(allowances||0),amount=Math.round(Math.min(gross,gross/30*days)*100)/100;
 return {days,amount,dailyRate:Math.round(gross/30*100)/100};
}
export function payrollDeductionPreview(records:any[],pay:any,currentDay:string){
 const other=Number(pay.otherDeductions??pay.deductions??0),calc=attendanceDeduction(records,pay.employee,pay.month,pay.basic,pay.allowances,currentDay);
 const saved=records.find(r=>r.kind==='payroll'&&r.id===pay.id),locked=saved&&['Approved','Paid'].includes(saved.status)&&pay.status!=='Draft';
 const amount=locked?Number(saved.attendanceDeduction||0):calc.amount;
 const overtime=locked?Number(saved.overtimeAmount||0):overtimeTotal(records,pay.employee,pay.month);const additions=Math.round((Math.max(0,Number(pay.additions||0)-Number(saved?.overtimeAmount||0))+overtime)*100)/100;
 const recovery=locked?{loanRecovery:Number(saved.loanRecovery||0),loanRecoveries:saved.loanRecoveries||[]}:loanPlan(records,pay.employee,pay.month,Number(pay.basic||0)+Number(pay.allowances||0)+additions-other-amount,saved?.id);
 return {...pay,...recovery,additions,overtimeAmount:overtime,otherDeductions:other,attendanceDeduction:amount,deductions:Math.round((other+amount+recovery.loanRecovery)*100)/100,absenceDays:locked?Number(saved.absenceDays||0):calc.days};
}
