// Explicit opt-in diagnostic. Never included in the automated offline suite.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createServer} from 'node:net';
import {mkdtemp, mkdir, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromium} from 'playwright';

if (process.env.TOGAS_RUN_LIVE_WORKFLOW !== '1') throw new Error('Requires TOGAS_RUN_LIVE_WORKFLOW=1; sends one synthetic journal to real Jev.');
const frontend = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(frontend, '..');
const apiPort = 18000, uiPort = 15173;
const api = `http://127.0.0.1:${apiPort}/api`, site = `http://127.0.0.1:${uiPort}`;
const temporary = await mkdtemp(join(tmpdir(), 'togas-live-browser-'));
const artifacts = join(frontend, 'test-results', 'live-workflow');
await mkdir(artifacts, {recursive: true});
const steps = [], errors = [];
let backend, preview, browser, page, analysis, approved, completed, analyzeRequests = 0;
function start(command, args, options) {
  const child = spawn(command, args, {...options, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  child.output = '';
  child.on('error', error => {child.startError = error;});
  child.stdout.on('data', data => {child.output += data;});
  child.stderr.on('data', data => {child.output += data;});
  return child;
}
async function ready(child, url) {
  for (let i = 0; i < 150; i++) {
    if (child.startError || child.exitCode !== null) throw new Error('Temporary server failed to start.');
    try {if ((await fetch(url)).ok) return;} catch {}
    await delay(100);
  }
  throw new Error('Temporary server readiness timeout.');
}
async function stop(child) {
  if (!child || child.exitCode !== null || child.startError) return;
  const exited = once(child, 'exit'); child.kill(); await exited;
}
async function rows(name) {
  const response = await fetch(`${api}/${name}`);
  assert.equal(response.ok, true);
  return response.json();
}
try {
  for (const port of [apiPort, uiPort]) {
    const server = createServer(); server.listen(port, '127.0.0.1');
    await once(server, 'listening');
    await new Promise(resolve => server.close(resolve));
  }
  const build = start(process.execPath, ['node_modules/vite/bin/vite.js', 'build', '--outDir', join(temporary, 'dist')],
    {cwd: frontend, env: {...process.env, VITE_API_URL: api}});
  assert.equal((await once(build, 'exit'))[0], 0, 'Production build must pass');
  const python = join(root, '.venv-clean', 'Scripts', 'python.exe');
  backend = start(python, ['-c', 'import os; from pathlib import Path; from fastapi.middleware.cors import CORSMiddleware; import main, uvicorn; main.DB = Path(os.environ["TOGAS_TEST_DB"]); main.app.add_middleware(CORSMiddleware, allow_origins=[os.environ["TOGAS_TEST_ORIGIN"]], allow_methods=["*"], allow_headers=["*"]); uvicorn.run(main.app, host="127.0.0.1", port=18000)'],
    {cwd: join(root, 'backend'), env: {...process.env, TOGAS_AI_MODE: 'jev', TOGAS_TEST_DB: join(temporary, 'test.db'), TOGAS_TEST_ORIGIN: site}});
  preview = start(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--outDir', join(temporary, 'dist'), '--host', '127.0.0.1', '--port', String(uiPort), '--strictPort'], {cwd: frontend});
  await Promise.all([ready(backend, `${api}/health`), ready(preview, site)]);
  browser = await chromium.launch({channel: 'chrome', headless: true});
  const context = await browser.newContext({timezoneId: 'Asia/Seoul', viewport: {width: 1280, height: 900}});
  // Only one analysis submission is allowed, including after UI failures.
  await context.route('**/api/ai/analyze', route => {
    analyzeRequests++;
    return analyzeRequests === 1 ? route.continue() : route.abort();
  });
  page = await context.newPage(); page.setDefaultTimeout(15000);
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(site);
  await page.getByRole('button', {name: 'Journal', exact: true}).click();
  await page.getByText('Live Jev mode:', {exact: false}).waitFor();
  const text = 'I need to read my study notes today.';
  await page.getByRole('textbox', {name: 'Journal entry', exact: true}).fill(text);
  await page.getByRole('button', {name: 'Save journal', exact: true}).click();
  await page.locator('.journal-entry').getByText(text, {exact: true}).waitFor();
  assert.equal((await rows('journals')).length, 1);
  steps.push('Synthetic journal saved independently');
  const responsePromise = page.waitForResponse(response => response.url() === `${api}/ai/analyze` && response.request().method() === 'POST', {timeout: 40000});
  await page.getByRole('button', {name: 'Organize with Jev', exact: true}).click();
  const response = await responsePromise;
  assert.equal(response.ok(), true, 'Live analysis must succeed; no retry');
  analysis = await response.json();
  assert.equal(analysis.provider, 'jev');
  assert.equal(analysis.request_count, 1);
  assert.equal(analysis.cached, false);
  assert.equal(analysis.proposals.length, 1);
  await page.getByRole('heading', {name: 'Review suggestions', exact: true}).waitFor();
  assert.equal((await rows('tasks')).length, 0);
  await page.getByText('Analysis details', {exact: true}).click();
  await page.screenshot({path: join(artifacts, '01-live-review.png'), fullPage: true});
  steps.push('Real uncached Jev result displayed; no task created before approval');
  const title = 'Live workflow study task';
  await page.getByRole('textbox', {name: 'Task title', exact: true}).fill(title);
  await page.getByLabel('Urgency').selectOption('3');
  await page.getByText('Planning details', {exact: true}).click();
  await page.getByLabel('Importance (1–5)', {exact: true}).fill('5');
  await page.getByLabel('Estimated minutes (optional)', {exact: true}).fill('20');
  await page.getByRole('button', {name: 'Approve', exact: true}).click();
  await page.getByText('All suggestions reviewed.', {exact: false}).waitFor();
  const tasks = await rows('tasks'); assert.equal(tasks.length, 1); approved = tasks[0];
  assert.equal(approved.title, title); assert.ok(approved.journal_id);
  assert.equal((await rows('journals'))[0].id, approved.journal_id);
  steps.push('Edited proposal explicitly approved and linked to saved journal');
  await page.getByRole('button', {name: 'Today', exact: true}).click();
  const planner = page.getByRole('region', {name: 'Day planner'});
  await planner.getByLabel('Available start 1', {exact: true}).waitFor();
  while (await planner.getByRole('button', {name: /Remove window/}).count()) await planner.getByRole('button', {name: /Remove window/}).first().click();
  await planner.getByLabel('Available start 1', {exact: true}).fill('00:00');
  await planner.getByLabel('Available end 1', {exact: true}).fill('23:59');
  await planner.getByLabel('Maximum tasks per day', {exact: true}).fill('5');
  await planner.getByRole('button', {name: 'Save availability', exact: true}).click();
  await planner.getByText('Availability saved.', {exact: true}).waitFor();
  await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
  await planner.locator('.placement').getByText(title, {exact: true}).waitFor();
  await planner.getByText('Why this task?', {exact: true}).click();
  await planner.getByRole('button', {name: 'Confirm plan', exact: true}).click();
  await planner.getByText('Schedule confirmed.', {exact: true}).waitFor();
  await page.getByRole('heading', {name: 'Confirmed schedule', exact: true}).waitFor();
  steps.push('Availability saved; priority placement proposed and schedule confirmed');
  for (const width of [390, 1280]) {
    await page.setViewportSize({width, height: 900});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: join(artifacts, `02-today-${width}.png`), fullPage: true});
  }
  await page.getByRole('button', {name: 'Start focusing', exact: true}).click();
  await page.getByRole('heading', {name: 'One task at a time', exact: true}).waitFor();
  await page.screenshot({path: join(artifacts, '03-focus.png'), fullPage: true});
  await page.getByRole('button', {name: 'Mark as done', exact: true}).click();
  await page.getByText('1 of 1 tasks completed', {exact: false}).waitFor();
  await page.reload();
  await page.getByText('1 of 1 tasks completed', {exact: false}).waitFor();
  completed = (await rows('tasks'))[0];
  assert.equal(completed.done, 1); assert.ok(completed.scheduled_start);
  assert.equal((await rows('journals')).length, 1);
  await page.screenshot({path: join(artifacts, '04-completed.png'), fullPage: true});
  steps.push('Focus completion and dashboard count persisted after browser reload');
  assert.deepEqual(errors, []); assert.equal(analyzeRequests, 1);
  const report = {created_at: new Date().toISOString(), status: 'passed', steps, analysis_submissions: analyzeRequests, analysis, approved, completed, page_errors: errors, database: 'isolated temporary SQLite', screenshots: artifacts};
  await writeFile(join(root, 'backend/evaluation/live-workflow-results.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({status: 'passed', steps, model: analysis.model, usage: analysis.usage, analysis_latency_ms: analysis.analysis_latency_ms, artifacts}, null, 2));
} catch (error) {
  if (page) await page.screenshot({path: join(artifacts, 'failure.png'), fullPage: true}).catch(() => {});
  await writeFile(join(artifacts, 'failure.json'), JSON.stringify({steps, analysis_submissions: analyzeRequests, analysis, error: error.message, page_errors: errors}, null, 2));
  throw error;
} finally {
  await browser?.close(); await stop(preview); await stop(backend);
}
