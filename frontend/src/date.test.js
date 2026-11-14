import test from 'node:test';
import assert from 'node:assert/strict';
import {localDate} from './date.js';

test('Today and journal dates cross midnight in Seoul together', () => {
  assert.equal(localDate(new Date('2026-11-14T14:59:59Z')), '2026-11-14');
  assert.equal(localDate(new Date('2026-11-14T15:00:00Z')), '2026-11-15');
  assert.equal(localDate(new Date('2026-12-31T15:00:00Z')), '2027-01-01');
});
