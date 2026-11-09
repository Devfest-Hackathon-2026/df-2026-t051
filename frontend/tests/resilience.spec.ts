import {test,expect} from '@playwright/test';
const draft={source:'demo',status:'unreviewed',extraction:{supported:true,title:'再試行の確認',unit:'人',categories:[{label:'A',value:12,evidence:'12'},{label:'B',value:null,evidence:null}],warnings:[],reason:null}};
for(const status of [401,403,429,504])test(`teacher handles injected ${status} without automatic retry`,async({page})=>{
  let attempts=0;await page.route('**/api/analyze',route=>{attempts++;return route.fulfill({status,json:{detail:`監査用のエラー ${status}`},headers:status===429?{'Retry-After':'1'}:{}});});
  await page.goto('/');await page.locator('#chart-file').setInputFiles('../backend/tests/fixtures/sample.png');await page.getByRole('button',{name:'固定デモデータを表示'}).click();
  await expect(page.getByRole('alert')).toBeFocused();await expect(page.getByRole('alert')).toContainText(String(status));await expect(page.getByRole('button',{name:'固定デモデータを表示'})).toBeEnabled();expect(attempts).toBe(1);
  await page.unroute('**/api/analyze');await page.route('**/api/analyze',route=>route.fulfill({json:draft}));await page.getByRole('button',{name:'固定デモデータを表示'}).click();await expect(page.getByRole('table')).toBeVisible();
});
test('teacher recovers from injected network failure',async({page})=>{
  let attempts=0;await page.route('**/api/analyze',r=>{attempts++;return r.abort();});await page.goto('/');await page.locator('#chart-file').setInputFiles('../backend/tests/fixtures/sample.png');await page.getByRole('button',{name:'固定デモデータを表示'}).click();
  await expect(page.getByRole('alert')).toBeFocused();await expect(page.getByRole('button',{name:'固定デモデータを表示'})).toBeEnabled();expect(attempts).toBe(1);
  await page.unroute('**/api/analyze');await page.route('**/api/analyze',route=>route.fulfill({json:draft}));await page.getByRole('button',{name:'固定デモデータを表示'}).click();await expect(page.getByRole('table')).toBeVisible();
});
test('teacher bounds a stalled request at its application timeout',async({page})=>{
  await page.addInitScript(()=>{const original=window.setTimeout.bind(window);window.setTimeout=(handler,timeout,...args)=>original(handler,timeout===60000?80:timeout,...args);});
  let attempts=0;await page.route('**/api/analyze',()=>{attempts++;});await page.goto('/');await page.locator('#chart-file').setInputFiles('../backend/tests/fixtures/sample.png');await page.getByRole('button',{name:'固定デモデータを表示'}).click();
  await expect(page.getByRole('alert')).toBeFocused();await expect(page.getByRole('alert')).toContainText('時間切れ');await expect(page.getByRole('button',{name:'固定デモデータを表示'})).toBeEnabled();expect(attempts).toBe(1);
});
