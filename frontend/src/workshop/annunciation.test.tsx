import {act} from 'react';
import {createRoot,type Root} from 'react-dom/client';
import {afterEach,beforeEach,it,expect} from 'vitest';
import {AttentionRail} from './AttentionRail';
import {fixture} from './fixtures.test-support';
import {acceptSnapshot,validateSnapshot} from './projection';
import type {Snapshot} from './generated';
let root:Root,host:HTMLDivElement;
beforeEach(()=>{Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();});
async function render(raw:Snapshot,reducedMotion=true){await act(async()=>root.render(<AttentionRail snapshot={validateSnapshot(raw)} reducedMotion={reducedMotion} onSelect={()=>{}}/>));}
const live=()=>host.querySelector('[data-alarm-announcement]')!;
it('announces arriving/changed alarms once, not on repeated identical receipts, without moving focus',async()=>{
 const raw=fixture();await render(raw);
 expect(live().getAttribute('aria-live')).toBe('polite');expect(live().textContent).toBe('');
 const focused=host.querySelector('button')!;focused.focus();
 const changes:string[]=[];const observer=new MutationObserver(()=>changes.push(live().textContent??''));observer.observe(live(),{childList:true,subtree:true,characterData:true});
 raw.items[4].facts[0].value='acknowledged';await render(raw);
 expect(live().textContent).toContain('acknowledged');expect(live().textContent).toContain('not causality');expect(document.activeElement).toBe(focused);
 for(let n=0;n<12;n++){raw.cursor=`store:${n+2}`;raw.generated_at+=1;await render(raw);}
 expect(changes).toHaveLength(1);
 raw.items.push({...raw.items[4],id:'arriving-alarm',label:'New source uncertainty'});await render(raw);
 expect(live().textContent).toContain('New source uncertainty');expect(changes).toHaveLength(2);expect(document.activeElement).toBe(focused);
 expect(host.querySelector('.annunciate')).toBeNull();observer.disconnect();
});
it('bounds batch announcements, ignores non-alarm updates, and does not relabel source resets as arrivals',async()=>{
 const raw=fixture();await render(raw,false);
 raw.items[1].label='Changed execution label';await render(raw,false);expect(live().textContent).toBe('');
 for(let n=0;n<10;n++)raw.items.push({...raw.items[4],id:`batch-arrival-${n}`,label:`Arrival ${n}`});
 await render(raw,false);expect(live().textContent).toContain('7 additional changes');expect(live().textContent).not.toContain('Arrival 9');
 raw.cursor='newidentity:1';await render(raw,false);expect(live().textContent).toContain('identity changed');expect(live().textContent).not.toContain('Arrival');
});
it('does not announce unknown/stale transport facts as a fresh alarm transition',async()=>{
 const raw=fixture();await render(raw);raw.connection_quality='disconnected';raw.items[4].facts[0].value='acknowledged';await render(raw);
 expect(live().textContent).toBe('');expect(host.querySelector('.annunciate')).toBeNull();
 raw.connection_quality='fresh';await render(raw);expect(live().textContent).toContain('acknowledged');
});
it('does not regress freshness when older buffered SSE has the same revision as a newer atomic snapshot',()=>{
 const raw=fixture();raw.generated_at=200;raw.items[1].facts.push({name:'lifecycle_quality',value:'stale'});
 const current=validateSnapshot(raw),older=fixture();older.generated_at=190;
 expect(acceptSnapshot(current,validateSnapshot(older))).toBe(current);
});
it('announces successive occurrences of the same alarm rule even when state labels repeat',async()=>{
 const raw=fixture();await render(raw);
 raw.items.push({...raw.items[4],id:'occurrence-2'});await render(raw);
 const first=live().textContent;expect(first).toContain('occurrence-2');
 raw.items.push({...raw.items[4],id:'occurrence-3'});await render(raw);
 expect(live().textContent).toContain('occurrence-3');expect(live().textContent).not.toBe(first);
});
it('announces priority-only transitions and successive removals, but not repeat receipts',async()=>{
 const raw=fixture();raw.items.push({...raw.items[4],id:'another'});await render(raw);
 raw.items[4].facts.push({name:'rule.priority',value:'high'});await render(raw);
 expect(live().textContent).toContain('priority high');
 raw.items.pop();await render(raw);const first=live().textContent;expect(first).toContain('not proof of clear');
 raw.items.splice(4,1);await render(raw);expect(live().textContent).not.toBe(first);
 const second=live().textContent;await render(raw);expect(live().textContent).toBe(second);
});
