import {acceptSnapshot,disconnected,validateSnapshot,type Projection} from './projection';
import {validateHistory} from './history';
import type {Session as WireSession} from './generated';
export type Session={csrf:WireSession['csrf'];permissions:readonly WireSession['permissions'][number][];controller_connected:false};
export class AuthenticationRequired extends Error {}
async function request(path:string,init:RequestInit={}):Promise<unknown>{
 const response=await fetch(path,{...init,credentials:'same-origin',cache:'no-store',redirect:'error'});
 if(response.status===401)throw new AuthenticationRequired('Local session required');
 if(!response.ok)throw new Error(`Workshop request failed (${response.status})`);
 const text=await response.text();if(text.length>4*1024*1024)throw new Error('Snapshot exceeds display limit');
 return JSON.parse(text);
}
export async function getSession():Promise<Session>{
 const v=await request('/api/session') as Partial<Session>;
 if(!v||typeof v.csrf!=='string'||!v.csrf||!Array.isArray(v.permissions)||!v.permissions.every(p=>p==='viewer'||p==='operator')||v.controller_connected!==false)throw new Error('Invalid local session');
 return Object.freeze({csrf:v.csrf,permissions:Object.freeze([...v.permissions]),controller_connected:false});
}
export async function login(token:string):Promise<Session>{await request('/api/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});return getSession();}
export async function getSnapshot():Promise<Projection>{return validateSnapshot(await request('/api/snapshot'));}
export async function getHistory(){return validateHistory(await request('/api/history'));}
export async function acknowledge(session:Session,occurrence_id:string):Promise<void>{
 if(!session.permissions.includes('operator'))throw new Error('Operator permission required');
 await request('/api/alarms/acknowledge',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({occurrence_id,position:'operator'})});
}
// Only this transport owns current state. No browser cache, localStorage, cursor query or credentials in URLs.
// EventSource sends Last-Event-ID on reconnect; every new browser session reacquires a full snapshot.
export function observe(onSnapshot:(p:Projection)=>void,onError:(e:unknown)=>void){
 let current:Projection|null=null,closed=false,refreshing=false,suspended=true,epoch=0;
 let pending:Projection|null=null;
 let offline=false;
 const source=new EventSource('/api/events');
 function lost(error:unknown){epoch++;refreshing=false;suspended=true;pending=null;if(current){current=disconnected(current);onSnapshot(current);}onError(error);if(error instanceof AuthenticationRequired)source.close();}
 function publish(next:Projection,authoritative=false){current=acceptSnapshot(current,next,authoritative);onSnapshot(current);}
 async function refresh(){
  if(closed||refreshing||offline)return;
  refreshing=true;suspended=true;const version=++epoch;
  try{
   const next=await getSnapshot();if(closed||version!==epoch)return;
   publish(next,true);refreshing=false;suspended=false;
   const buffered=pending;pending=null;
   if(buffered){try{publish(buffered);}catch{void refresh();}}
  }catch(error){if(!closed&&version===epoch)lost(error);}
 }
 source.addEventListener('snapshot',event=>{
  if(closed||offline)return;
  try{
   const data=(event as MessageEvent<string>).data;
   if(typeof data!=='string'||data.length>4*1024*1024)throw new Error('Invalid stream payload size');
   const next=validateSnapshot(JSON.parse(data));
   if(refreshing){pending=pending?acceptSnapshot(pending,next,true):next;return;}
   if(suspended){void refresh();return;}
   try{publish(next);}catch{void refresh();}
  }catch(error){lost(error);void refresh();}
 });
 source.addEventListener('reset',()=>{if(!closed){pending=null;epoch++;refreshing=false;void refresh();}});
 source.addEventListener('session-expired',()=>{if(!closed)lost(new AuthenticationRequired('Local session expired'));});
 source.onopen=()=>{void refresh();};
 source.onerror=()=>{
  if(closed)return;
  lost(new Error('Transport disconnected; last-known facts only'));
  const version=epoch;
  // EventSource does not expose a reconnect HTTP 401. Probe authentication,
  // without presenting HTTP-only recovery as a healthy live stream.
  void getSession().catch(error=>{if(!closed&&version===epoch&&error instanceof AuthenticationRequired)lost(error);});
 };
 const wentOffline=()=>{offline=true;if(!closed)lost(new Error('Browser offline; last-known facts only'));};
 const wentOnline=()=>{offline=false;void refresh();};
 window.addEventListener('offline',wentOffline);window.addEventListener('online',wentOnline);
 void refresh();
 return {refresh,close(){closed=true;epoch++;source.close();window.removeEventListener('offline',wentOffline);window.removeEventListener('online',wentOnline);}};
}
