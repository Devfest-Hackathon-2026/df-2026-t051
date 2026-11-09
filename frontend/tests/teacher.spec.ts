import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';

const id='b'.repeat(32),snapshotId='c'.repeat(32);
const extraction={supported:true,reason:null,title:'教員確認の教材',unit:'人',categories:[{label:'A',value:12,evidence:'12'},{label:'B',value:18,evidence:'18'}],warnings:[]};
const data={title:extraction.title,unit:'人',categories:extraction.categories.map(({label,value})=>({label,value}))};

async function setup(page,approved=false,publicAccess=false){
  let saved=approved?{id,status:'approved',version:2,data,original:extraction,image_id:null,snapshot_id:snapshotId}:null;
  const snapshot={id:snapshotId,status:'approved',approved_at:'2026-11-06T00:00:00Z',data};
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname,method=route.request().method();
    if(path==='/api/config')return route.fulfill({json:{demo:false,authMode:'google_iam',persistence:true,serviceBaseUrl:'https://example.test',publicAccess}});
    if(path==='/api/analyze')return route.fulfill({json:{source:'gemini',status:'unreviewed',image_id:null,extraction}});
    if(path==='/api/drafts'&&method==='GET')return route.fulfill({json:saved?[saved]:[]});
    if(path==='/api/drafts'&&method==='POST'){
      saved={id,status:'unreviewed',version:1,...route.request().postDataJSON(),snapshot_id:null};
      return route.fulfill({status:201,json:saved});
    }
    if(path===`/api/drafts/${id}/approve`){saved={...saved,status:'approved',snapshot_id:snapshotId};return route.fulfill({json:snapshot});}
    if(path===`/api/drafts/${id}/approved`)return route.fulfill({json:snapshot});
    if(path===`/api/drafts/${id}`)return route.fulfill({json:saved});
    return route.fulfill({status:404,json:{detail:'not found'}});
  });
}

for(const publicAccess of [false,true])test(`sharing notice reflects configured public access ${publicAccess}`,async({page})=>{
  await setup(page,true,publicAccess);await page.goto('/');
  await page.getByRole('button',{name:'教員確認の教材 — 承認済み'}).click();
  await expect(page.getByText(publicAccess?'このリンクでは承認済みの教材だけを閲覧できます。':'現在はIAM非公開です。共有先でもCloud Runのアクセス権が必要です。')).toBeVisible();
});

test('teacher phase and original AI state stay distinct through approval',async({page})=>{
  await setup(page);await page.goto('/');
  await expect(page.getByText(/Day 1|準備中/)).toHaveCount(0);
  await expect(page.getByRole('list',{name:'教材作成の流れ'}).getByRole('listitem')).toHaveCount(5);
  await page.locator('#chart-file').setInputFiles('../backend/tests/fixtures/sample.png');
  await expect(page.locator('[aria-current="step"]')).toContainText('AI解析');
  await page.getByRole('button',{name:'グラフを読み取る'}).click();
  await expect(page.getByText('教材：未保存・教員確認前',{exact:true})).toBeVisible();
  await expect(page.getByText('AI抽出・未検証',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'未承認として保存'}).click();
  await expect(page.getByText('教材：未承認・保存済み',{exact:true})).toBeVisible();
  await page.getByRole('checkbox').check();
  await expect(page.locator('[aria-current="step"]')).toContainText('承認');
  await page.getByRole('button',{name:'確認して承認版を作成'}).click();
  await expect(page.getByRole('heading',{name:'承認版を作成しました'})).toBeFocused();
  await expect(page.getByText('教材：承認済み（配布版固定）',{exact:true})).toBeVisible();
  await expect(page.getByText('AI抽出・未検証',{exact:true})).toBeVisible();
  await expect(page.locator('[aria-current="step"]')).toContainText('共有');
  await expect(page.getByRole('spinbutton',{name:'項目1の数値'})).toBeDisabled();
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
  fs.mkdirSync('../docs/verification',{recursive:true});
  fs.writeFileSync('../docs/verification/day5-teacher-aria.yml',await page.locator('main').ariaSnapshot());
  for(const width of [320,390]){
    await page.setViewportSize({width,height:850});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
  }
});

test('opening an existing approval does not call it newly created',async({page})=>{
  await setup(page,true);await page.goto('/');
  await page.getByRole('button',{name:'教員確認の教材 — 承認済み'}).click();
  await expect(page.getByRole('heading',{name:'承認済み教材を開いています'})).toBeFocused();
  await expect(page.getByRole('heading',{name:'承認版を作成しました'})).toHaveCount(0);
  await expect(page.getByText('教材：承認済み（配布版固定）',{exact:true})).toBeVisible();
  await expect(page.getByText('AI抽出・未検証',{exact:true})).toBeVisible();
});
