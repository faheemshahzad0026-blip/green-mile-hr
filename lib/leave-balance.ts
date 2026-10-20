// Company-configured annual entitlement, renewed on each joining anniversary.
const dayMs=86400000;
function date(s:string){if(!/^\d{4}-\d{2}-\d{2}$/.test(s))return NaN;const n=Date.parse(s+'T00:00:00Z');return Number.isFinite(n)&&new Date(n).toISOString().slice(0,10)===s?n:NaN;}
function anniversary(joining:string,year:number){const m=Number(joining.slice(5,7)),d=Number(joining.slice(8));return new Date(Date.UTC(year,m-1,Math.min(d,new Date(Date.UTC(year,m,0)).getUTCDate()))).toISOString().slice(0,10);}
export function annualLeaveBalance(employee:any,leaves:any[],allowance:any,currentDay:string){
 const joining=String(employee.joining||'');if(!Number.isFinite(date(joining))||joining>currentDay)return {available:false,message:'A valid joining date is required before this cycle starts.'};
 let year=Number(currentDay.slice(0,4));if(anniversary(joining,year)>currentDay)year--;
 const start=anniversary(joining,year),next=anniversary(joining,year+1),end=new Date(date(next)-dayMs).toISOString().slice(0,10);
 const total=allowance===''||allowance==null?30:Number(allowance);if(!Number.isFinite(total)||total<0)return {available:false,message:'HR must configure a valid annual leave allowance.'};
 const used=new Set<string>(),booked=new Set<string>(),pending=new Set<string>();
 for(const l of leaves){if(String(l.employee)!==String(employee.id)||l.type!=='Annual'||!['Approved','Pending'].includes(l.status)||!Number.isFinite(date(l.from))||!Number.isFinite(date(l.to))||l.to<l.from)continue;
 const from=l.from>start?l.from:start,to=l.to<end?l.to:end;
 for(let n=date(from);n<=date(to);n+=dayMs){const d=new Date(n).toISOString().slice(0,10);(l.status==='Pending'?pending:d<=currentDay?used:booked).add(d);}}
 const committed=used.size+booked.size;
 return {available:true,start,end,total,used:used.size,booked:booked.size,pending:pending.size,remaining:Math.max(0,total-committed),overdrawn:Math.max(0,committed-total)};
}
