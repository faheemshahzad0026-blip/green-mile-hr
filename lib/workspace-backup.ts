// Export current server records and recent audit together. Never use the
// browser's filtered or cached record list as the backup source.
export async function workspaceBackup(db:any,owner:string,format:(row:any)=>any,exportedAt:string){
 const results=await db.batch([
  db.prepare('SELECT * FROM hr_records WHERE owner=? ORDER BY id DESC LIMIT 10001').bind(owner),
  db.prepare('SELECT * FROM hr_audit WHERE owner=? ORDER BY id DESC LIMIT 100').bind(owner),
 ]);
 const records=results[0].results;
 if(records.length>10000)throw Error('Workspace exceeds the current 10,000-record backup limit. Request a full database export before continuing.');
 return {version:1,exportedAt,timezone:'Asia/Dubai',records:records.map(format),audit:results[1].results};
}
