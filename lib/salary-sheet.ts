import {monthlyAttendanceLedger} from './attendance-ledger';
import {dailyAttendance} from './attendance-summary';
import {payrollNet} from './hr';
export const salaryHeaders=['Employee ID','Employee name','Department','Present','Leave','Absent','Off','Missing','Upcoming','N/A','Total days','Basic (AED)','Allowances (AED)','Additions (AED)','Deductions (AED)','Net salary (AED)','Status','Worked hours','Late minutes','Extra hours','Attendance deduction (AED)','Other deductions (AED)','Loan / advance recovery (AED)'];
export function monthlySalarySheet(records:any[],month:string,currentDay:string){
 const payroll=new Map<string,any>();for(const r of records.filter(r=>r.kind==='payroll'&&r.month===month).sort((a,b)=>Number(a.id)-Number(b.id)))payroll.set(String(r.employee),r);
 const source=records.map(r=>r.kind==='employees'&&payroll.has(String(r.id))?{...r,status:'Active'}:r);
 const ledger=monthlyAttendanceLedger(source,month,currentDay),work=new Map<string,{hours:number,late:number,extra:number}>();for(const day of ledger.days){if(day>currentDay)break;for(const r of dailyAttendance(source,day,currentDay)){const k=String(r.employee.id),v=work.get(k)||{hours:0,late:0,extra:0};v.hours+=r.hours||0;v.late+=r.lateMinutes||0;v.extra+=r.extraHours||0;work.set(k,v);}}
 return ledger.rows.map(r=>({...r,employee:records.find(e=>e.kind==='employees'&&e.id===r.employee.id)||r.employee,pay:payroll.get(String(r.employee.id)),work:work.get(String(r.employee.id))||{hours:0,late:0,extra:0}}));
}
export const salaryValues=(r:any)=>[r.employee.code,r.employee.name,r.employee.department,r.totals.present,r.totals.leave,r.totals.absent,r.totals.off,r.totals.missing,r.totals.upcoming,r.totals.na,r.totals.total,...['basic','allowances','additions','deductions'].map(k=>r.pay?Number(r.pay[k]||0):'—'),r.pay?payrollNet(r.pay):'—',r.pay?.status||'Not generated',Number(r.work.hours.toFixed(2)),r.work.late,Number(r.work.extra.toFixed(2)),r.pay?Number(r.pay.attendanceDeduction||0):'—',r.pay?Number(r.pay.otherDeductions??r.pay.deductions??0):'—',r.pay?Number(r.pay.loanRecovery||0):'—'];
