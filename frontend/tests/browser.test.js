import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {createServer} from 'node:net';
import {mkdtemp, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {chromium} from 'playwright';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(frontend, '..');
const apiPort = Number(process.env.TOGAS_TEST_API_PORT || 8000);
const uiPort = Number(process.env.TOGAS_TEST_UI_PORT || 5173);
const api = `http://127.0.0.1:${apiPort}/api`;
const site = `http://127.0.0.1:${uiPort}`;

async function requireFreePort(port) {
  const server = createServer();
  server.listen(port, '127.0.0.1');
  try {
    await once(server, 'listening');
  } catch {
    throw new Error(`Port ${port} is already in use. Stop that server before running browser tests.`);
  }
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
}

function start(command, args, options) {
  const child = spawn(command, args, {...options, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  child.output = '';
  child.startError = null;
  child.on('error', error => {child.startError = error;});
  child.stdout.on('data', data => {child.output += data;});
  child.stderr.on('data', data => {child.output += data;});
  return child;
}

async function ready(child, url) {
  for (let i = 0; i < 150; i++) {
    if (child.startError || child.exitCode !== null) {
      throw new Error(`Test server failed: ${child.startError?.message ?? child.output}`);
    }
    try {
      if ((await fetch(url, {signal: AbortSignal.timeout(1000)})).ok) return;
    } catch {}
    await delay(100);
  }
  throw new Error(`Test server did not become ready: ${url}\n${child.output}`);
}

async function stop(child) {
  if (!child || child.exitCode !== null || child.startError) return;
  const exited = once(child, 'exit');
  child.kill();
  await exited;
}

test('production UI with real SQLite persistence and mocked AI', {timeout: 90000}, async t => {
  // Refuse to reuse a user's running servers or their database.
  await requireFreePort(apiPort);
  await requireFreePort(uiPort);
  const temporary = await mkdtemp(join(tmpdir(), 'togas-browser-'));
  let backend, preview, browser;
  try {
    const python = process.env.TOGAS_TEST_PYTHON ?? join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    backend = start(python, ['-c',
      'import os; from pathlib import Path; from fastapi.middleware.cors import CORSMiddleware; import main, uvicorn; main.DB = Path(os.environ["TOGAS_TEST_DB"]); main.app.add_middleware(CORSMiddleware, allow_origins=[os.environ["TOGAS_TEST_ORIGIN"]], allow_methods=["*"], allow_headers=["*"]); uvicorn.run(main.app, host="127.0.0.1", port=int(os.environ["TOGAS_TEST_API_PORT"]))',
    ], {cwd: join(root, 'backend'), env: {...process.env, TOGAS_TEST_DB: join(temporary, 'test.db'), TOGAS_TEST_API_PORT: String(apiPort), TOGAS_TEST_ORIGIN: site, TOGAS_AI_MODE: 'mock', HF_HUB_OFFLINE: '1'}});
    preview = start(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(uiPort), '--strictPort'], {cwd: frontend});
    await Promise.all([ready(backend, `${api}/health`), ready(preview, site)]);
    browser = await chromium.launch({channel: process.env.TOGAS_BROWSER_CHANNEL ?? 'chrome', headless: true});
    const context = await browser.newContext({timezoneId: 'Asia/Seoul'});
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    // Intercept all AI calls before they reach the backend. No model is invoked.
    await context.route('**/api/ai/**', route => route.fulfill({json: {proposals: [
      {title: 'Read NLP notes', category: 'study', urgency_score: 0, action_probability: 0.9, needs_review: false},
      {title: 'Rejected suggestion', category: 'personal', urgency_score: 1, action_probability: 0.6, needs_review: true},
    ]}}));
    await page.goto(site);
    await page.getByText('All caught up!').waitFor();

    await t.test('manual save failure retains input; retry saves once and survives reload', async () => {
      await page.getByRole('button', {name: 'Tasks', exact: true}).click();
      assert.equal(await page.getByRole('form', {name: 'New task', exact: true}).count(), 0);
      await page.getByRole('button', {name: 'Add task', exact: true}).click();
      const input = page.getByRole('textbox', {name: 'New task title'});
      await input.fill('Finish NLP assignment');
      await page.getByRole('button', {name: 'Close', exact: true}).click();
      assert.equal(await input.count(), 0);
      await page.getByRole('button', {name: 'Add task', exact: true}).click();
      assert.equal(await input.inputValue(), 'Finish NLP assignment');
      assert.equal(await input.evaluate(element => element === document.activeElement), true);
      const fail = route => route.request().method() === 'POST'
        ? route.fulfill({status: 503, json: {detail: 'Simulated save failure'}})
        : route.continue();
      await page.route('**/api/tasks', fail);
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      await page.getByText('Simulated save failure').waitFor();
      assert.equal(await input.inputValue(), 'Finish NLP assignment');
      await page.unroute('**/api/tasks', fail);
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      await page.locator('.task').getByText('Finish NLP assignment', {exact: true}).waitFor();
      assert.equal(await input.count(), 0);
      assert.equal(await page.getByRole('button', {name: 'Add task', exact: true}).getAttribute('aria-expanded'), 'false');
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, 1);
      await page.reload();
      await page.getByRole('button', {name: 'Tasks', exact: true}).click();
      await page.locator('.task').getByText('Finish NLP assignment', {exact: true}).waitFor();
    });

    await t.test('API validation errors are readable and preserve manual input', async () => {
      await page.getByRole('button', {name: 'Add task', exact: true}).click();
      const input = page.getByRole('textbox', {name: 'New task title'});
      assert.equal(await input.inputValue(), '');
      const tooLong = 'a'.repeat(251);
      await input.fill(tooLong);
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      const alert = page.locator('.alert').filter({hasText: '250'});
      await alert.waitFor();
      assert.match(await alert.innerText(), /title:/);
      assert.doesNotMatch(await alert.innerText(), /\[object Object\]/);
      assert.equal(await input.inputValue(), tooLong);
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, 1);
      await input.fill('');
      await page.getByRole('button', {name: 'Dismiss', exact: true}).click();
      await page.getByRole('button', {name: 'Close', exact: true}).click();
    });

    await t.test('completion, reopening, Focus, and dashboard counts work', async () => {
      // Completion is confirmed after PATCH + reload, rather than optimistically.
      await page.locator('.task input[type=checkbox]').click();
      await page.locator('.task .done').waitFor();
      await page.locator('.task input[type=checkbox]').click();
      await page.locator('.task .done').waitFor({state: 'detached'});
      await page.getByRole('button', {name: 'Today', exact: true}).click();
      await page.getByText('0 of 1 tasks completed').waitFor();
      await page.getByRole('button', {name: 'Start focusing'}).click();
      await page.getByRole('heading', {name: 'One task at a time'}).waitFor();
      await page.getByRole('button', {name: 'Mark as done'}).click();
      await page.getByText('1 of 1 tasks completed').waitFor();
    });

    await t.test('journal review rejects without saving and preserves an edited proposal after failure', async () => {
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.locator('textarea').fill('I need to read NLP notes. I might clean my room.');
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, 1);
      assert.equal((await (await fetch(`${api}/journals`)).json()).length, 1);
      await page.getByRole('button', {name: 'Reject', exact: true}).nth(1).click();
      assert.equal(await page.getByRole('textbox', {name: 'Task title', exact: true}).count(), 1);
      const title = page.getByRole('textbox', {name: 'Task title', exact: true});
      await title.fill('Read chapter 3');
      const fail = route => route.fulfill({status: 503, json: {detail: 'Simulated approval failure'}});
      await page.route('**/api/tasks', fail);
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await page.getByText('Simulated approval failure').waitFor();
      assert.equal(await title.inputValue(), 'Read chapter 3');
      await page.unroute('**/api/tasks', fail);
    });

    await t.test('pending approval blocks duplicates and stores urgency zero', async () => {
      let release;
      const gate = new Promise(resolve => {release = resolve;});
      let posts = 0;
      const hold = async route => {
        if (route.request().method() === 'POST') {
          posts++;
          assert.equal(route.request().postDataJSON().urgency_score, 0);
          await gate;
        }
        await route.continue();
      };
      await page.route('**/api/tasks', hold);
      try {
        await page.getByRole('button', {name: 'Approve', exact: true}).evaluate(button => {button.click(); button.click();});
        await page.getByRole('status').waitFor();
        assert.equal(await page.getByRole('button', {name: 'Approve', exact: true}).isDisabled(), true);
        assert.equal(await page.getByRole('button', {name: 'Reject', exact: true}).isDisabled(), true);
        assert.equal(await page.getByRole('textbox', {name: 'Task title', exact: true}).isDisabled(), true);
      } finally { release(); }
      await page.getByRole('textbox', {name: 'Task title', exact: true}).waitFor({state: 'detached'});
      await page.unroute('**/api/tasks', hold);
      assert.equal(posts, 1);
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.length, 2);
      assert.equal(tasks.find(task => task.title === 'Read chapter 3').urgency_score, 0);
      assert.equal(tasks.some(task => task.title === 'Rejected suggestion'), false);
    });

    await t.test('mobile layout fits the viewport; deletion persists', async () => {
      await page.setViewportSize({width: 390, height: 844});
      await page.getByRole('button', {name: 'Go to Tasks'}).click();
      await page.locator('.task').getByText('Read chapter 3', {exact: true}).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await mkdir(join(frontend, 'test-results'), {recursive: true});
      await page.screenshot({path: join(frontend, 'test-results', 'mobile-tasks.png'), fullPage: true});
      await page.locator('.task').filter({hasText: 'Read chapter 3'}).getByRole('button', {name: 'Delete'}).click();
      await page.locator('.task').filter({hasText: 'Read chapter 3'}).waitFor({state: 'detached'});
      await page.reload();
      await page.getByRole('button', {name: 'Tasks', exact: true}).click();
      await page.locator('.task').getByText('Finish NLP assignment', {exact: true}).waitFor();
      assert.equal(await page.locator('.task').count(), 1);
      assert.deepEqual(pageErrors, []);
    });

    await t.test('independent journal save preserves failed input and avoids duplicate analysis retries', async () => {
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.locator('textarea').fill('Plan internship tasks tomorrow.');
      assert.equal(await page.getByRole('button', {name: 'New entry', exact: true}).isDisabled(), true);
      await page.locator('.journal-entry').first().getByRole('button', {name: 'Open entry'}).click();
      await page.getByText('Save your current journal before opening another entry.').waitFor();
      assert.equal(await page.locator('textarea').inputValue(), 'Plan internship tasks tomorrow.');
      const failSave = route => route.request().method() === 'POST'
        ? route.fulfill({status: 503, json: {detail: 'Simulated journal save failure'}}) : route.continue();
      await page.route('**/api/journals', failSave);
      await page.getByRole('button', {name: 'Save journal', exact: true}).click();
      await page.getByText('Simulated journal save failure').waitFor();
      assert.equal(await page.locator('textarea').inputValue(), 'Plan internship tasks tomorrow.');
      await page.unroute('**/api/journals', failSave);
      await page.getByRole('button', {name: 'Save journal', exact: true}).click();
      await page.getByRole('status').filter({hasText: 'Journal saved.'}).waitFor();
      assert.equal((await (await fetch(`${api}/journals`)).json()).length, 2);
      assert.equal(await page.getByRole('button', {name: 'New entry', exact: true}).isDisabled(), false);
      const failAnalysis = route => route.fulfill({status: 503, json: {detail: 'Simulated analysis failure'}});
      await page.route('**/api/ai/analyze', failAnalysis);
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByText('Simulated analysis failure').waitFor();
      assert.equal((await (await fetch(`${api}/journals`)).json()).length, 2);
      await page.unroute('**/api/ai/analyze', failAnalysis);
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      assert.equal((await (await fetch(`${api}/journals`)).json()).length, 2);
      while (await page.getByRole('button', {name: 'Reject', exact: true}).count()) await page.getByRole('button', {name: 'Reject', exact: true}).first().click();
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.locator('.journal-entry').filter({hasText: 'Plan internship tasks tomorrow.'}).getByRole('button', {name: 'Open entry'}).click();
      assert.equal(await page.locator('textarea').inputValue(), 'Plan internship tasks tomorrow.');
      await page.getByRole('button', {name: 'Save journal', exact: true}).click();
      await page.getByRole('status').filter({hasText: 'Journal saved.'}).waitFor();
      assert.equal((await (await fetch(`${api}/journals`)).json()).length, 2);
    });

    await t.test('task editing supports cancel, failed save, category, urgency and deadline', async () => {
      await page.getByRole('button', {name: 'Tasks', exact: true}).click();
      await page.getByRole('button', {name: 'Add task', exact: true}).click();
      await page.getByRole('textbox', {name: 'New task title'}).fill('Prepare internship report');
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      let row = page.locator('.task').filter({hasText: 'Prepare internship report'});
      await row.getByRole('button', {name: 'Edit', exact: true}).click();
      let form = page.getByRole('form', {name: 'Edit Prepare internship report', exact: true});
      await form.getByRole('textbox', {name: 'Edit task title'}).fill('Discard this title');
      await form.getByRole('button', {name: 'Cancel', exact: true}).click();
      await row.getByText('Prepare internship report', {exact: true}).waitFor();
      await row.getByRole('button', {name: 'Edit', exact: true}).click();
      form = page.getByRole('form', {name: 'Edit Prepare internship report', exact: true});
      await form.getByRole('textbox', {name: 'Edit task title'}).fill('Updated internship report');
      await form.getByLabel('Category').selectOption('work');
      await form.getByLabel('Urgency').selectOption('3');
      await form.getByLabel('Due date').fill('2026-11-01');
      const task = (await (await fetch(`${api}/tasks`)).json()).find(task => task.title === 'Prepare internship report');
      const failEdit = route => route.fulfill({status: 503, json: {detail: 'Simulated edit failure'}});
      await page.route(`**/api/tasks/${task.id}`, failEdit);
      await form.getByRole('button', {name: 'Save changes'}).click();
      await page.getByText('Simulated edit failure').waitFor();
      assert.equal(await form.getByRole('textbox', {name: 'Edit task title'}).inputValue(), 'Updated internship report');
      await page.unroute(`**/api/tasks/${task.id}`, failEdit);
      await form.getByRole('button', {name: 'Save changes'}).click();
      row = page.locator('.task').filter({hasText: 'Updated internship report'});
      await row.waitFor();
      const updated = (await (await fetch(`${api}/tasks`)).json()).find(item => item.id === task.id);
      assert.equal(updated.category, 'work');
      assert.equal(updated.urgency_score, 3);
      assert.equal(updated.due_date, '2026-11-01');
      await page.getByRole('button', {name: 'Today', exact: true}).click();
      await page.getByRole('heading', {name: 'Updated internship report', exact: true}).waitFor();
      await page.getByText('Overdue tasks come first.', {exact: false}).waitFor();
    });

    await t.test('search finds both data types and Focus remains open on completion failure', async () => {
      await page.getByRole('button', {name: 'Search', exact: true}).click();
      await page.getByRole('searchbox', {name: 'Search tasks and journals'}).fill('internship');
      await page.getByRole('heading', {name: 'Tasks (1)', exact: true}).waitFor();
      await page.getByRole('heading', {name: 'Journals (1)', exact: true}).waitFor();
      await page.getByRole('button', {name: 'Start focusing'}).click();
      const task = (await (await fetch(`${api}/tasks`)).json()).find(task => task.title === 'Updated internship report');
      const fail = route => route.fulfill({status: 503, json: {detail: 'Simulated completion failure'}});
      await page.route(`**/api/tasks/${task.id}`, fail);
      await page.getByRole('button', {name: 'Mark as done'}).click();
      await page.getByText('Simulated completion failure').waitFor();
      await page.getByRole('heading', {name: 'One task at a time'}).waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).find(item => item.id === task.id).done, 0);
      await page.unroute(`**/api/tasks/${task.id}`, fail);
      await page.getByRole('button', {name: 'Mark as done'}).click();
      await page.getByRole('heading', {name: "Let's get things done."}).waitFor();
    });

    await t.test('real backend mock mode extracts reviewable dates without storing unapproved tasks', async () => {
      await context.unroute('**/api/ai/**');
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.locator('textarea').fill('I need to read NLP notes tomorrow. I feel tired.');
      const response = page.waitForResponse(response => response.url().endsWith('/api/ai/analyze'));
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      const analysis = await (await response).json();
      assert.equal(analysis.provider, 'mock');
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      assert.equal(await page.getByRole('textbox', {name: 'Task title', exact: true}).count(), 1);
      assert.ok(await page.getByLabel('Due date').inputValue());
      const before = (await (await fetch(`${api}/tasks`)).json()).length;
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await page.getByRole('textbox', {name: 'Task title', exact: true}).waitFor({state: 'detached'});
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.length, before + 1);
      const approved = tasks.find(task => task.title === 'I need to read NLP notes tomorrow.');
      assert.ok(approved.journal_id);
      assert.ok(approved.due_date);
      await page.getByRole('button', {name: 'Go to Tasks'}).click();
      const row = page.locator('.task').filter({hasText: approved.title});
      await row.getByRole('button', {name: 'Edit', exact: true}).click();
      const form = page.getByRole('form', {name: `Edit ${approved.title}`, exact: true});
      await form.getByLabel('Due date').fill('');
      await form.getByRole('button', {name: 'Save changes'}).click();
      await row.waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).find(task => task.id === approved.id).due_date, null);
    });

    await t.test('future tasks stay out of Today and layouts fit mobile and desktop', async () => {
      await page.getByRole('button', {name: 'Add task', exact: true}).click();
      await page.getByRole('textbox', {name: 'New task title'}).fill('Future-only task');
      await page.locator('form').getByLabel('Due date').fill('2030-01-01');
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      await page.locator('.task').getByText('Future-only task', {exact: true}).waitFor();
      await page.getByRole('button', {name: 'Today', exact: true}).click();
      await page.getByRole('heading', {name: "Today's tasks", exact: true}).waitFor();
      assert.equal(await page.locator('.task').filter({hasText: 'Future-only task'}).count(), 0);
      for (const width of [320, 390, 1280]) {
        await page.setViewportSize({width, height: 900});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      }
      await page.screenshot({path: join(frontend, 'test-results', 'desktop-today.png'), fullPage: true});
      await page.setViewportSize({width: 390, height: 844});
      await page.screenshot({path: join(frontend, 'test-results', 'mobile-today.png'), fullPage: true});
      assert.deepEqual(pageErrors, []);
    });
    await t.test('live-mode labels and confidence review work with an intercepted hosted response', async () => {
      const livePage = await context.newPage();
      livePage.setDefaultTimeout(10000);
      let intercepted = 0;
      livePage.on('pageerror', error => pageErrors.push(error.message));
      await livePage.route('**/api/health', route => route.fulfill({json: {status: 'ok', ai_mode: 'jev'}}));
      await livePage.route('**/api/ai/analyze', route => {
        intercepted++;
        return route.fulfill({json: {
          provider: 'jev', model: 'jev-test-fixture', request_count: 0, cached: true,
          usage: {input_tokens: 100, output_tokens: 10}, warnings: [],
          proposals: [{title: 'Meet my friend tomorrow.', category: 'personal', urgency_score: 1.88, due_date: '2026-11-13', action_probability: 0.98, category_confidence: 0.91, urgency_confidence: 0.48, needs_review: true}],
        }});
      });
      try {
        await livePage.goto(site);
        await livePage.getByRole('button', {name: 'Journal', exact: true}).click();
        await livePage.getByText('Live Jev mode:', {exact: false}).waitFor();
        await livePage.locator('textarea').fill('Meet my friend tomorrow.');
        await livePage.getByRole('button', {name: 'Organize with Jev', exact: true}).click();
        await livePage.getByRole('heading', {name: 'Review suggestions'}).waitFor();
        assert.equal(await livePage.getByLabel('Urgency').inputValue(), '1.88');
        assert.equal(await livePage.getByLabel('Urgency').locator('option:checked').innerText(), 'Suggested: 1.88 / 3');
        await livePage.getByText('Reused a recent Jev analysis. No new API request was made.').waitFor();
        await livePage.getByText('Prediction details', {exact: true}).click();
        await livePage.getByText('urgency confidence: 48%', {exact: false}).waitFor();
        await livePage.getByText('Needs review — uncertain prediction', {exact: true}).waitFor();
        assert.equal(intercepted, 1);
        const before = (await (await fetch(`${api}/tasks`)).json()).length;
        await livePage.getByRole('button', {name: 'Approve', exact: true}).click();
        await livePage.getByRole('textbox', {name: 'Task title', exact: true}).waitFor({state: 'detached'});
        assert.equal((await (await fetch(`${api}/tasks`)).json()).length, before + 1);
        assert.equal((await (await fetch(`${api}/tasks`)).json()).find(task => task.title === 'Meet my friend tomorrow.').urgency_score, 1.88);
        assert.deepEqual(pageErrors, []);
      } finally { await livePage.close(); }
    });

    await t.test('journal retry after a committed but lost response creates no duplicate', async () => {
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.getByRole('button', {name: 'New entry', exact: true}).click();
      await page.locator('textarea').fill('Read the journal retry notes.');
      const before = (await (await fetch(`${api}/journals`)).json()).length;
      let committedId;
      const loseResponse = async route => {
        if (route.request().method() !== 'POST') return route.continue();
        assert.ok(route.request().postDataJSON().request_id);
        const response = await route.fetch();
        committedId = (await response.json()).id;
        await route.abort('failed');
      };
      await page.route('**/api/journals', loseResponse);
      await page.getByRole('button', {name: 'Save journal', exact: true}).click();
      await page.getByRole('alert').waitFor();
      assert.equal(await page.locator('textarea').inputValue(), 'Read the journal retry notes.');
      assert.equal((await (await fetch(`${api}/journals`)).json()).length, before + 1);
      await page.unroute('**/api/journals', loseResponse);
      await page.getByRole('button', {name: 'Save journal', exact: true}).click();
      await page.getByRole('status').filter({hasText: 'Journal saved.'}).waitFor();
      const entries = await (await fetch(`${api}/journals`)).json();
      assert.equal(entries.length, before + 1);
      assert.equal(entries.find(entry => entry.content === 'Read the journal retry notes.').id, committedId);
      const entry = page.locator('.journal-entry').filter({hasText: 'Read the journal retry notes.'});
      assert.equal(await entry.count(), 1);
      await entry.getByRole('button', {name: 'Open entry'}).click();
      await page.waitForFunction(() => {
        const editor = document.getElementById('journal-text');
        const rect = editor.getBoundingClientRect();
        return document.activeElement === editor && rect.top >= 0 && rect.bottom <= innerHeight;
      });
    });

    await t.test('empty analysis explains that the journal is safe and returns to the editor', async () => {
      await page.getByRole('button', {name: 'New entry', exact: true}).click();
      await page.locator('textarea').fill('I feel tired.');
      const before = (await (await fetch(`${api}/tasks`)).json()).length;
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByText('No actionable tasks were found.', {exact: false}).waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, before);
      await page.getByRole('button', {name: 'Back to journal', exact: true}).click();
      assert.equal(await page.locator('textarea').inputValue(), 'I feel tired.');
      assert.equal(await page.locator('textarea').evaluate(editor => editor === document.activeElement), true);
    });

    await t.test('review shows original text and reasons and preserves edits while navigating', async () => {
      await page.getByRole('button', {name: 'New entry', exact: true}).click();
      await page.locator('textarea').fill('Visit Dr. Kim tomorrow. I feel tired.');
      const before = (await (await fetch(`${api}/tasks`)).json()).length;
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      assert.equal(await page.getByRole('textbox', {name: 'Task title', exact: true}).count(), 1);
      await page.getByText('Original journal text', {exact: true}).click();
      await page.locator('.source-text').getByText('Visit Dr. Kim tomorrow.', {exact: true}).waitFor();
      assert.match(await page.locator('.review-reasons').innerText(), /demo suggestion/);
      await page.getByRole('textbox', {name: 'Task title', exact: true}).fill('Doctor appointment');
      await page.getByLabel('Category').selectOption('health');
      await page.getByRole('button', {name: 'Go to Tasks'}).click();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, before);
      await page.getByRole('button', {name: 'Review suggestions (1)', exact: true}).click();
      assert.equal(await page.getByRole('textbox', {name: 'Task title', exact: true}).inputValue(), 'Doctor appointment');
      assert.equal(await page.getByLabel('Category').inputValue(), 'health');
      await page.getByText('Original journal text', {exact: true}).click();
      await page.screenshot({path: join(frontend, 'test-results', 'day2-review.png'), fullPage: true});
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await page.getByText('All suggestions reviewed.', {exact: false}).waitFor();
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.length, before + 1);
      assert.equal(tasks.find(task => task.title === 'Doctor appointment').category, 'health');
      assert.deepEqual(pageErrors, []);
    });
    await t.test('manual retry after a committed but lost response saves once, including after workspace refresh', async () => {
      await page.getByRole('button', {name: 'Tasks', exact: true}).click();
      await page.getByRole('button', {name: 'Add task', exact: true}).click();
      await page.getByRole('textbox', {name: 'New task title'}).fill('Day 3 retry-safe manual task');
      const before = (await (await fetch(`${api}/tasks`)).json()).length;
      let token, committedId;
      const loseResponse = async route => {
        if (route.request().method() !== 'POST') return route.continue();
        token = route.request().postDataJSON().request_id;
        assert.ok(token);
        committedId = (await (await route.fetch()).json()).id;
        await route.abort('failed');
      };
      await page.route('**/api/tasks', loseResponse);
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      await page.getByRole('alert').waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, before + 1);
      await page.unroute('**/api/tasks', loseResponse);
      await page.getByRole('button', {name: 'Reload workspace', exact: true}).click();
      const row = page.locator('.task').filter({hasText: 'Day 3 retry-safe manual task'});
      await row.waitFor();
      const retry = page.waitForRequest(request => request.method() === 'POST' && request.url().endsWith('/api/tasks'));
      await page.getByRole('button', {name: 'Add', exact: true}).click();
      assert.equal((await retry).postDataJSON().request_id, token);
      await page.getByRole('form', {name: 'New task', exact: true}).waitFor({state: 'detached'});
      assert.equal(await row.count(), 1);
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.length, before + 1);
      assert.equal(tasks.find(task => task.title === 'Day 3 retry-safe manual task').id, committedId);
    });

    await t.test('approval retry after a lost response preserves edits and creates one linked task', async () => {
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.getByRole('button', {name: 'New entry', exact: true}).click();
      await page.locator('textarea').fill('Read Day 3 notes tomorrow.');
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      const input = page.getByRole('textbox', {name: 'Task title', exact: true});
      await input.fill('Edited Day 3 study task');
      await page.getByLabel('Urgency').selectOption('0');
      const before = (await (await fetch(`${api}/tasks`)).json()).length;
      const loseResponse = async route => {
        if (route.request().method() !== 'POST') return route.continue();
        await route.fetch();
        await route.abort('failed');
      };
      await page.route('**/api/tasks', loseResponse);
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await page.getByRole('alert').waitFor();
      assert.equal(await input.inputValue(), 'Edited Day 3 study task');
      await page.unroute('**/api/tasks', loseResponse);
      await page.getByRole('button', {name: 'Approve', exact: true}).click();
      await page.getByText('All suggestions reviewed.', {exact: false}).waitFor();
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.length, before + 1);
      const saved = tasks.find(task => task.title === 'Edited Day 3 study task');
      assert.equal(saved.urgency_score, 0);
      assert.ok(saved.journal_id);
      assert.ok(saved.due_date);
      assert.deepEqual(pageErrors, []);
    });

    await t.test('stabilized extraction handles cooking and action lists while keeping original text and explicit review', async () => {
      await page.getByRole('button', {name: 'Journal', exact: true}).click();
      await page.getByRole('button', {name: 'New entry', exact: true}).click();
      await page.locator('textarea').fill('meet friend. cook for tonight.');
      const before = (await (await fetch(`${api}/tasks`)).json()).length;
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      assert.deepEqual(await page.getByRole('textbox', {name: 'Task title', exact: true}).evaluateAll(inputs => inputs.map(input => input.value)), ['meet friend.', 'cook for tonight.']);
      assert.equal((await (await fetch(`${api}/tasks`)).json()).length, before);
      while (await page.getByRole('button', {name: 'Reject', exact: true}).count()) await page.getByRole('button', {name: 'Reject', exact: true}).first().click();
      await page.getByRole('button', {name: 'Back to journal', exact: true}).click();
      await page.getByRole('button', {name: 'New entry', exact: true}).click();
      const text = 'Study Python, cook dinner, and call my mother.';
      await page.locator('textarea').fill(text);
      await page.getByRole('button', {name: 'Preview suggestions'}).click();
      await page.getByRole('heading', {name: 'Review suggestions'}).waitFor();
      const titles = page.getByRole('textbox', {name: 'Task title', exact: true});
      assert.deepEqual(await titles.evaluateAll(inputs => inputs.map(input => input.value)), ['Study Python', 'cook dinner', 'call my mother.']);
      assert.equal(await page.locator('.source-text').count(), 3);
      assert.equal(await page.locator('.source-text p').evaluateAll(nodes => nodes.every(node => node.textContent === 'Study Python, cook dinner, and call my mother.')), true);
      assert.match(await page.locator('.review-reasons').first().innerText(), /Multiple actions/);
      await titles.first().fill('Study Python chapter 2');
      await page.getByRole('button', {name: 'Approve', exact: true}).first().click();
      await titles.nth(1).waitFor({state: 'visible'});
      while (await page.getByRole('button', {name: 'Reject', exact: true}).count()) await page.getByRole('button', {name: 'Reject', exact: true}).first().click();
      await page.getByText('All suggestions reviewed.', {exact: false}).waitFor();
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.length, before + 1);
      assert.ok(tasks.find(task => task.title === 'Study Python chapter 2').journal_id);
      assert.ok((await (await fetch(`${api}/journals`)).json()).some(entry => entry.content === text));
      assert.deepEqual(pageErrors, []);
    });

    let planningPage, planningFirst, planningSecond;
    await t.test('Day 3 metadata editing, persistent multiple windows and rejection work', async () => {
      planningFirst = await (await fetch(`${api}/tasks`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: 'Day3 first scheduled task', urgency_score: 3, importance: 5, estimated_minutes: 45})})).json();
      planningSecond = await (await fetch(`${api}/tasks`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: 'Day3 second provisional task', urgency_score: 3, importance: 4})})).json();
      planningPage = await context.newPage();
      planningPage.setDefaultTimeout(10000);
      planningPage.on('pageerror', error => pageErrors.push(error.message));
      await planningPage.clock.install({time: new Date('2031-02-10T00:00:00Z')});
      await planningPage.goto(site);
      const planner = planningPage.getByRole('region', {name: 'Day planner'});
      await planner.getByLabel('Available start 1').fill('09:00');
      await planner.getByLabel('Available end 1').fill('10:00');
      await planner.getByRole('button', {name: 'Add time window', exact: true}).click();
      await planner.getByLabel('Available end 2').fill('14:00');
      await planner.getByLabel('Maximum tasks per day').fill('2');
      const failAvailability = route => route.fulfill({status: 503, json: {detail: 'Simulated availability failure'}});
      await planningPage.route('**/api/availability', failAvailability);
      await planner.getByRole('button', {name: 'Save availability', exact: true}).click();
      await planner.getByText('Simulated availability failure', {exact: false}).waitFor();
      assert.equal(await planner.getByLabel('Available end 2').inputValue(), '14:00');
      await planningPage.unroute('**/api/availability', failAvailability);
      await planner.getByRole('button', {name: 'Save availability', exact: true}).click();
      await planner.getByText('Availability saved.', {exact: true}).waitFor();
      const saved = await (await fetch(`${api}/availability?date=2031-02-10`)).json();
      assert.equal(saved.windows.length, 2);
      assert.equal(saved.max_tasks, 2);
      await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
      await planner.getByRole('heading', {name: 'Proposed schedule', exact: true}).waitFor();
      assert.equal(await planner.locator('.placement').count(), 2);
      await planner.getByText('13:00–13:30 · 30 min (provisional estimate)', {exact: true}).waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).find(task => task.id === planningFirst.id).scheduled_start, null);
      await planner.getByRole('button', {name: 'Reject plan', exact: true}).click();
      await planner.getByText('Plan rejected. Task times are unchanged.', {exact: true}).waitFor();
      assert.equal((await (await fetch(`${api}/tasks`)).json()).find(task => task.id === planningFirst.id).scheduled_start, null);
    });

    await t.test('Day 3 confirmation recovers from a lost committed response and Today stays chronological', async () => {
      const planner = planningPage.getByRole('region', {name: 'Day planner'});
      await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
      await planner.getByRole('button', {name: 'Confirm plan', exact: true}).waitFor();
      let postedPlan;
      const loseConfirmation = async route => {
        postedPlan = route.request().postDataJSON().plan;
        const response = await route.fetch();
        assert.equal(response.status(), 200);
        await route.abort('failed');
      };
      await planningPage.route('**/api/planning/confirm', loseConfirmation);
      await planner.getByRole('button', {name: 'Confirm plan', exact: true}).click();
      await planner.getByRole('alert').waitFor();
      await planningPage.unroute('**/api/planning/confirm', loseConfirmation);
      const retry = planningPage.waitForRequest(request => request.url().endsWith('/planning/confirm'));
      await planner.getByRole('button', {name: 'Confirm plan', exact: true}).click();
      assert.equal((await retry).postDataJSON().plan.plan_id, postedPlan.plan_id);
      await planner.getByText('Schedule confirmed.', {exact: true}).waitFor();
      await planningPage.getByRole('heading', {name: 'Confirmed schedule', exact: true}).waitFor();
      const rows = planningPage.locator('.task').filter({hasText: /Day3 (first scheduled|second provisional) task/});
      assert.deepEqual(await rows.locator('.task-content span').allTextContents(), ['Day3 first scheduled task', 'Day3 second provisional task']);
      assert.match(await rows.nth(1).innerText(), /30 min \(provisional\)/);
      const tasks = await (await fetch(`${api}/tasks`)).json();
      assert.equal(tasks.find(task => task.id === planningSecond.id).estimated_minutes, null);
      await planningPage.reload();
      await planningPage.getByRole('heading', {name: 'Confirmed schedule', exact: true}).waitFor();
      assert.equal(await planningPage.getByLabel('Available end 2').inputValue(), '14:00');
    });

    await t.test('Day 3 scheduled edits preserve times, reject overlaps and support Focus completion', async () => {
      const row = planningPage.locator('.task').filter({hasText: 'Day3 first scheduled task'});
      await row.getByRole('button', {name: 'Edit', exact: true}).click();
      const form = planningPage.getByRole('form', {name: 'Edit Day3 first scheduled task', exact: true});
      await form.getByText('Planning details', {exact: true}).click();
      await form.getByLabel('Estimated minutes (optional)', {exact: true}).fill('270');
      await form.getByRole('button', {name: 'Save changes', exact: true}).click();
      await planningPage.getByRole('alert').filter({hasText: 'overlaps a confirmed task'}).waitFor();
      assert.equal(await form.getByLabel('Estimated minutes (optional)', {exact: true}).inputValue(), '270');
      await form.getByLabel('Estimated minutes (optional)', {exact: true}).fill('50');
      await form.getByLabel('Importance (1–5)', {exact: true}).fill('4');
      await form.getByLabel('Effort (1–5)', {exact: true}).fill('2');
      await form.getByRole('button', {name: 'Save changes', exact: true}).click();
      await row.waitFor();
      let saved = (await (await fetch(`${api}/tasks`)).json()).find(task => task.id === planningFirst.id);
      assert.equal(saved.scheduled_start, '2031-02-10T09:00:00');
      assert.equal(saved.estimated_minutes, 50);
      assert.equal(saved.effort_level, 2);
      await planningPage.getByRole('button', {name: 'Search', exact: true}).click();
      await planningPage.getByRole('searchbox', {name: 'Search tasks and journals'}).fill('Day3 first scheduled task');
      await planningPage.getByRole('heading', {name: 'Tasks (1)', exact: true}).waitFor();
      await planningPage.getByRole('button', {name: 'Start focusing', exact: true}).click();
      await planningPage.getByRole('button', {name: 'Mark as done', exact: true}).click();
      await planningPage.getByRole('heading', {name: "Let's get things done.", exact: true}).waitFor();
      saved = (await (await fetch(`${api}/tasks`)).json()).find(task => task.id === planningFirst.id);
      assert.equal(saved.done, 1);
      assert.equal(saved.scheduled_start, '2031-02-10T09:00:00');
      for (const width of [320, 390, 1280]) {
        await planningPage.setViewportSize({width, height: 900});
        assert.equal(await planningPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        if (width === 390) await planningPage.screenshot({path: join(frontend, 'test-results', 'day3-planner-mobile.png'), fullPage: true});
      }
      await planningPage.screenshot({path: join(frontend, 'test-results', 'day3-planner.png'), fullPage: true});
      assert.deepEqual(pageErrors, []);
      await planningPage.close();
    });

    await t.test('Day 3 stale confirmation explains the conflict and supports regeneration', async () => {
      const third = await (await fetch(`${api}/tasks`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: 'Day3 stale candidate', urgency_score: 3, importance: 5, estimated_minutes: 15})})).json();
      await fetch(`${api}/availability`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({date: '2031-02-10', windows: [{start: '09:00', end: '10:00'}, {start: '13:00', end: '14:00'}], max_tasks: 3})});
      const stalePage = await context.newPage();
      stalePage.setDefaultTimeout(10000);
      stalePage.on('pageerror', error => pageErrors.push(error.message));
      try {
        await stalePage.clock.install({time: new Date('2031-02-10T00:00:00Z')});
        await stalePage.goto(site);
        const planner = stalePage.getByRole('region', {name: 'Day planner'});
        await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
        await planner.getByRole('button', {name: 'Confirm plan', exact: true}).waitFor();
        await fetch(`${api}/tasks/${third.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title: 'Day3 changed candidate'})});
        await planner.getByRole('button', {name: 'Confirm plan', exact: true}).click();
        await planner.getByRole('alert').filter({hasText: 'Tasks or availability changed'}).waitFor();
        assert.equal((await (await fetch(`${api}/tasks`)).json()).find(task => task.id === third.id).scheduled_start, null);
        await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
        await planner.locator('.placement').getByText('Day3 changed candidate', {exact: true}).waitFor();
        await planner.getByRole('button', {name: 'Confirm plan', exact: true}).click();
        await planner.getByText('Schedule confirmed.', {exact: true}).waitFor();
        assert.equal((await (await fetch(`${api}/tasks`)).json()).find(task => task.id === third.id).scheduled_start, '2031-02-10T13:30:00');
        assert.deepEqual(pageErrors, []);
      } finally {await stalePage.close();}
    });

    await t.test('Day 4 review shows missing confidence honestly and retries a manual missing task safely', async () => {
      const reviewPage = await context.newPage();
      reviewPage.setDefaultTimeout(10000);
      reviewPage.on('pageerror', error => pageErrors.push(error.message));
      await reviewPage.route('**/api/health', route => route.fulfill({json: {status: 'ok', ai_mode: 'jev'}}));
      await reviewPage.route('**/api/ai/analyze', route => route.fulfill({json: {
        provider: 'jev', model: 'jev-day4-test-fixture', usage: {input_tokens: 123, output_tokens: 45}, analysis_latency_ms: 9.2,
        cached: false, request_count: 1, warnings: [], proposals: [{title: 'Day4 fixture candidate', action_probability: 0.64,
          category: 'other', urgency_score: 1, category_confidence: null, urgency_confidence: null,
          source_text: 'A synthetic fixture journal.', needs_review: true, review_reasons: ['The suggested category is uncertain.']}],
      }}));
      try {
        await reviewPage.goto(site);
        await reviewPage.getByRole('button', {name: 'Journal', exact: true}).click();
        await reviewPage.locator('textarea').fill('A synthetic fixture journal.');
        await reviewPage.getByRole('button', {name: 'Organize with Jev', exact: true}).click();
        await reviewPage.getByRole('heading', {name: 'Review suggestions', exact: true}).waitFor();
        await reviewPage.getByText('Extracted 1 task suggestion.', {exact: true}).waitFor();
        await reviewPage.getByText('Prediction details', {exact: true}).click();
        await reviewPage.getByText('category confidence: not provided', {exact: false}).waitFor();
        assert.doesNotMatch(await reviewPage.locator('main').innerText(), /NaN%|0%/);
        await reviewPage.getByText('Analysis details', {exact: true}).click();
        await reviewPage.getByText('Model: jev-day4-test-fixture', {exact: false}).waitFor();
        await reviewPage.getByRole('button', {name: 'Add a missing task', exact: true}).click();
        const form = reviewPage.getByRole('form', {name: 'Missing task', exact: true});
        await form.getByRole('textbox', {name: 'Missing task title', exact: true}).fill('Day4 missed manual task');
        await form.getByLabel('Category').selectOption('work');
        const before = (await (await fetch(`${api}/tasks`)).json()).length;
        const loseResponse = async route => {
          if (route.request().method() !== 'POST') return route.continue();
          await route.fetch(); await route.abort('failed');
        };
        await reviewPage.route('**/api/tasks', loseResponse);
        await form.getByRole('button', {name: 'Approve manual task', exact: true}).click();
        await reviewPage.getByRole('alert').waitFor();
        assert.equal(await form.getByRole('textbox', {name: 'Missing task title', exact: true}).inputValue(), 'Day4 missed manual task');
        await reviewPage.unroute('**/api/tasks', loseResponse);
        await form.getByRole('button', {name: 'Approve manual task', exact: true}).click();
        await form.waitFor({state: 'detached'});
        const tasks = await (await fetch(`${api}/tasks`)).json();
        assert.equal(tasks.length, before + 1);
        const saved = tasks.find(task => task.title === 'Day4 missed manual task');
        assert.ok(saved.journal_id);
        assert.equal(saved.category, 'work');
        await reviewPage.getByRole('button', {name: 'Reject', exact: true}).click();
        await reviewPage.getByRole('button', {name: 'Go to Tasks', exact: true}).click();
        await reviewPage.getByLabel('Task filter').selectOption('completed');
        assert.equal(await reviewPage.locator('.task').filter({hasText: saved.title}).count(), 0);
        assert.equal(await reviewPage.locator('.task input[type=checkbox]').evaluateAll(nodes => nodes.every(node => node.checked)), true);
        await reviewPage.getByLabel('Task filter').selectOption('unscheduled');
        await reviewPage.locator('.task').getByText(saved.title, {exact: true}).waitFor();
        await reviewPage.getByLabel('Task filter').selectOption('scheduled');
        assert.equal(await reviewPage.locator('.task').filter({hasText: saved.title}).count(), 0);
        await reviewPage.getByLabel('Task filter').selectOption('all');
        for (const width of [320, 390, 1280]) {
          await reviewPage.setViewportSize({width, height: 900});
          assert.equal(await reviewPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        }
        assert.deepEqual(pageErrors, []);
      } finally {await reviewPage.close();}
    });

    await t.test('Day 4 journal to review, priority, confirmed schedule and Focus completion works end to end', async () => {
      // Complete earlier synthetic fixtures in this temporary database so the
      // next-task recommendation for this scenario is unambiguous.
      for (const task of await (await fetch(`${api}/tasks`)).json()) {
        if (!task.done) await fetch(`${api}/tasks/${task.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({done: true})});
      }
      // Isolate this real-date flow from the Day 3 scenarios' fixed clocks.
      const flowContext = await browser.newContext({timezoneId: 'Asia/Seoul'});
      const flowPage = await flowContext.newPage();
      flowPage.setDefaultTimeout(10000);
      flowPage.on('pageerror', error => pageErrors.push(error.message));
      try {
        await flowPage.goto(site);
        await flowPage.getByRole('button', {name: 'Journal', exact: true}).click();
        const text = 'I need to read Day4 notes today.';
        await flowPage.locator('textarea').fill(text);
        const before = (await (await fetch(`${api}/tasks`)).json()).length;
        await flowPage.getByRole('button', {name: 'Preview suggestions', exact: true}).click();
        await flowPage.getByRole('heading', {name: 'Review suggestions', exact: true}).waitFor();
        await flowPage.getByText('Demo results', {exact: false}).waitFor();
        assert.equal((await (await fetch(`${api}/tasks`)).json()).length, before);
        await flowPage.getByRole('textbox', {name: 'Task title', exact: true}).fill('Day4 end-to-end study task');
        await flowPage.getByLabel('Urgency').selectOption('3');
        await flowPage.getByText('Planning details', {exact: true}).click();
        await flowPage.getByLabel('Importance (1–5)', {exact: true}).fill('5');
        await flowPage.getByLabel('Estimated minutes (optional)', {exact: true}).fill('20');
        await flowPage.getByRole('button', {name: 'Approve', exact: true}).click();
        await flowPage.getByText('All suggestions reviewed.', {exact: false}).waitFor();
        const approved = (await (await fetch(`${api}/tasks`)).json()).find(task => task.title === 'Day4 end-to-end study task');
        assert.ok(approved.journal_id);
        assert.ok((await (await fetch(`${api}/journals`)).json()).find(entry => entry.id === approved.journal_id && entry.content === text));
        const priority = await (await fetch(`${api}/ai/prioritize`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reference_date: approved.due_date})})).json();
        assert.equal(priority.recommendation.task.id, approved.id);
        await flowPage.getByRole('button', {name: 'Today', exact: true}).click();
        const planner = flowPage.getByRole('region', {name: 'Day planner'});
        await planner.getByLabel('Available start 1', {exact: true}).waitFor();
        while (await planner.getByRole('button', {name: /Remove window/}).count()) await planner.getByRole('button', {name: /Remove window/}).first().click();
        await planner.getByLabel('Available start 1', {exact: true}).fill('00:00');
        await planner.getByLabel('Available end 1', {exact: true}).fill('23:59');
        await planner.getByLabel('Maximum tasks per day', {exact: true}).fill('5');
        await planner.getByRole('button', {name: 'Save availability', exact: true}).click();
        await planner.getByText('Availability saved.', {exact: true}).waitFor();
        await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
        await planner.locator('.placement').getByText(approved.title, {exact: true}).waitFor();
        await planner.getByText('Why this task?', {exact: true}).click();
        await planner.getByRole('button', {name: 'Confirm plan', exact: true}).click();
        await planner.getByText('Schedule confirmed.', {exact: true}).waitFor();
        await flowPage.getByRole('heading', {name: 'Confirmed schedule', exact: true}).waitFor();
        for (const width of [320, 390, 1280]) {
          await flowPage.setViewportSize({width, height: 900});
          assert.equal(await flowPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
          if (width !== 320) await flowPage.screenshot({path: join(frontend, 'test-results', `day4-today-${width}.png`), fullPage: true});
        }
        await flowPage.getByRole('button', {name: 'Start focusing', exact: true}).click();
        await flowPage.getByRole('heading', {name: 'One task at a time', exact: true}).waitFor();
        await flowPage.getByRole('button', {name: 'Mark as done', exact: true}).click();
        await flowPage.getByRole('heading', {name: "Let's get things done.", exact: true}).waitFor();
        const completed = (await (await fetch(`${api}/tasks`)).json()).find(task => task.id === approved.id);
        assert.equal(completed.done, 1);
        assert.ok(completed.scheduled_start);
        const request = flowPage.waitForRequest(request => request.url().endsWith('/planning/propose'));
        await planner.getByLabel('Plan from now (today only)', {exact: true}).check();
        await planner.getByRole('button', {name: 'Generate plan', exact: true}).click();
        assert.equal((await request).postDataJSON().plan_from_now, true);
        await planner.getByText('Existing confirmed times are preserved.', {exact: false}).waitFor();
        await planner.getByRole('button', {name: 'Reject plan', exact: true}).click();
        assert.deepEqual(pageErrors, []);
      } finally {await flowContext.close();}
    });

    await t.test('Today uses Seoul dates when the browser is in another timezone', async () => {
      const travelling = await browser.newContext({timezoneId: 'America/Los_Angeles'});
      try {
        const otherPage = await travelling.newPage();
        await otherPage.clock.install({time: new Date('2026-11-14T15:05:00Z')});
        const dashboardResponse = otherPage.waitForResponse(response => response.url().includes('/api/dashboard?today=2026-11-15'));
        await otherPage.goto(site);
        await otherPage.getByText('2026-11-15', {exact: true}).waitFor();
        const response = await dashboardResponse;
        assert.equal((await response.json()).date, '2026-11-15');
      } finally { await travelling.close(); }
    });
  } finally {
    await browser?.close();
    await Promise.all([stop(preview), stop(backend)]);
    if (dirname(temporary) !== resolve(tmpdir()) || !temporary.includes('togas-browser-')) throw new Error('Unexpected test directory');
    await rm(temporary, {recursive: true, force: true, maxRetries: 3});
  }
});
