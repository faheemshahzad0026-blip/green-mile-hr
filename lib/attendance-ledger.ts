export const ledgerTotals=['Present','Leave','Absent','Off','Missing','Upcoming','N/A','Total days'];
export function monthlyAttendanceLedger(records:any[],month:string,currentDay:string){
 if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(month))return {days:[],rows:[]};
 const count=new Date(Date.UTC(Number(month.slice(0,4)),Number(month.slice(5)),0)).getUTCDate();
 const days=Array.from({length:count},(_,i)=>month+'-'+String(i+1).padStart(2,'0'));
 const linked=new Map<string,any[]>();for(const r of records){if(r.employee){const k=String(r.employee);if(!linked.has(k))linked.set(k,[]);linked.get(k)!.push(r);}}
 const rows=records.filter(e=>e.kind==='employees'&&((['Active','On leave'].includes(e.status)&&(!e.joining||e.joining<=days[count-1]))||(linked.get(String(e.id))||[]).some(r=>(r.kind==='attendance'&&r.date?.startsWith(month))||(r.kind==='leave'&&r.status==='Approved'&&r.from<=days[count-1]&&r.to>=days[0])))).map(employee=>{
 const own=linked.get(String(employee.id))||[],att=new Map<string,any>();for(const r of own.filter(r=>r.kind==='attendance').sort((a,b)=>Number(a.id)-Number(b.id)))att.set(r.date,r);
 const leaves=own.filter(r=>r.kind==='leave'&&r.status==='Approved').sort((a,b)=>Number(b.id)-Number(a.id));
 const shifts=own.filter(r=>r.kind==='shifts').sort((a,b)=>String(b.effective).localeCompare(String(a.effective))||Number(b.id)-Number(a.id));
 const totals={present:0,leave:0,absent:0,off:0,missing:0,upcoming:0,na:0,total:count};
 const cells=days.map(day=>{
 const record=att.get(day),leave=leaves.find(r=>r.from<=day&&r.to>=day),shift=shifts.find(r=>r.effective<=day);
 const weekday=new Date(day+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'long',timeZone:'UTC'});
 let code='—',label='Missing attendance',group:'present'|'leave'|'absent'|'off'|'missing'|'upcoming'|'na'='missing';
 if(employee.joining&&day<employee.joining){code='N/A';label='Before joining';group='na';}
 else if(record&&['Present','Late'].includes(record.status)){code='P';label=record.status;group='present';}
 else if(record?.status==='Absent'){code='A';label='Absent';group='absent';}
 else if(record?.status==='Rest day'){code='WO';label='Weekly off';group='off';}
 else if(leave||record?.status==='On leave'){code=leave?.type==='Sick'?'S':leave?.type==='Casual'?'C':'L';label=leave?leave.type+' leave (approved)':'On leave';group='leave';}
 else if(shift?.restDay===weekday){code='WO';label='Weekly off';group='off';}
 else if(day>currentDay){code='·';label='Upcoming';group='upcoming';}
 else if(day===currentDay){label='Not checked in';}
 totals[group]++;return {day,code,label,group,record,leave};
 });return {employee,cells,totals};
 }).sort((a,b)=>Number(a.employee.code)-Number(b.employee.code));
 return {days,rows};
}
export const ledgerValues=(r:any)=>[r.employee.code,r.employee.name,...r.cells.map((c:any)=>c.code),r.totals.present,r.totals.leave,r.totals.absent,r.totals.off,r.totals.missing,r.totals.upcoming,r.totals.na,r.totals.total];

export const ledgerDayHeader=(day:string)=>day.slice(8)+'\n'+new Date(day+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'short',timeZone:'UTC'});
