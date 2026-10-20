import {attendanceHours,nextDay} from './attendance';
export function dailyAttendance(records:any[],day:string,currentDay:string){
 const byEmployee=new Map<string,any[]>();for(const r of records){if(r.employee){const key=String(r.employee);if(!byEmployee.has(key))byEmployee.set(key,[]);byEmployee.get(key)!.push(r);}}
 const weekday=new Date(day+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'long',timeZone:'UTC'});
 return records.filter(e=>e.kind==='employees'&&['Active','On leave'].includes(e.status)&&(!e.joining||e.joining<=day)).map(e=>{
 const linked=byEmployee.get(String(e.id))||[],record=linked.find(r=>r.kind==='attendance'&&r.date===day),shift=linked.filter(r=>r.kind==='shifts'&&r.effective<=day).sort((a,b)=>b.effective.localeCompare(a.effective)||b.id-a.id)[0],leave=linked.find(r=>r.kind==='leave'&&r.status==='Approved'&&r.from<=day&&r.to>=day),night=linked.find(r=>r.kind==='attendance'&&r.timeIn&&!r.timeOut&&nextDay(r.date)===day);
 let status=record?.status|| (leave?'On leave':shift?.restDay===weekday?'Rest day':night?'Open night shift':day<currentDay?'Missing attendance':day===currentDay?'Not checked in':'Upcoming');
 let lateMinutes:number|null=null,extraHours:number|null=null;const hours=record?attendanceHours(record):null;
 if(record?.timeIn&&shift?.start&&status!=='Absent'&&status!=='Rest day'&&status!=='On leave'){const mins=(v:string)=>Number(v.slice(0,2))*60+Number(v.slice(3));lateMinutes=Math.max(0,mins(record.timeIn)-mins(shift.start));if(lateMinutes>0&&status==='Present')status='Late';if(hours!==null&&shift.end){let scheduled=mins(shift.end)-mins(shift.start);if(scheduled<=0)scheduled+=1440;const breakHours=Number(shift.breakMinutes||0)/60;extraHours=Math.max(0,Math.max(0,hours-breakHours)-Math.max(0,scheduled/60-breakHours));}}
 return {employee:e,record,shift,status,lateMinutes,hours,extraHours};
 });
}
