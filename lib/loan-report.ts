import {isLoan} from './loan-recovery';
import {fmtDate,money,today} from './hr';
export const loanHeaders=['Loan ID','Employee ID','Employee name','Department','Type','Loan date','Principal (AED)','Monthly installment (AED)','Recovered (AED)','Reserved (AED)','Outstanding (AED)','Status'];
export const recoveryHeaders=['Loan ID','Employee ID','Employee name','Salary month','Payroll status','Recovery (AED)','Payment date','Reference'];
const cents=(v:any)=>Math.round(Number(v||0)*100);
export function loanReport(records:any[],filters:{employee?:string,department?:string,type?:string,status?:string,month?:string}={}){
 const employees=new Map(records.filter(r=>r.kind==='employees').map(r=>[String(r.id),r]));
 const linked=new Map<string,any[]>();
 for(let payroll of records){if(!['payroll','finalSettlements'].includes(payroll.kind))continue;if(payroll.kind==='finalSettlements')payroll={...payroll,month:String(payroll.lastDay).slice(0,7),reference:payroll.paymentReference};for(const allocation of Array.isArray(payroll.loanRecoveries)?payroll.loanRecoveries:[]){const key=String(payroll.employee)+':'+allocation.loanId;const items=linked.get(key)||[];items.push({payroll,amount:Number(allocation.amount||0)});linked.set(key,items);}}
 const loans=records.filter(r=>r.kind==='adjustments'&&isLoan(r)).map(loan=>{
  const employee=employees.get(String(loan.employee))||{code:'—',name:'Unknown employee',department:''};
  const history=linked.get(String(loan.employee)+':'+loan.id)||[];
  const recovered=history.filter(h=>h.payroll.status==='Paid').reduce((n,h)=>n+cents(h.amount),0)/100;
  const reserved=history.filter(h=>h.payroll.status==='Approved').reduce((n,h)=>n+cents(h.amount),0)/100;
  const scheduled=Number(loan.monthlyInstallment)>0&&!!loan.recoveryStart;
  const remaining=Math.max(0,cents(loan.amount)-cents(recovered))/100;
  const status=!scheduled?'Manual':remaining===0?'Recovered':loan.status==='Pending'?'Pending':'Active';
  return {loan,employee,history,recovered,reserved,remaining,status};
 }).filter(r=>(!filters.employee||String(r.loan.employee)===filters.employee)&&(!filters.department||r.employee.department===filters.department)&&(!filters.type||r.loan.type===filters.type)&&(!filters.status||r.status===filters.status)).sort((a,b)=>String(a.employee.code).localeCompare(String(b.employee.code),undefined,{numeric:true})||String(a.loan.date).localeCompare(String(b.loan.date))||Number(a.loan.id)-Number(b.loan.id));
 const history=loans.flatMap(r=>r.history.filter(h=>!filters.month||h.payroll.month===filters.month).map(h=>({...h,loan:r.loan,employee:r.employee}))).sort((a,b)=>String(b.payroll.month).localeCompare(String(a.payroll.month))||Number(a.loan.id)-Number(b.loan.id));
 const totals={principal:loans.reduce((n,r)=>n+cents(r.loan.amount),0)/100,recovered:loans.reduce((n,r)=>n+cents(r.recovered),0)/100,reserved:loans.reduce((n,r)=>n+cents(r.reserved),0)/100,outstanding:loans.filter(r=>r.status!=='Manual').reduce((n,r)=>n+cents(r.remaining),0)/100,manual:loans.filter(r=>r.status==='Manual').length};
 return {loans,history,totals};
}
export const loanValues=(r:any)=>[r.loan.id,r.employee.code,r.employee.name,r.employee.department,r.loan.type,fmtDate(r.loan.date),Number(r.loan.amount||0),Number(r.loan.monthlyInstallment||0),r.recovered,r.reserved,r.status==='Manual'?'Not tracked':r.remaining,r.status];
export const recoveryValues=(r:any)=>[r.loan.id,r.employee.code,r.employee.name,/^\d{4}-\d{2}$/.test(r.payroll.month)?r.payroll.month.slice(5)+'/'+r.payroll.month.slice(0,4):r.payroll.month,(r.payroll.kind==='finalSettlements'?'F&F · ':'')+r.payroll.status,r.amount,fmtDate(r.payroll.paidDate),r.payroll.reference||'—'];
export const loanReportNote='Balances use all saved salary and final settlement history. Paid salary counts as recovered; Approved salary is reserved; Draft is planned only. The salary month filter applies only to recovery history. Legacy manual loans have no automatic recovery schedule and their remaining balance is not tracked.';
const esc=(v:any)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function loanReportHTML(report:ReturnType<typeof loanReport>,company:any,origin:string,selection:string){
 const table=(headers:string[],rows:any[][],financial:number[],total?:any[])=>`<table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((v,i)=>`<td>${esc(financial.includes(i)&&typeof v==='number'?money(v):v)}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${headers.length}">No matching records.</td></tr>`}</tbody>${total?`<tfoot><tr>${total.map((v,i)=>`<td>${esc(financial.includes(i)&&typeof v==='number'?money(v):v)}</td>`).join('')}</tr></tfoot>`:''}</table>`;
 const t=report.totals,total=['TOTAL','','','','','',t.principal,report.loans.reduce((n,r)=>n+Number(r.loan.monthlyInstallment||0),0),t.recovered,t.reserved,t.outstanding,''];
 return `<!doctype html><html><head><meta charset="utf-8"><title>Loan Recovery Report</title><style>@page{size:A3 landscape;margin:12mm}*{box-sizing:border-box}body{font:12px Arial;color:#244b31;margin:20px}header{display:flex;gap:18px;align-items:center;border-bottom:2px solid #176342;padding-bottom:14px}header img{width:60px;height:68px;object-fit:contain}h1{font-size:24px;margin:0}h2{font-size:18px;margin-top:24px}p{line-height:1.6;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;table-layout:fixed;font-size:11px}th,td{border:1px solid #8fa68c;padding:9px 5px;text-align:center;overflow-wrap:anywhere}th,tfoot{background:#e2ecd9;font-weight:bold}thead{display:table-header-group}tr{break-inside:avoid}.controls{margin-bottom:20px;display:flex;gap:12px}button{padding:12px}section.history{break-before:page}@media print{.controls{display:none}body{margin:0}}</style></head><body><div class="controls"><button onclick="window.print()">Print / Save PDF</button><button onclick="window.close()">Close</button></div><header><img src="${esc(origin)}/green-mile-logo.png" alt="Company logo"><div><h1>Green Mile Recycling LLC</h1><p>${esc([company?.location,company?.phone,company?.email].filter(Boolean).join(' · '))}</p></div></header><h2>Loan Recovery Report</h2><p>${esc(selection)} · Generated ${esc(fmtDate(today()))} · AED</p><p>${esc(loanReportNote)}</p>${table(loanHeaders,report.loans.map(loanValues),[6,7,8,9,10],total)}<p>Tracked outstanding: AED ${esc(money(t.outstanding))}. Manual loans: ${t.manual}.</p><section class="history"><h2>Salary recovery history</h2><p>${esc(selection)}</p>${table(recoveryHeaders,report.history.map(recoveryValues),[5])}</section></body></html>`;
}
export async function loanReportWorkbook(ExcelJS:any,report:ReturnType<typeof loanReport>,logo:any,selection:string,company:any){
 const book=new ExcelJS.Workbook();book.creator='Green Mile Recycling LLC · HR';const image=book.addImage({buffer:logo,extension:'png'});
 const t=report.totals,total=['TOTAL','','','','','',t.principal,report.loans.reduce((n,r)=>n+Number(r.loan.monthlyInstallment||0),0),t.recovered,t.reserved,t.outstanding,''];
 for(const [name,headers,values,numeric] of [['Loan balances',loanHeaders,[...report.loans.map(loanValues),total],[6,7,8,9,10]],['Recovery history',recoveryHeaders,report.history.map(recoveryValues),[5]]] as [string,string[],any[][],number[]][]){
  const sheet=book.addWorksheet(name);sheet.columns=headers.map((_,i)=>({width:i===2?30:i===3?24:19}));sheet.addImage(image,{tl:{col:0,row:0},ext:{width:52,height:60}});
  sheet.mergeCells(1,2,2,headers.length);sheet.getCell('B1').value='Green Mile Recycling LLC · Loan Recovery Report';sheet.getCell('B1').font={bold:true,size:18,color:{argb:'FF174D35'}};
  sheet.mergeCells(3,2,3,headers.length);sheet.getCell('B3').value=[company?.location,company?.phone,company?.email].filter(Boolean).join(' · ');
  sheet.mergeCells(4,1,4,headers.length);sheet.getCell('A4').value=selection+' · AED';for(let i=1;i<=4;i++)sheet.getRow(i).height=25;
  sheet.getRow(5).values=headers;sheet.getRow(5).height=42;
  for(const [n,v] of [headers,...values].entries()){const row=sheet.getRow(n+5);row.values=v;if(n)row.height=34;row.eachCell((cell:any,col:number)=>{cell.border={top:{style:'thin'},left:{style:'thin'},bottom:{style:'thin'},right:{style:'thin'}};cell.alignment={wrapText:true,vertical:'middle',horizontal:'center'};cell.font={bold:n===0||v[0]==='TOTAL',color:{argb:n===0?'FFFFFFFF':'FF244B31'}};cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:n===0?'FF176342':n%2?'FFE6EFDD':'FFF2F6ED'}};if(n&&numeric.includes(col-1))cell.numFmt='#,##0.00';});}
  const noteRow=values.length+7;sheet.mergeCells(noteRow,1,noteRow+1,headers.length);sheet.getCell(noteRow,1).value=loanReportNote;sheet.getCell(noteRow,1).alignment={wrapText:true,vertical:'middle'};sheet.getRow(noteRow).height=30;sheet.getRow(noteRow+1).height=30;
  sheet.views=[{state:'frozen',xSplit:3,ySplit:5}];sheet.autoFilter={from:{row:5,column:1},to:{row:5,column:headers.length}};sheet.pageSetup={paperSize:8,orientation:'landscape',fitToPage:true,fitToWidth:1,fitToHeight:0,printTitlesRow:'5:5'};
 }
 return book;
}
