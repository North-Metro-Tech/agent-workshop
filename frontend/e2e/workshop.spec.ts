import {test,expect} from '@playwright/test';
const token=process.env.WORKSHOP_E2E_TOKEN;
test.skip(!token,'Actual loopback service login must be provisioned with WORKSHOP_E2E_TOKEN.');
test('actual service: local login, immutable scene/DOM facts, keyboard, reduced motion and browser restart',async({page,context})=>{
 test.skip(!token,'Set WORKSHOP_E2E_TOKEN for a provisioned actual loopback service; no API mocks.');
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/');
 const login=page.getByLabel('Local login secret');
 await expect(login).toBeVisible();await login.fill(token!);await page.getByRole('button',{name:'Establish local session'}).click();
 await expect(page.getByRole('heading',{name:'Agent Workshop',exact:true})).toBeVisible();
 await expect(page.getByText(/PARTIAL COVERAGE/)).toBeVisible();
 const snapshot=await page.evaluate(async()=>{const response=await fetch('/api/snapshot');return response.json();});
 expect(snapshot.native_write_enabled).toBe(false);
 for(const item of snapshot.items){
  const row=page.locator('.roster > li').filter({has:page.getByRole('button',{name:`${item.kind}: ${item.label}`,exact:true})});
  await expect(row).toHaveCount(1);await row.locator('summary').click();
  await expect(row).toContainText(item.id);await expect(row).toContainText(item.station);
  for(const f of item.facts){await expect(row).toContainText(f.name);await expect(row).toContainText(f.value);}
 }
 const list=page.getByRole('listbox',{name:'Scene items'});await list.focus();await page.keyboard.press('Home');await page.keyboard.press('Enter');
 if(snapshot.items.length){await expect(page.locator('#item-detail')).toContainText(snapshot.items[0].id);await expect(page.locator('#item-detail')).toBeFocused();}
 await expect(page.locator('.annunciate')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'ADMISSION HOLD — NOT A SAFETY-RATED STOP',exact:true})).toBeDisabled();
 const select=page.getByLabel('Key-switch position');await select.selectOption('controller');
 for(const button of await page.getByRole('button',{name:/Acknowledge locally:/}).all())await expect(button).toBeDisabled();
 expect(await page.evaluate(()=>localStorage.length)).toBe(0);
 const cookies=await context.cookies();expect(cookies.some(c=>c.httpOnly)).toBe(true);
 const requests:string[]=[];page.on('request',r=>requests.push(r.url()));await page.reload();
 await expect(page.getByRole('heading',{name:'Agent Workshop',exact:true})).toBeVisible();expect(requests.some(url=>new URL(url).pathname==='/api/snapshot')).toBe(true);expect(requests.filter(url=>new URL(url).pathname==='/api/events').every(url=>!new URL(url).search)).toBe(true);
});
