import type {History} from './generated';
import {cursorParts,type Immutable} from './projection';
export type RetainedHistory=Immutable<History>;
function record(v:unknown):v is Record<string,unknown>{return !!v&&typeof v==='object'&&!Array.isArray(v);}
function text(v:unknown):v is string{return typeof v==='string'&&v.length<=16384;}
export function validateHistory(value:unknown):RetainedHistory{
 if(!record(value)||typeof value.cursor!=='string'||value.semantics!=='historical evidence; bounded excerpt, not current state or verified progress'||value.ordering!=='per-identity retained order; cross-source ordering uncertain'||!Array.isArray(value.entries)||value.entries.length>100)throw new Error('Invalid retained history');
 cursorParts(value.cursor);const ids=new Set<string>();
 const entries=value.entries.map(entry=>{
  if(!record(entry)||!text(entry.id)||ids.has(entry.id)||!text(entry.item_id)||!text(entry.label)||!(entry.observed_at===null||(typeof entry.observed_at==='number'&&Number.isFinite(entry.observed_at)))||!Array.isArray(entry.facts)||entry.facts.length>256)throw new Error('Invalid historical entry');
  ids.add(entry.id);
  const facts=entry.facts.map(f=>{if(!record(f)||!text(f.name)||!text(f.value))throw new Error('Invalid historical fact');return Object.freeze({name:f.name,value:f.value});});
  return Object.freeze({id:entry.id,item_id:entry.item_id,label:entry.label,observed_at:entry.observed_at,facts:Object.freeze(facts)});
 });
 return Object.freeze({cursor:value.cursor,semantics:value.semantics,ordering:value.ordering,entries:Object.freeze(entries)});
}
