import {AsyncLocalStorage} from 'node:async_hooks';
const context=new AsyncLocalStorage<{waitUntil:(promise:Promise<any>)=>void}>();
export function withPushContext<T>(ctx:{waitUntil:(promise:Promise<any>)=>void},fn:()=>T){return context.run(ctx,fn);}
export async function runPushTask(task:Promise<any>){const safe=task.catch(()=>{});const ctx=context.getStore();if(ctx)ctx.waitUntil(safe);else await safe;}
