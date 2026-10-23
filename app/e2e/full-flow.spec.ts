import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

const SCENARIO_DAY = process.env.E2E_DAY ?? '2021-06-09';
const SCENARIO_UNIT = process.env.E2E_UNIT ?? 'Site1-Milford-7.5t';
const RUN = process.env.E2E_RUN ?? '1';

async function signIn(page: Page, user: string, password: string) {
  await page.goto('/');
  await page.getByLabel('Email').fill(user);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Uptime Desk').first()).toBeVisible({ timeout: 60_000 });
}

async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByLabel('Email')).toBeVisible();
}

test('replay, diagnose, approve, dispatch, and ask the assistant', async ({ page }) => {
  const t: Record<string, number | string | boolean> = { run: RUN, scenario: `${SCENARIO_UNIT}|${SCENARIO_DAY}` };
  const t0 = Date.now();
  const mark = (k: string) => { t[k] = Math.round((Date.now() - t0) / 100) / 10; };

  // Manager: sign in and launch a recorded day.
  await signIn(page, process.env.MANAGER_USER!, process.env.MANAGER_PASSWORD!);
  mark('signed_in_s');
  await page.goto('/scenarios');
  const row = page.getByRole('row').filter({ hasText: SCENARIO_DAY }).filter({ hasText: SCENARIO_UNIT });
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.getByRole('button', { name: 'Replay' }).click();
  // Starting a run can take up to a minute when the API and Aurora are waking from idle.
  await expect(page.getByRole('heading', { name: 'Live pipeline' })).toBeVisible({ timeout: 120_000 });
  t.run_id = (await page.locator('code').first().innerText()).trim();
  mark('replay_started_s');

  // Pipeline: wait for the drafted work order.
  const woBanner = page.getByText(/Work order WO-[\w-]+:/);
  await expect(woBanner).toBeVisible({ timeout: 6 * 60_000 });
  mark('work_order_drafted_s');
  const banner = await woBanner.innerText();
  const woId = banner.match(/WO-[\w-]+/)![0];
  t.work_order_id = woId;
  t.work_order_status = banner.includes(': draft') ? 'draft' : banner.includes(': blocked') ? 'blocked' : 'other';
  await expect(page.getByText('Published label (ground truth)')).toBeVisible({ timeout: 60_000 });

  // Diagnosis: either verified citations or an explicit abstention.
  await page.goto('/diagnosis');
  await expect(page.getByRole('heading', { name: 'Diagnosis' })).toBeVisible();
  await expect(page.getByText(/passed: quote on page and entailed|Insufficient evidence/).first()).toBeVisible({ timeout: 60_000 });
  t.verified_citations_shown = await page.getByText('passed: quote on page and entailed').count();

  // Work orders: approve the draft, which resumes the Step Functions run.
  expect(t.work_order_status, `work order ${woId} was ${t.work_order_status}, not draft`).toBe('draft');
  await page.goto('/work-orders');
  const card = page.locator('.card').filter({ hasText: woId });
  await card.getByRole('button', { name: 'Approve and dispatch' }).click();
  await expect(card.getByText('approved')).toBeVisible({ timeout: 60_000 });
  mark('approved_s');

  // Dispatch board: wait for the Fargate OR-Tools task to assign or escalate it.
  let placed = '';
  for (let i = 0; i < 40 && !placed; i++) {
    await page.goto('/dispatch');
    await expect(page.getByRole('heading', { name: 'Dispatch board' })).toBeVisible();
    await page.waitForTimeout(3000);
    const assigned = page.locator('table').first().getByText(woId);
    const escalated = page.locator('table').nth(1).getByText(woId);
    if (await assigned.count()) placed = 'assigned';
    else if (await escalated.count()) placed = 'escalated_or_reschedule';
    else await page.waitForTimeout(7000);
  }
  expect(placed, 'work order never reached the dispatch board').not.toBe('');
  t.dispatch_outcome = placed;
  mark('dispatched_s');
  await signOut(page);

  // Technician: ask about own jobs, then try to read the manager's newly dispatched order.
  await signIn(page, process.env.TECH_USER!, process.env.TECH_PASSWORD!);
  await page.goto('/assistant');
  const box = page.getByLabel('Question');
  await box.fill('What jobs do I have this week?');
  await page.getByRole('button', { name: 'Ask' }).click();
  await expect(page.locator('.card').filter({ hasText: 'What jobs do I have this week?' })).toBeVisible({ timeout: 120_000 });
  mark('assistant_answered_s');
  await box.fill(`Show me the details of work order ${woId}.`);
  await page.getByRole('button', { name: 'Ask' }).click();
  const second = page.locator('.card').filter({ hasText: `work order ${woId}` });
  await expect(second).toBeVisible({ timeout: 120_000 });
  t.cross_technician_denied = (await second.getByText('Access denied').count()) > 0;
  t.cross_technician_leak = (await second.innerText()).toLowerCase().includes('stage2') ||
    (await second.innerText()).toLowerCase().includes('stage 2');
  mark('done_s');

  mkdirSync('../reports/gate-5-e2e', { recursive: true });
  writeFileSync(`../reports/gate-5-e2e/run-${RUN}.json`, JSON.stringify(t, null, 1));
  expect(t.cross_technician_leak).toBe(false);
});
