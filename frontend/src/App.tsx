import {useEffect,useRef,useState,type FormEvent} from 'react';
import {acknowledge,AuthenticationRequired,getHistory,getSession,login,observe,type Session} from './workshop/api';
import {cursorParts,units,type Projection} from './workshop/projection';
import {WorkshopCanvas} from './workshop/WorkshopCanvas';
import {RoleRoster} from './workshop/RoleRoster';
import {ActorExecutionFaceplate} from './workshop/ActorExecutionFaceplate';
import {AttentionRail} from './workshop/AttentionRail';
import {ReviewBench} from './workshop/ReviewBench';
import {OperatorPanel} from './workshop/OperatorPanel';
import {Timeline,type Observation} from './workshop/Timeline';
export function useReducedMotion(){
 const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
 useEffect(()=>{const query=window.matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setReduced(query.matches);query.addEventListener('change',update);update();return()=>query.removeEventListener('change',update);},[]);
 return reduced;
}
export function WorkshopView({snapshot,permissions,busy=false,onAcknowledge=()=>{},observations=[],historyExcerptCursor=null}:{snapshot:Projection;permissions:readonly string[];busy?:boolean;onAcknowledge?:(id:string)=>void;observations?:readonly Observation[];historyExcerptCursor?:string|null}){
 const [selected,setSelected]=useState<string|null>(null),[station,setStation]=useState<string|null>(null);
 const reducedMotion=useReducedMotion();
 function select(id:string){setSelected(id);document.getElementById('item-detail')?.focus();}
 return <><header><h1>Agent Workshop</h1><p className="coverage" role="status">PARTIAL COVERAGE · inventory incomplete · availability unknown outside declared observed scope</p><p>Source mode: {snapshot.source_mode} · Connection quality: <strong>{snapshot.connection_quality}</strong> · Snapshot: {snapshot.cursor}</p><p>Service generated at {snapshot.generated_at}. Per-signal acquisition ages, native/mapped values, source and evidence are retained in item facts. No global availability claim.</p>{snapshot.connection_quality!=='fresh'&&<p className="coverage">LAST-KNOWN / {snapshot.connection_quality} — do not rely on this as current actor state.</p>}</header><nav aria-label="Unit navigation"><button aria-pressed={station===null} onClick={()=>setStation(null)}>Overview · all stations</button>{units(snapshot).map(s=><button key={s} aria-pressed={station===s} onClick={()=>setStation(s)}>{s}</button>)}</nav><main><div className="overview"><WorkshopCanvas snapshot={snapshot} station={station} selected={selected} reducedMotion={reducedMotion} onIntent={i=>i.type==='select'?select(i.id):setStation(i.station)}/><AttentionRail snapshot={snapshot} reducedMotion={reducedMotion} onSelect={select}/></div><ActorExecutionFaceplate item={snapshot.items.find(i=>i.id===selected)}/><ReviewBench snapshot={snapshot} onSelect={select}/><RoleRoster snapshot={snapshot} station={station} onSelect={select}/><OperatorPanel snapshot={snapshot} permissions={permissions} busy={busy} onAcknowledge={onAcknowledge}/><Timeline observations={observations} historyExcerptCursor={historyExcerptCursor}/></main></>;
}
export default function App(){
 const [session,setSession]=useState<Session|null>(null),[needsLogin,setNeedsLogin]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false),[snapshot,setSnapshot]=useState<Projection|null>(null),[observations,setObservations]=useState<Observation[]>([]);
 const [historyError,setHistoryError]=useState('');
 const [historyExcerptCursor,setHistoryExcerptCursor]=useState<string|null>(null);
 const stream=useRef<ReturnType<typeof observe>|null>(null);
 useEffect(()=>{let alive=true;getSession().then(s=>{if(alive)setSession(s);}).catch(e=>{if(alive){setNeedsLogin(e instanceof AuthenticationRequired);setError(e instanceof AuthenticationRequired?'':'Cannot establish local session.');}});return()=>{alive=false;};},[]);
 useEffect(()=>{
  if(!session)return;
  let alive=true,loadingHistory=false,historyCursor='';
  let latest:Projection|null=null;
  function authFailure(e:unknown){if(e instanceof AuthenticationRequired){setNeedsLogin(true);setSession(null);setSnapshot(null);setObservations([]);setHistoryExcerptCursor(null);}}
  function loadHistory(){
   if(!latest||latest.connection_quality!=='fresh'||loadingHistory||historyCursor===latest.cursor)return;
   const requestedIdentity=cursorParts(latest.cursor).identity;loadingHistory=true;
   void getHistory().then(history=>{
    if(!alive||!latest||cursorParts(latest.cursor).identity!==requestedIdentity||cursorParts(history.cursor).identity!==requestedIdentity)return;
    historyCursor=history.cursor;setHistoryExcerptCursor(history.cursor);setObservations([...history.entries]);setHistoryError('');
   }).catch(e=>{if(alive){setHistoryError('Retained history unavailable; previously loaded entries remain historical only.');authFailure(e);}})
    .finally(()=>{loadingHistory=false;if(alive&&latest&&cursorParts(latest.cursor).identity!==requestedIdentity)loadHistory();});
  }
  const subscription=observe(p=>{
   if(latest&&cursorParts(latest.cursor).identity!==cursorParts(p.cursor).identity){historyCursor='';setObservations([]);setHistoryExcerptCursor(null);}
   latest=p;setSnapshot(p);setError('');loadHistory();
  },e=>{setError('Transport disconnected or invalid data: last-known facts only.');authFailure(e);});
  stream.current=subscription;
  return()=>{alive=false;subscription.close();stream.current=null;};
 },[session]);
 async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const input=form.elements.namedItem('token') as HTMLInputElement;const token=input.value;input.value='';setBusy(true);try{setSession(await login(token));setNeedsLogin(false);setError('');}catch{setError('Local login failed. Check the provisioned secret.');}finally{setBusy(false);}}
 async function ack(id:string){if(!session)return;setBusy(true);try{await acknowledge(session,id);await stream.current?.refresh();}catch(e){setError('Acknowledgement not verified. Reconcile and inspect the occurrence; do not assume success.');if(e instanceof AuthenticationRequired){setSession(null);setNeedsLogin(true);}}finally{setBusy(false);}}
 return <>{historyError&&<p role="status">{historyError}</p>}{error&&<p role="alert">{error}</p>}{needsLogin?<main><h1>Agent Workshop · local session</h1><p>Loopback supervision only. Use the locally provisioned login secret; it is never put in a URL or browser storage.</p><form onSubmit={submit}><label>Local login secret <input type="password" name="token" autoComplete="off" required/></label><button disabled={busy}>Establish local session</button></form></main>:snapshot?<WorkshopView snapshot={snapshot} permissions={session?.permissions??[]} busy={busy} onAcknowledge={id=>void ack(id)} observations={observations} historyExcerptCursor={historyExcerptCursor}/>:<main><h1>Agent Workshop</h1><p>Awaiting authenticated atomic snapshot. Coverage and availability unknown.</p></main>}</>;
}
