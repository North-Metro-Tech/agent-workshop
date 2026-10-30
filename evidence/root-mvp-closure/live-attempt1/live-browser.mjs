// Installed-fleet integration evidence only. No native writes or product changes.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const root='/home/aaron/.hermes/kanban/boards/agent-workshop/workspaces/t_7e8a8223/root-mvp-closure';
const directory=path.dirname(import.meta.filename);
const require=createRequire(path.join(root,'frontend/package.json'));
const {chromium,expect}=require('@playwright/test');
const origin='https://frankenfarm.taile4f46c.ts.net:10000';
const secret=fs.readFileSync('/home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local/login-secret','utf8').trim();
const comparison=JSON.parse(fs.readFileSync(path.join(directory,'one-shot-workflow-2.json'),'utf8'));
const target=comparison.comparisons.find(x=>x.task.native_id==='t_7e8a8223'&&x.native_attempt_status==='running');
assert.ok(target,'A real running final-sweep attempt must exist; never manufacture one');
const browser=await chromium.launch({headless:true,executablePath:'/home/aaron/.local/bin/chromium'});
const errors=[],urls=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>urls.push(r.url()));
 assert.equal((await context.request.get(origin+'/api/session')).status(),401);
 assert.equal((await page.goto(origin)).status(),200);
 await expect(page.getByRole('heading',{name:'Agent Workshop · local session',exact:true})).toBeVisible();
 await page.getByLabel('Local login secret').fill(secret);
 await page.getByRole('button',{name:'Establish local session'}).click();
 await expect(page.getByRole('heading',{name:'Agent Workshop',exact:true})).toBeVisible();
 await expect(page.getByText('PARTIAL COVERAGE · inventory incomplete · availability unknown outside declared observed scope',{exact:true})).toBeVisible();
 await expect(page.locator('[data-history-id]').first()).toBeVisible();
 const initial=await page.evaluate(async()=>({snapshot:await (await fetch('/api/snapshot')).json(),history:await (await fetch('/api/history')).json()}));
 const snapshot=initial.snapshot;
 fs.writeFileSync(path.join(directory,'browser-snapshot-initial.json'),JSON.stringify(snapshot,null,2)+'\n');
 assert.equal(snapshot.source_mode,'approved-local');assert.equal(snapshot.connection_quality,'fresh');assert.equal(snapshot.native_write_enabled,false);
 const executions=snapshot.items.filter(i=>i.kind==='execution');assert.equal(executions.length,comparison.compared_attempts);
 for(const entry of comparison.comparisons){
  const item=executions.find(i=>i.label===entry.execution_id);assert.ok(item);
  const facts=Object.fromEntries(item.facts.map(f=>[f.name,f.value]));
  assert.equal(facts['lifecycle.mapped'],entry.projected_lifecycle);
  assert.equal(facts['lifecycle.evidence_class'],'source_record');
  assert.equal(facts['task.native_id'],entry.task.native_id);
  assert.equal(facts['task.source_instance'],entry.task.source_instance);
  assert.equal(facts['task.namespace'],entry.task.namespace);
 }
 const selected=executions.find(i=>i.label===target.execution_id);assert.ok(selected);
 const select=page.getByRole('button',{name:`execution: ${target.execution_id} · ${selected.station}`,exact:true});
 await select.click();await expect(page.locator('#item-detail')).toBeFocused();
 const detail=page.locator('#item-detail');
 await expect(detail).toContainText(selected.id);await expect(detail).toContainText('t_7e8a8223');
 // SSE updates acquisition age/time/count continuously. Compare stable native
 // semantics; never demand that a later render reproduce an earlier age float.
 const dynamicFacts=new Set(['acquired_at','acquisition_age','retained_observation_count']);
 for(const fact of selected.facts){await expect(detail.getByText(fact.name,{exact:true})).toBeVisible();if(!dynamicFacts.has(fact.name))await expect(detail).toContainText(fact.value);}
 const ageText=await detail.getByText('acquisition_age',{exact:true}).evaluate(el=>el.nextElementSibling?.textContent);
 assert.ok(Number.isFinite(Number(ageText))&&Number(ageText)>=0);
 const canvas=page.locator('canvas');
 assert.equal(await canvas.evaluate(c=>Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data).some((v,i)=>i%4!==3&&v!==0)),true);
 await expect(page.getByRole('button',{name:'ADMISSION HOLD — NOT A SAFETY-RATED STOP',exact:true})).toBeDisabled();
 await page.screenshot({path:path.join(directory,'live-selected-detail.png')});
 const station=page.getByLabel('Key-switch position');await station.selectOption('controller');
 for(const b of await page.getByRole('button',{name:/Acknowledge locally:/}).all())await expect(b).toBeDisabled();
 await station.selectOption('viewer');
 await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(directory,'live-operator-overview.png')});
 await expect.poll(async()=>page.evaluate(async()=>((await (await fetch('/api/snapshot')).json()).cursor))).not.toBe(snapshot.cursor);
 const final=await page.evaluate(async()=>({snapshot:await (await fetch('/api/snapshot')).json(),history:await (await fetch('/api/history')).json(),localStorage:localStorage.length,sessionStorage:sessionStorage.length}));
 fs.writeFileSync(path.join(directory,'browser-snapshot-final.json'),JSON.stringify(final.snapshot,null,2)+'\n');
 fs.writeFileSync(path.join(directory,'browser-history.json'),JSON.stringify(final.history,null,2)+'\n');
 assert.equal(final.snapshot.connection_quality,'fresh');assert.ok(final.history.entries.length>0);
 assert.equal(final.localStorage,0);assert.equal(final.sessionStorage,0);
 await page.reload();await expect(page.getByRole('heading',{name:'Agent Workshop',exact:true})).toBeVisible();
 assert.equal((await context.request.post(origin+'/api/session',{headers:{Origin:'http://untrusted.invalid'},data:{token:'not-a-secret'}})).status(),403);
 assert.equal((await context.request.get(origin+'/api/snapshot?token=not-a-secret')).status(),403);
 const executeStatus=(await context.request.post(origin+'/api/execute',{headers:{Origin:origin},data:{}})).status();
 assert.ok([404,405].includes(executeStatus),'No supported execute mutation route');
 const cookies=await context.cookies();assert.ok(cookies.some(c=>c.name==='workshop_session'&&c.httpOnly&&c.sameSite==='Strict'));
 assert.ok(urls.every(u=>!u.includes(secret)));assert.deepEqual(errors,[]);
 const second=await browser.newContext();assert.equal((await second.request.get(origin+'/api/session')).status(),401);await second.close();
 const report={result:'PASS',origin,source_mode:snapshot.source_mode,connection_quality:snapshot.connection_quality,compared_executions:executions.length,all_execution_lifecycle_task_links_match_separate_native_acquisition:true,target_execution:target.execution_id,target_task:target.task.native_id,target_process_at_separate_acquisition:target.process_at_acquisition,selected_detail_facts: selected.facts.length,canvas_pixels:true,live_cursor_advanced:final.snapshot.cursor!==snapshot.cursor,initial_cursor:snapshot.cursor,final_cursor:final.snapshot.cursor,history_entries:final.history.entries.length,keyboard_detail_focus:true,admission_hold_disconnected:true,controller_does_not_enable_controls:true,native_write_enabled:false,session_reload:true,new_context_requires_auth:true,host_origin_query_boundary:true,no_execute_route:true,browser_storage_entries:0,page_errors:errors,coverage:'partial',availability:'unknown',limits:['Native comparison uses a separately timed acquisition; historian exact-revision verification is a separate step.','No manual assistive-technology speech or owner daily-use judgement.','No native controls, forced native task changes, remote exposure or broader fleet discovery.']};
 fs.writeFileSync(path.join(directory,'browser-report.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report,null,2));
} finally {await browser.close();}
