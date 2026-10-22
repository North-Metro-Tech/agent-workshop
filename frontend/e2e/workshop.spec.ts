import {test,expect,chromium,type Page} from '@playwright/test';
import {spawn,type ChildProcess} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {once} from 'node:events';
import {mkdtempSync,mkdirSync,rmSync} from 'node:fs';
import {createServer} from 'node:net';
import path from 'node:path';

// Real, isolated, synthetic service is mandatory and provisioned by this suite.
// No skipped tests, fetch intercepts, API mocks, native acquisition or preexisting secrets.
const root=path.resolve(import.meta.dirname,'../..');
const token=randomBytes(32).toString('base64url');
let processHandle:ChildProcess|null=null,port:number,origin:string,stateDir:string;
let serviceOutput='';
async function start(){
 serviceOutput='';
 processHandle=spawn(process.env.WORKSHOP_E2E_PYTHON??path.join(root,'.venv/bin/python'),
  [path.join(root,'scripts/dev.py'),'serve','--synthetic','--port',String(port),'--state-dir',stateDir],
  {cwd:root,env:{...process.env,WORKSHOP_LOGIN_TOKEN:token},stdio:['ignore','pipe','pipe']});
 processHandle.stdout?.on('data',data=>{serviceOutput+=data.toString();});processHandle.stderr?.on('data',data=>{serviceOutput+=data.toString();});
 processHandle.on('error',error=>{serviceOutput+=error.message;});
 await expect.poll(async()=>{try{return (await fetch(origin+'/api/session',{headers:{Origin:origin}})).status;}catch{return 0;}},
  {timeout:10000,message:'Isolated real HTTP service must start; '+serviceOutput}).toBe(401);
}
async function stop(){
 const child=processHandle;processHandle=null;if(!child||child.exitCode!==null)return;
 const exited=once(child,'exit');child.kill('SIGINT');await exited;
 expect(child.exitCode,serviceOutput).toBe(0);
}
async function login(page:Page){
 await page.goto(origin+'/');await page.getByLabel('Local login secret').fill(token);
 await page.getByRole('button',{name:'Establish local session'}).click();
 await expect(page.getByRole('heading',{name:'Agent Workshop',exact:true})).toBeVisible();
 await expect(page.locator('[data-history-id]').first()).toBeVisible();
}
async function snapshot(page:Page){return page.evaluate(async()=>{const response=await fetch('/api/snapshot');if(!response.ok)throw new Error('No actual snapshot');return response.json();});}
async function history(page:Page){return page.evaluate(async()=>{const response=await fetch('/api/history');if(!response.ok)throw new Error('No actual historian');return response.json();});}

test.describe.configure({mode:'serial'});
test.beforeAll(async()=>{
 const reservation=createServer();reservation.listen(0,'127.0.0.1');await once(reservation,'listening');port=(reservation.address() as {port:number}).port;
 await new Promise<void>(resolve=>reservation.close(()=>resolve()));origin=`http://127.0.0.1:${port}`;
 const base=path.join(root,'.workshop-state/e2e');mkdirSync(base,{recursive:true,mode:0o700});stateDir=mkdtempSync(path.join(base,'run-'));
 await start();
});
test.afterAll(async()=>{await stop();if(stateDir)rmSync(stateDir,{recursive:true,force:true});});

test('provisioned service: scene/DOM facts, keyboard, reduced motion and local-only authority',async({page,context})=>{
 await page.emulateMedia({reducedMotion:'reduce'});await login(page);
 await expect(page.getByText(/PARTIAL COVERAGE/)).toBeVisible();
 const data=await snapshot(page);expect(data.source_mode).toBe('synthetic');expect(data.native_write_enabled).toBe(false);
 for(const item of data.items){
  const row=page.locator('.roster > li').filter({has:page.getByRole('button',{name:`${item.kind}: ${item.label}`,exact:true})});
  await expect(row).toHaveCount(1);await row.locator('summary').click();
  await expect(row).toContainText(item.id);await expect(row).toContainText(item.station);
  for(const f of item.facts){
   await expect(row).toContainText(f.name);
   if(/(?:^|[._])age$/.test(f.name)&&f.value!=='unknown'){
    const displayed=await row.locator('dt').evaluateAll((nodes,name)=>nodes.find(n=>n.textContent===name)?.nextElementSibling?.textContent,f.name);
    expect(Number.isFinite(Number(displayed))).toBe(true);expect(Number(displayed)).toBeGreaterThanOrEqual(0);expect(Math.abs(Number(displayed)-Number(f.value))).toBeLessThan(5);
   }else await expect(row).toContainText(f.value);
  }
 }
 const canvas=page.locator('canvas');await expect(canvas).toBeVisible();
 expect(await canvas.evaluate((node:HTMLCanvasElement)=>{const pixels=node.getContext('2d')!.getImageData(0,0,node.width,node.height).data;return pixels.some((value,index)=>index%4!==3&&value!==0);})).toBe(true);
 const list=page.getByRole('listbox',{name:'Scene items'});await list.focus();await page.keyboard.press('Home');await page.keyboard.press('Enter');
 await expect(page.locator('#item-detail')).toContainText(data.items[0].id);await expect(page.locator('#item-detail')).toBeFocused();
 await expect(page.locator('.annunciate')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'ADMISSION HOLD — NOT A SAFETY-RATED STOP',exact:true})).toBeDisabled();
 await page.getByLabel('Key-switch position').selectOption('controller');
 for(const button of await page.getByRole('button',{name:/Acknowledge locally:/}).all())await expect(button).toBeDisabled();
 expect(await page.evaluate(()=>localStorage.length)).toBe(0);
 const cookies=await context.cookies();expect(cookies.some(c=>c.name==='workshop_session'&&c.httpOnly&&c.sameSite==='Strict')).toBe(true);
 await page.screenshot({path:path.join(root,'evidence/phase3-remediation/browser-scene.png'),fullPage:true});
 const requests:string[]=[];page.on('request',r=>requests.push(r.url()));await page.reload();
 await expect(page.locator('[data-history-id]').first()).toBeVisible();
 expect(requests.some(url=>new URL(url).pathname==='/api/snapshot')).toBe(true);
 expect(requests.filter(url=>new URL(url).pathname==='/api/events').every(url=>!new URL(url).search)).toBe(true);
});

