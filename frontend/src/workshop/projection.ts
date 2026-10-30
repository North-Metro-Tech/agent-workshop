import type {Snapshot,Item} from './generated';
export type Immutable<T> = T extends object ? {readonly [K in keyof T]:Immutable<T[K]>} : T;
export type Projection = Immutable<Snapshot>;
export type ViewItem = Immutable<Item>;
const kinds = new Set(['role','execution','task','alarm','incident','diagnostic']);
function record(v:unknown): v is Record<string,unknown> {return !!v && typeof v==='object' && !Array.isArray(v);}
function text(v:unknown):v is string{return typeof v==='string' && v.length<=16384;}
export function cursorParts(cursor:string):{identity:string,revision:bigint} {
  const match=/^([^:\s]{1,128}):(0|[1-9][0-9]{0,19})$/.exec(cursor);
  if(!match) throw new Error('Invalid projection cursor');
  return {identity:match[1],revision:BigInt(match[2])};
}
export function validateSnapshot(value:unknown):Projection {
  if(!record(value)||!text(value.cursor)||typeof value.generated_at!=='number'||!Number.isFinite(value.generated_at)||value.generated_at<0||value.native_write_enabled!==false||!['synthetic','approved-local'].includes(String(value.source_mode))||!text(value.connection_quality)||!Array.isArray(value.items)||value.items.length>10000) throw new Error('Invalid read-only snapshot');
  cursorParts(value.cursor);
  const ids=new Set<string>();
  const items=value.items.map(raw=>{
    if(!record(raw)||!text(raw.id)||ids.has(raw.id)||!kinds.has(String(raw.kind))||!text(raw.label)||!text(raw.station)||typeof raw.attention!=='boolean'||!(raw.acknowledge_id===null||text(raw.acknowledge_id))||!Array.isArray(raw.facts)||raw.facts.length>256) throw new Error('Invalid projection item');
    ids.add(raw.id);
    const facts=raw.facts.map(f=>{if(!record(f)||!text(f.name)||!text(f.value)) throw new Error('Invalid fact');return Object.freeze({name:f.name,value:f.value});});
    return Object.freeze({id:raw.id,kind:raw.kind as Item['kind'],label:raw.label,station:raw.station,attention:raw.attention,acknowledge_id:raw.acknowledge_id,facts:Object.freeze(facts)});
  });
  return Object.freeze({cursor:value.cursor,generated_at:value.generated_at,native_write_enabled:false,source_mode:value.source_mode as Snapshot['source_mode'],connection_quality:value.connection_quality,items:Object.freeze(items)});
}
export function acceptSnapshot(current:Projection|null,next:Projection,authoritative=false):Projection {
  if(!current) return next;
  const a=cursorParts(current.cursor),b=cursorParts(next.cursor);
  if(a.identity!==b.identity) {if(!authoritative) throw new Error('Cursor identity changed: atomic snapshot required');return next;}
  if(b.revision<a.revision)return current;
  if(b.revision===a.revision&&next.generated_at<current.generated_at)return current;
  return next;
}
export function disconnected(p:Projection):Projection {return Object.freeze({...p,connection_quality:'disconnected'});}
export function fact(item:ViewItem,name:string):string|undefined{return item.facts.find(f=>f.name===name)?.value;}
export function isUnacknowledged(item:ViewItem):boolean {return ['unacknowledged','return-to-normal-unacked'].includes(fact(item,'alarm_state')??'');}
export function safeEvidenceURL(value:string):string|null {
  try {const u=new URL(value);if(u.protocol!=='https:'||u.hostname!=='github.com'||u.port||u.username||u.password||!/^\/North-Metro-Tech\/agent-workshop(?:\/|$)/.test(u.pathname))return null;return u.href;}catch{return null;}
}
export function units(p:Projection):string[]{return [...new Set(p.items.map(i=>i.station))];}
