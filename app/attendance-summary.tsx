'use client';
import {useMemo,useState} from 'react';
import {dailyAttendance} from '../lib/attendance-summary';
import {today,fmtDate} from '../lib/hr';

function gpsLabel(loc:any){
  if(!loc||loc.latitude==null||loc.longitude==null) return null;
  return `https://www.google.com/maps?q=${loc.latitude},${loc.longitude}`;
}

export default function AttendanceSummary({records,onOpen}:{records:any[],onOpen:(action:string,r:any,k:string)=>void}){
  const [day,setDay]=useState(today()),[department,setDepartment]=useState(''),[status,setStatus]=useState('');
  const all=useMemo(()=>dailyAttendance(records,day,today()),[records,day]);
  const rows=all.filter(r=>(!department||r.employee.department===department)&&(!status||r.status===status));

  return <section className="card daily-summary">
    <div className="card-head">
      <div>
        <h2>Daily attendance review</h2>
        <p>{fmtDate(day)} · Open View for In/Out selfies and GPS maps. Missing attendance needs HR review; it is not automatically saved as absent.</p>
      </div>
    </div>
    <div className="daily-controls">
      <label>Date<input type="date" value={day} onChange={e=>{if(e.target.value)setDay(e.target.value)}}/></label>
      <label>Department<select value={department} onChange={e=>setDepartment(e.target.value)}><option value="">All departments</option>{[...new Set(all.map(r=>r.employee.department))].map(d=><option key={d}>{d}</option>)}</select></label>
      <label>Status<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{[...new Set(all.map(r=>r.status))].map(s=><option key={s}>{s}</option>)}</select></label>
      <strong>{rows.length} employee(s)</strong>
    </div>
    <p className="daily-note">Selfie and GPS columns show evidence from employee check-in and check-out. Late minutes use the employee’s effective shift start.</p>
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{['Employee','Department','Status','Check in','Check out','Selfies','GPS','Worked hours','Late minutes','Extra hours','Actions'].map(h=><th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map(r=>{
            const rec=r.record;
            const inSelfie=!!rec?.checkInSelfie;
            const outSelfie=!!rec?.checkOutSelfie;
            const inGps=gpsLabel(rec?.checkInLocation);
            const outGps=gpsLabel(rec?.checkOutLocation);
            return <tr key={r.employee.id}>
              <td>{r.employee.name} · {r.employee.code}</td>
              <td>{r.employee.department}</td>
              <td><span className="badge">{r.status}</span></td>
              <td>{rec?.timeIn||'—'}</td>
              <td>{rec?.timeOut||'—'}</td>
              <td>
                {rec?(
                  <span className="att-evidence-col">
                    {inSelfie&&<span className="att-gps-chip">In</span>}
                    {outSelfie&&<span className="att-gps-chip">Out</span>}
                    {!inSelfie&&!outSelfie&&'—'}
                  </span>
                ):'—'}
              </td>
              <td>
                {rec?(
                  <span className="att-evidence-col">
                    {inGps&&<a className="att-gps-chip" href={inGps} target="_blank" rel="noreferrer">In map</a>}
                    {outGps&&<a className="att-gps-chip" href={outGps} target="_blank" rel="noreferrer">Out map</a>}
                    {!inGps&&!outGps&&'—'}
                  </span>
                ):'—'}
              </td>
              <td>{r.hours===null?'—':r.hours.toFixed(2)}</td>
              <td>{r.lateMinutes===null?'—':r.lateMinutes}</td>
              <td>{r.extraHours===null?'—':r.extraHours.toFixed(2)}</td>
              <td>
                <button className="secondary" onClick={()=>onOpen('view',rec||r.employee,rec?'attendance':'employees')}>View</button>
                {rec&&<button className="secondary" onClick={()=>onOpen('update',rec,'attendance')}>Edit</button>}
              </td>
            </tr>;
          })}
        </tbody>
      </table>
      {!rows.length&&<p className="daily-note">No employees match this date and filter.</p>}
    </div>
  </section>;
}