test('real transport reconnect restores atomic facts without replacing retained history',async({page,context})=>{
 await login(page);const before=await history(page);
 await context.setOffline(true);await expect(page.getByText(/LAST-KNOWN \/ disconnected/)).toBeVisible();
 for(const button of await page.getByRole('button',{name:/Acknowledge locally:/}).all())await expect(button).toBeDisabled();
 await context.setOffline(false);await expect(page.getByText(/LAST-KNOWN \/ disconnected/)).toHaveCount(0);
 await expect(page.locator('[data-history-id]').first()).toBeVisible();expect((await history(page)).entries).toEqual(before.entries);
});

test('new browser process and service restart retain diagnostics, revoke sessions and invalidate live freshness',async({page})=>{
 await login(page);const before=await history(page);const old=await snapshot(page);
 await stop();await expect(page.getByText(/LAST-KNOWN \/ disconnected/)).toBeVisible();await start();
 // A restarted service has no in-memory login/session authority. The existing
 // browser must expose reauthentication without a manual reload.
 await expect(page.getByLabel('Local login secret')).toBeVisible({timeout:15000});
 const second=await chromium.launch({headless:true,executablePath:process.env.WORKSHOP_E2E_CHROMIUM});
 try{
  const fresh=await second.newPage();await login(fresh);
  const retained=await history(fresh),current=await snapshot(fresh);
  expect(retained.entries).toEqual(before.entries);expect(current.cursor.split(':')[0]).toBe(old.cursor.split(':')[0]);
  expect(BigInt(current.cursor.split(':')[1])).toBeGreaterThan(BigInt(old.cursor.split(':')[1]));
  const ids=await fresh.locator('[data-history-id]').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('data-history-id')));
  expect(ids).toEqual(retained.entries.map((entry:{id:string})=>entry.id));
  await expect(fresh.locator('[data-history-cursor]')).toContainText(retained.cursor);
  const executions=current.items.filter((item:{kind:string})=>item.kind==='execution');
  expect(executions.every((item:{facts:{name:string,value:string}[]})=>item.facts.some(f=>f.name==='acquired_at'&&f.value==='unknown'))).toBe(true);
 }finally{await second.close();}
});

test('actual local acknowledgement updates one restrained live region and preserves focus',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});await login(page);
 const announcement=page.locator('[data-alarm-announcement]');await expect(announcement).toHaveText('');
 await page.getByLabel('Key-switch position').selectOption('operator');
 const ack=page.getByRole('button',{name:/Acknowledge locally:/}).first();await expect(ack).toBeEnabled();
 // Keep keyboard focus on a stable control; mutation is an actual same-origin HTTP call.
 const selector=page.getByLabel('Key-switch position');await selector.focus();
 await page.evaluate(async()=>{
  const session=await (await fetch('/api/session')).json();const p=await (await fetch('/api/snapshot')).json();const alarm=p.items.find((i:{acknowledge_id:string|null})=>i.acknowledge_id!==null);
  const response=await fetch('/api/alarms/acknowledge',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({occurrence_id:alarm.acknowledge_id,position:'operator'})});if(!response.ok)throw new Error('Actual local acknowledgement failed');
 });
 await expect(announcement).toContainText('acknowledged');await expect(selector).toBeFocused();
 const text=await announcement.textContent();await page.evaluate(async()=>{for(let n=0;n<6;n++)await fetch('/api/snapshot');});
 await expect(announcement).toHaveText(text!);await expect(page.locator('.annunciate')).toHaveCount(0);
});
