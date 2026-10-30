import {useEffect,useRef,useState} from 'react';
import {cursorParts,fact,type Projection} from './projection';
// One polite batch per material transition, not per snapshot receipt. Never focus.
export function useAlarmAnnouncements(snapshot:Projection){
 const previous=useRef<{identity:string;states:Map<string,string>}|null>(null);
 const [announcement,setAnnouncement]=useState('');
 const transition=useRef(0);
 useEffect(()=>{
  if(snapshot.connection_quality!=='fresh')return;
  const identity=cursorParts(snapshot.cursor).identity;
  const alarms=snapshot.items.filter(i=>i.kind==='alarm');
  const states=new Map(alarms.map(i=>[i.id,JSON.stringify([i.label,fact(i,'alarm_state'),fact(i,'rule.priority')])]));
  const before=previous.current;previous.current={identity,states};
  // Initial inventory is available in the rail. Don't read every alarm on login.
  if(!before)return;
  if(before.identity!==identity){setAnnouncement(`Alarm source identity changed. Update ${++transition.current}. Inspect the refreshed alarm inventory; first-out ordering may be uncertain.`);return;}
  const changed=alarms.filter(i=>before.states.get(i.id)!==states.get(i.id));
  const removed=[...before.states.keys()].filter(id=>!states.has(id)).length;
  if(!changed.length&&!removed)return;
  const details=changed.slice(0,3).map(i=>`${i.label.slice(0,80)} (${i.id.slice(0,80)}): ${fact(i,'alarm_state')??'unknown'}; priority ${fact(i,'rule.priority')??'unknown'}`).join('; ');
  // A transition sequence also makes repeated removal/reset batches observable
  // without clearing/reinserting live regions or announcing identical receipts.
  setAnnouncement(`Alarm update ${++transition.current}. ${details}${changed.length>3?`; ${changed.length-3} additional changes; inspect attention rail`:''}${removed?`; ${removed} no longer in the displayed inventory, not proof of clear`:''}. First-out is observed order, not causality.`);
 },[snapshot]);
 return announcement;
}
