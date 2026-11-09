import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const id='a'.repeat(32);
const snapshot={id,status:'approved',approved_at:'2026-11-05T03:00:00Z',data:{title:'学習用の記録',unit:'人',categories:[{label:'A組',value:0},{label:'B組',value:18},{label:'C組',value:null}]}};

test('one known value is never presented as the overall maximum and minimum',async({page})=>{
  await page.route('**/api/materials/*',r=>r.fulfill({json:{...snapshot,data:{...snapshot.data,categories:[{label:'A',value:13},{label:'B',value:null}]}}}));
  await page.goto(`/learn/${id}`);
  await expect(page.getByText('確定している数値は1件だけです。全項目の最大値・最小値はまだ判断できません。')).toBeVisible();
  await expect(page.getByText('確認できた値：A、13 人')).toBeVisible();
  await expect(page.getByText(/^最大値：|^最小値：/)).toHaveCount(0);
});

test('partial extrema are explicitly limited to the known subset',async({page})=>{
  await page.route('**/api/materials/*',r=>r.fulfill({json:snapshot}));await page.goto(`/learn/${id}`);
  await expect(page.getByText('未確定の項目があります。全項目の最大値・最小値は確定していません。')).toBeVisible();
  await expect(page.getByText('確認できた範囲の最大値：B組、18 人')).toBeVisible();
});

test('student keyboard comparison and repeat announcement update; no model request',async({page})=>{
  let analyzes=0;page.on('request',r=>{if(r.url().includes('/api/analyze'))analyzes++;});
  await page.route('**/api/materials/*',route=>route.fulfill({json:snapshot}));
  await page.goto(`/learn/${id}`);
  await expect(page).toHaveTitle('学習用の記録 | ChartBridge');
  await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'メインコンテンツへ移動'})).toBeFocused();
  await page.keyboard.press('Enter');await page.keyboard.press('Tab');
  await expect(page.getByRole('combobox',{name:'比較する項目',exact:true})).toBeFocused();
  await page.keyboard.press('ArrowDown');await page.keyboard.press('Tab');await page.keyboard.press('Home');await page.keyboard.press('Tab');
  await expect(page.getByRole('button',{name:'数値を比較する'})).toBeFocused();await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toContainText('差は 18 人');
  const old=await page.getByRole('status').locator('span').elementHandle();
  await page.keyboard.press('Enter');
  expect(await old!.evaluate(element=>element.isConnected)).toBe(false);
  await page.getByRole('combobox',{name:'比較する項目',exact:true}).selectOption('2');
  await page.getByRole('button',{name:'数値を比較する'}).click();
  await expect(page.getByRole('status')).toContainText('未確定の数値を含むため比較できません');
  expect(analyzes).toBe(0);
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});

test('all unknown values and unknown unit never become a numeric zero',async({page})=>{
  await page.route('**/api/materials/*',r=>r.fulfill({json:{...snapshot,data:{title:'未確定の教材',unit:null,categories:[{label:'A',value:null},{label:'B',value:null}]}}}));
  await page.goto(`/learn/${id}`);
  await expect(page.getByText('確定した数値がないため、最大値・最小値を計算できません。')).toBeVisible();
  await expect(page.getByText('単位：未確定',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'数値を比較する'}).click();
  await expect(page.getByRole('status')).toContainText('未確定');
  await page.getByRole('combobox',{name:'差し引く項目',exact:true}).selectOption('0');
  await page.getByRole('button',{name:'数値を比較する'}).click();
  await expect(page.getByRole('status')).toContainText('異なる2つの項目');
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});

test('server error focuses alert, retry recovers and focuses title',async({page})=>{
  let fail=true;
  await page.route('**/api/materials/*',r=>fail?r.fulfill({status:503,json:{detail:'test'}}):r.fulfill({json:snapshot}));
  await page.goto(`/learn/${id}`);
  await expect(page.getByRole('alert')).toBeFocused();
  await expect(page.getByRole('alert')).toContainText('再試行');
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
  fail=false;await page.getByRole('button',{name:'もう一度読み込む'}).click();
  await expect(page.getByRole('heading',{name:'学習用の記録',exact:true})).toBeFocused();
});

for(const status of [403,404])test(`direct URL ${status} is a human-readable student error`,async({page})=>{
  await page.route('**/api/materials/*',r=>r.fulfill({status,json:{detail:'test'}}));
  await page.goto('/learn/not-a-material');
  await expect(page.getByRole('heading',{name:'承認済み教材を開く'})).toBeVisible();
  await expect(page.getByRole('alert')).toBeFocused();
  await expect(page.getByRole('alert')).toContainText(status===403?'アクセス権':'見つかりません');
});

test('invalid response and network errors have Japanese messages',async({page})=>{
  await page.route('**/api/materials/*',r=>r.fulfill({contentType:'text/html',body:'<html>bad response</html>'}));
  await page.goto(`/learn/${id}`);await expect(page.getByRole('alert')).toContainText('教材データを読み取れません');
  await page.unroute('**/api/materials/*');await page.route('**/api/materials/*',r=>r.abort());
  await page.getByRole('button',{name:'もう一度読み込む'}).click();await expect(page.getByRole('alert')).toContainText('接続できません');
});

test('a pending request times out with an accessible retry action',async({page})=>{
  // Accelerate only the application's 20-second timeout; this is a mock test.
  await page.addInitScript(()=>{
    const original=window.setTimeout.bind(window);
    window.setTimeout=(handler,timeout,...args)=>original(handler,timeout===20000?50:timeout,...args);
  });
  await page.route('**/api/materials/*',()=>{});
  await page.goto(`/learn/${id}`);
  await expect(page.getByRole('alert')).toContainText('時間切れ');
  await expect(page.getByRole('alert')).toBeFocused();
  await expect(page.getByRole('button',{name:'もう一度読み込む'})).toBeEnabled();
});

for(const width of [320,390,1280])test(`12 long categories fit viewport ${width}`,async({page})=>{
  await page.setViewportSize({width,height:850});
  await page.route('**/api/materials/*',r=>r.fulfill({json:{...snapshot,data:{...snapshot.data,title:'長い見出し'.repeat(12),categories:Array.from({length:12},(_,i)=>({label:'非常に長い項目名'.repeat(8)+i,value:i%3===0?null:i*2}))}}}));
  await page.goto(`/learn/${id}`);await expect(page.getByRole('table')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});
