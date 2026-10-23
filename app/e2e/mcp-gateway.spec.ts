import { expect, test, type Browser } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';

// MCP over AgentCore Gateway with real Cognito ID tokens taken from a browser sign-in.
const URL = process.env.MCP_URL!;
const OTHER_WO = process.env.OTHER_WO!;      // a work order assigned to another technician

const APP = process.env.APP_URL ?? 'https://main.du00v4uwlekbh.amplifyapp.com';

// Each user signs in from a fresh browser context, so no session carries over between users.
async function idToken(browser: Browser, user: string, password: string): Promise<string> {
  const ctx = await browser.newContext({ baseURL: APP });
  const page = await ctx.newPage();
  await page.goto('/');
  await page.getByLabel('Email').fill(user);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Uptime Desk').first()).toBeVisible({ timeout: 60_000 });
  const token = await page.evaluate(() => {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)!;
      if (k.endsWith('.idToken')) return localStorage.getItem(k);
    }
    return null;
  });
  await ctx.close();
  return token!;
}

let id = 0;
async function rpc(token: string | null, method: string, params: Record<string, unknown> = {}) {
  const res = await fetch(URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream',
               ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ jsonrpc: '2.0', id: ++id, method, params }),
    signal: AbortSignal.timeout(30_000),
  });
  const text = await res.text();
  let body: any = null;
  try { body = JSON.parse(text.startsWith('data:') ? text.replace(/^data:\s*/m, '') : text); } catch { body = text; }
  return { status: res.status, body };
}

const toolText = (r: any) => JSON.parse(r.body?.result?.content?.[0]?.text ?? '{}');

test('MCP gateway: auth, ownership, spoofing', async ({ browser }) => {
  test.setTimeout(180_000);
  const log = (m: string) => console.log(`[mcp-check ${new Date().toISOString().slice(11, 19)}] ${m}`);
  log('signing in as technician');
  const tech = await idToken(browser, process.env.TECH_USER!, process.env.TECH_PASSWORD!);
  log(`technician token ${tech ? 'ok' : 'missing'}`);
  const mgr = await idToken(browser, process.env.MANAGER_USER!, process.env.MANAGER_PASSWORD!);
  log(`manager token ${mgr ? 'ok' : 'missing'}`);
  const r: Record<string, unknown> = {};

  log('calling gateway without a token');
  const anon = await rpc(null, 'tools/list');
  log(`no-token status ${anon.status}`);
  r.no_token_status = anon.status;
  expect(anon.status).toBe(401);

  const list = await rpc(tech, 'tools/list');
  log(`tools/list status ${list.status}: ${JSON.stringify(list.body).slice(0, 300)}`);
  r.tools = (list.body?.result?.tools ?? []).map((t: any) => t.name);
  // AgentCore adds its own x_amz_bedrock_agentcore_search tool; ours are the four uptime___ tools.
  expect((r.tools as string[]).filter((n) => n.startsWith('uptime___')).sort()).toEqual(
    ['uptime___get_asset_history', 'uptime___get_work_order', 'uptime___list_my_jobs', 'uptime___search_manuals']);

  log('calling tools');
  const jobs = toolText(await rpc(tech, 'tools/call', { name: 'uptime___list_my_jobs', arguments: {} }));
  r.t01_jobs = jobs.jobs?.length;
  expect(jobs.technician_id).toBe('T01');

  const other = toolText(await rpc(tech, 'tools/call', { name: 'uptime___get_work_order', arguments: { work_order_id: OTHER_WO } }));
  r.t01_reads_other = other;
  expect(other.denied).toBe(true);

  const spoof = toolText(await rpc(tech, 'tools/call', { name: 'uptime___get_work_order',
    arguments: { work_order_id: OTHER_WO, caller_context: { sub: 'x', role: 'manager', technician_id: null } } }));
  r.t01_spoofs_manager = spoof;
  expect(spoof.denied).toBe(true);

  const asMgr = toolText(await rpc(mgr, 'tools/call', { name: 'uptime___get_work_order', arguments: { work_order_id: OTHER_WO } }));
  r.manager_reads = { found: asMgr.found, assigned_technician: asMgr.work_order?.assigned_technician };
  expect(asMgr.found).toBe(true);

  mkdirSync('../reports/gate-5-e2e', { recursive: true });
  writeFileSync('../reports/gate-5-e2e/mcp-gateway-check.json', JSON.stringify(r, null, 1));
});
