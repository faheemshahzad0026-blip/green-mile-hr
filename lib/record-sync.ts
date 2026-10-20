export function mergeSyncedRecords(previous:any[],changes:any[],deletedIds:number[]=[]){
 const removed=new Set(deletedIds),oldIds=new Set(previous.map(r=>r.id));
 const updates=new Map(changes.filter(r=>!removed.has(r.id)).map(r=>[r.id,r]));
 return [...changes.filter(r=>!oldIds.has(r.id)&&!removed.has(r.id)),...previous.filter(r=>!removed.has(r.id)).map(r=>updates.get(r.id)||r)];
}
