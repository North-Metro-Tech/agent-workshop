import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {it,expect,vi} from 'vitest';
import {fixture} from './fixtures.test-support';
import {validateSnapshot,type Projection} from './projection';
import {validateHistory} from './history';
import type {History} from './generated';
const transport=vi.hoisted(()=>({getSession:vi.fn(),getHistory:vi.fn(),observe:vi.fn()}));
vi.mock('./api',async original=>({...await original<typeof import('./api')>(),...transport}));
vi.mock('./WorkshopCanvas',()=>({WorkshopCanvas:()=>null}));
import App from '../App';
const history=(identity='store',label='Historical source proof'):History=>({
 cursor:`${identity}:1`,semantics:'historical evidence; bounded excerpt, not current state or verified progress',
 ordering:'per-identity retained order; cross-source ordering uncertain',entries:[{id:`${identity}-record`,
 item_id:'exec-1',label,observed_at:null,facts:[{name:'source',value:'synthetic retained evidence'}]}]
});
it('retained history is bounded, validated and deeply immutable, never current-state semantics',()=>{
 const raw=history(),value=validateHistory(raw);raw.entries[0].label='mutated outside';
 expect(value.entries[0].label).toBe('Historical source proof');expect(Object.isFrozen(value.entries[0].facts[0])).toBe(true);
 expect(()=>validateHistory({...history(),semantics:'current facts'})).toThrow();
 expect(()=>validateHistory({...history(),entries:Array.from({length:101},()=>history().entries[0])})).toThrow();
 expect(()=>validateHistory({...history(),entries:[history().entries[0],history().entries[0]]})).toThrow();
});
it('an in-flight old historian response cannot repopulate diagnostics after source identity changes',async()=>{
 Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});
 const media=vi.spyOn(window,'matchMedia').mockReturnValue({matches:true,addEventListener:()=>{},removeEventListener:()=>{}} as unknown as MediaQueryList);
 transport.getSession.mockResolvedValue({csrf:'synthetic-csrf',permissions:['viewer'],controller_connected:false});
 let resolve!:(history:History)=>void,emit!:(p:Projection)=>void;
 transport.getHistory.mockReturnValueOnce(new Promise<History>(done=>{resolve=done;})).mockResolvedValueOnce(history('replacement','New historian proof'));
 transport.observe.mockImplementation((onSnapshot:(p:Projection)=>void)=>{emit=onSnapshot;onSnapshot(validateSnapshot(fixture()));return {close:()=>{},refresh:async()=>{}};});
 const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 try{
  await act(async()=>root.render(<App/>));expect(transport.getHistory).toHaveBeenCalledTimes(1);
  const next=fixture();next.cursor='replacement:1';await act(async()=>emit(validateSnapshot(next)));
  await act(async()=>resolve(history('store','OLD HISTORIAN MUST NOT APPEAR')));
  expect(transport.getHistory).toHaveBeenCalledTimes(2);
  expect(host.textContent).not.toContain('OLD HISTORIAN MUST NOT APPEAR');expect(host.textContent).toContain('New historian proof');
  expect(host.querySelector('[data-history-cursor]')?.textContent).toBe('replacement:1');
 }finally{await act(async()=>root.unmount());host.remove();media.mockRestore();transport.getHistory.mockReset();transport.observe.mockReset();transport.getSession.mockReset();}
});
