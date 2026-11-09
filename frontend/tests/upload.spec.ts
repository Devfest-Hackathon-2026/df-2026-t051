import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('keyboard upload, unreviewed results and no automated accessibility violations', async ({page}) => {
  await page.goto('/');
  await expect(page.getByText('ローカルデモ：', {exact:false})).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', {name:'メインコンテンツへ移動'})).toBeFocused();
  await page.keyboard.press('Enter');
  await page.locator('#chart-file').setInputFiles('../backend/tests/fixtures/sample.png');
  await page.getByRole('button', {name:'固定デモデータを表示'}).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', {name:'読み取り結果'})).toBeFocused();
  await expect(page.getByRole('cell', {name:'未確定',exact:true})).toBeVisible();
  await expect(page.getByText('AI抽出・未検証',{exact:true})).toBeVisible();
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});

test('invalid upload focuses accessible error and retry works', async ({page}) => {
  await page.goto('/');
  await page.locator('#chart-file').setInputFiles({name:'bad.png',mimeType:'image/png',buffer:Buffer.from('invalid')});
  await page.getByRole('button', {name:'固定デモデータを表示'}).click();
  await expect(page.getByRole('alert')).toBeFocused();
  await expect(page.getByRole('alert')).toContainText('有効なPNG/JPEG');
  await page.locator('#chart-file').setInputFiles('../backend/tests/fixtures/sample.png');
  await page.getByRole('button', {name:'固定デモデータを表示'}).click();
  await expect(page.getByRole('table')).toBeVisible();
});
