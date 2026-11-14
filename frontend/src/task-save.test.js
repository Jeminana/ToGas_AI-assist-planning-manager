import test from 'node:test';
import assert from 'node:assert/strict';
import {createTaskSaver} from './task-save.js';

function harness(request) {
  const events = {pending: [], saved: [], errors: []};
  const save = createTaskSaver({
    request,
    onPendingChange: value => events.pending.push(value),
    onSaved: task => events.saved.push(task),
    onError: message => events.errors.push(message),
  });
  return {save, events};
}

test('successful save preserves urgency zero and publishes the returned task', async () => {
  const returnedTask = {id: 7, title: 'Study NLP', urgency_score: 0, done: 0};
  const calls = [];
  const {save, events} = harness(async (path, options) => {
    calls.push({path, options});
    return returnedTask;
  });
  let confirmed = false;
  assert.equal(await save({title: 'Study NLP', urgency_score: 0}, () => {confirmed = true;}), true);
  assert.equal(confirmed, true);
  assert.deepEqual(events.saved, [returnedTask]);
  assert.deepEqual(events.pending, [true, false]);
  assert.deepEqual(events.errors, ['']);
  assert.equal(calls.length, 1); // No refresh request after a committed save.
  assert.equal(calls[0].path, '/tasks');
  assert.equal(calls[0].options.method, 'POST');
  const {request_id, ...payload} = JSON.parse(calls[0].options.body);
  assert.match(request_id, /^[0-9a-f-]{36}$/);
  assert.deepEqual(payload, {
    title: 'Study NLP', category: 'other', urgency_score: 0,
  });
});

test('lost responses reuse a token; successful independent saves use fresh tokens', async () => {
  const tokens = [];
  const task = {title: 'Retry safely', urgency_score: 0, due_date: null};
  const {save} = harness(async (path, options) => {
    tokens.push(JSON.parse(options.body).request_id);
    if (tokens.length === 1) throw new TypeError('Response lost after commit');
    return {id: 8, ...task};
  });
  assert.equal(await save(task), false);
  assert.equal(await save({...task}), true);
  assert.equal(tokens[0], tokens[1]);
  assert.equal(await save({...task}), true);
  assert.notEqual(tokens[1], tokens[2]);
});

test('separate suggestions with identical text retain separate retry tokens', async () => {
  const tokens = [];
  const {save} = harness(async (path, options) => {
    tokens.push(JSON.parse(options.body).request_id);
    throw new Error('Offline');
  });
  await save({_id: 'first', title: 'Read'});
  await save({_id: 'second', title: 'Read'});
  await save({_id: 'first', title: 'Read'});
  assert.notEqual(tokens[0], tokens[1]);
  assert.equal(tokens[0], tokens[2]);
});

test('missing metadata receives defaults', async () => {
  const {save} = harness(async (path, options) => {
    const task = JSON.parse(options.body);
    assert.equal(task.category, 'other');
    assert.equal(task.urgency_score, 1);
    return {id: 1, ...task};
  });
  assert.equal(await save({title: 'Buy milk'}), true);
});

test('planning metadata is preserved, including an explicitly unknown duration', async () => {
  const {save} = harness(async (path, options) => {
    const task = JSON.parse(options.body);
    assert.equal(task.importance, 5);
    assert.equal(task.effort_level, 1);
    assert.equal(task.estimated_minutes, null);
    assert.equal(task.scheduled_start, '2026-11-14T09:00');
    return {id: 10, ...task};
  });
  assert.equal(await save({title: 'Planning task', importance: 5, effort_level: 1, estimated_minutes: null, scheduled_start: '2026-11-14T09:00'}), true);
});

test('approved task keeps its deadline and source journal', async () => {
  const {save} = harness(async (path, options) => {
    const task = JSON.parse(options.body);
    assert.equal(task.due_date, '2026-11-16');
    assert.equal(task.journal_id, 9);
    return {id: 1, ...task};
  });
  assert.equal(await save({title: 'Read notes', due_date: '2026-11-16', journal_id: 9}), true);
});

test('server rejection retains the edited suggestion and permits a retry', async () => {
  const suggestion = {title: 'Edited suggestion', category: 'study', urgency_score: 2};
  let proposals = [suggestion];
  let attempts = 0;
  const {save, events} = harness(async () => {
    if (++attempts === 1) throw new Error('HTTP 503');
    return {id: 2, ...suggestion};
  });
  const approve = () => save(suggestion, () => {proposals = [];});
  assert.equal(await approve(), false);
  assert.deepEqual(proposals, [suggestion]);
  assert.deepEqual(events.saved, []);
  assert.equal(events.errors.at(-1), 'HTTP 503');
  assert.equal(await approve(), true);
  assert.deepEqual(proposals, []);
  assert.equal(attempts, 2);
  assert.deepEqual(events.pending, [true, false, true, false]);
});

test('network failure retains manual input and releases the save lock', async () => {
  let input = 'Finish assignment';
  const {save, events} = harness(async () => {throw new TypeError('Failed to fetch');});
  assert.equal(await save({title: input}, () => {input = '';}), false);
  assert.equal(input, 'Finish assignment');
  assert.deepEqual(events.saved, []);
  assert.deepEqual(events.pending, [true, false]);
  assert.equal(events.errors.at(-1), 'Failed to fetch');
});

test('repeated submissions while pending send one request and confirm once', async () => {
  let resolveRequest;
  let calls = 0;
  let confirmations = 0;
  const {save, events} = harness(() => {
    calls++;
    return new Promise(resolve => {resolveRequest = resolve;});
  });
  const task = {title: 'Study'};
  const first = save(task, () => {confirmations++;});
  assert.equal(await save(task, () => {confirmations++;}), false);
  assert.equal(calls, 1);
  assert.deepEqual(events.pending, [true]);
  resolveRequest({id: 3, ...task});
  assert.equal(await first, true);
  assert.equal(confirmations, 1);
  assert.equal(events.saved.length, 1);
  assert.deepEqual(events.pending, [true, false]);
});

test('a synchronous request failure also releases the lock for retry', async () => {
  let attempts = 0;
  const {save} = harness(() => {
    if (++attempts === 1) throw new Error('Request failed');
    return Promise.resolve({id: 4, title: 'Study'});
  });
  assert.equal(await save({title: 'Study'}), false);
  assert.equal(await save({title: 'Study'}), true);
  assert.equal(attempts, 2);
});
