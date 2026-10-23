import { chromium } from '@playwright/test';
const BASE = process.env.BASE ?? 'http://localhost:4174';
const OUT = process.env.OUT;
const pages = ['/', '/pipeline', '/asset', '/diagnosis', '/work-orders', '/dispatch', '/assistant', '/evidence'];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
for (const p of pages) {
  await page.goto(BASE + p);
  await page.waitForTimeout(1500);
  const bad = await page.locator('.banner.bad').allInnerTexts();
  const signIn = await page.getByRole('button', { name: 'Sign in' }).count();
  const h1 = await page.locator('h1').first().innerText().catch(() => '');
  console.log(p.padEnd(13), '|', h1, '| error banners:', JSON.stringify(bad), '| sign-in:', signIn);
  if (OUT) await page.screenshot({ path: `${OUT}/static${p === '/' ? '-home' : p.replace('/', '-')}.png`, fullPage: false });
}
console.log('page errors:', errors);
await browser.close();
