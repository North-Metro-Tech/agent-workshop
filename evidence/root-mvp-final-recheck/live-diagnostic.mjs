// Diagnostic only: preserve the mismatch, do not treat stale facts as current agreement.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
const root='/home/aaron/.hermes/kanban/boards/agent-workshop/workspaces/t_7e8a8223/root-mvp-closure';
const dir=path.dirname(import.meta.filename);
const require=createRequire(path.join(root,'frontend/package.json'));
const {chromium,expect}=require('@playwright/test');
const origin='https://frankenfarm.taile4f46c.ts.net:10000';
const secret=fs.readFileSync('/home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local/login-secret','utf8').trim();
const browser=await chromium.launch({headless:true,executablePath:'/home/aaron/.local/bin/chromium'});
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const page=await context.newPage();
 assert.equal((await context.request.get(origin+'/api/session')).status(),401);
 assert.equal((await page.goto(origin)).status(),200);
 await page.getByLabel('Local login secret').fill(secret);
 await page.getByRole('button',{name:'Establish local session'}).click();
 await expect(page.getByRole('heading',{name:'Agent Workshop',exact:true})).toBeVisible();
 const initial=await page.evaluate(async()=>await(await fetch('/api/snapshot')).json());
 fs.writeFileSync(path.join(dir,'browser-snapshot-initial.json'),JSON.stringify(initial,null,2)+'\n');
 assert.equal(initial.native_write_enabled,false);assert.equal(initial.source_mode,'approved-local');
 const diag=JSON.parse(fs.readFileSync(path.join(dir,'agreement-diagnostic.json'),'utf8'));
 const rows=[];
 for(const r of diag.installed.rows){
  const item=initial.items.find(i=>i.kind==='execution'&&i.label===r.id);assert.ok(item);
  const facts=Object.fromEntries(item.facts.map(f=>[f.name,f.value]));
  rows.push({id:r.id,native_lifecycle:r.current_source.lifecycle,retained_lifecycle:facts['lifecycle.mapped'],quality:facts.lifecycle_quality,source_record:facts['lifecycle.evidence_class'],task:facts['task.native_id'],agrees:r.current_source.lifecycle===facts['lifecycle.mapped']});
 }
 assert.ok(rows.some(r=>r.id==='42'&&!r.agrees));assert.ok(rows.some(r=>r.id==='44'&&!r.agrees));
 assert.ok(rows.filter(r=>!r.agrees).every(r=>r.quality==='unknown'));
 const target=initial.items.find(i=>i.kind==='execution'&&i.label==='45');assert.ok(target);
 await page.getByRole('button',{name:`execution: 45 · ${target.station}`,exact:true}).click();
 await expect(page.locator('#item-detail')).toBeFocused();
 await expect(page.locator('#item-detail')).toContainText('t_7e8a8223');
 await expect(page.getByRole('button',{name:'ADMISSION HOLD — NOT A SAFETY-RATED STOP',exact:true})).toBeDisabled();
 await page.screenshot({path:path.join(dir,'live-diagnostic.png')});
 await expect.poll(async()=>page.evaluate(async()=>(await(await fetch('/api/snapshot')).json()).cursor)).not.toBe(initial.cursor);
 const final=await page.evaluate(async()=>await(await fetch('/api/snapshot')).json());
 fs.writeFileSync(path.join(dir,'browser-snapshot-final.json'),JSON.stringify(final,null,2)+'\n');
 const report={result:'MISMATCH_REPRODUCED_NOT_MVP_PASS',origin,initial_cursor:initial.cursor,final_cursor:final.cursor,connection_quality:initial.connection_quality,native_write_enabled:initial.native_write_enabled,rows,interpretation:'Current native unknown transitions retained as raw records but prior active lifecycle is preserved with unknown quality under reconciliation latch; Core disposition required, no assertion weakened to manufacture agreement.'};
 fs.writeFileSync(path.join(dir,'live-diagnostic-report.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
