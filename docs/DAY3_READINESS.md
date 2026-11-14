# ToGas — Day 2.5 stabilization and Day 3 readiness

November 14, 2026. As of this Day 2.5 checkpoint, Day 3 architecture was proposed below and not yet implemented.

This is the historical Day 2.5 checkpoint. Day 3 has since been explicitly requested and implemented; see [DAY3_REPORT.md](DAY3_REPORT.md) for the actual schema, policy and verification. The newer request supersedes the field scales and implementation stop below.

## 1. Current capabilities

Journal save/history → candidate analysis → editable review → explicit approval/rejection → task CRUD → Today/Jump Start → Focus remains intact. Analysis never writes tasks. Titles, original source, category, urgency, explicit deadline and review reasons remain available. Existing records and API shapes are preserved.

TypeSafe Jev still batches the three decisions for up to 15 candidates into one request. Its adapter, endpoint, credentials, cache and request/response contract are unchanged. Routine development uses mock decisions. No real-model quality claim follows from mock results.

Today and Jump Start rank incomplete tasks by deadline bucket, urgency, deadline and task id. The recommendation explains its deadline bucket and urgency. This is priority ranking; it does not assign calendar time.

## 2. Changes made in Day 2.5

Inspection found a missing `cook` imperative, action-word substring matching, incomplete negation guards and no action-list splitting. The new pure segmentation component keeps sentence/abbreviation handling, splits only recognizable action-clause boundaries, and uses intention grammar with unseen verbs rather than depending entirely on an expanding verb list.

| Input | Offline result |
| --- | --- |
| `meet friend. cook for tonight.` | 2 proposals |
| `Buy milk and clean my room.` | 2 proposals |
| `Buy bread and butter.` | 1 proposal |
| `Study Python, cook dinner, and call my mother.` | 3 proposals |
| `I feel tired today.` | 0 proposals |
| `I finished my assignment yesterday.` | 0 proposals |
| `I am stressed because I need to submit my report.` | 1 intention proposal; full sentence retained as source |
| `내일 과제를 제출하고 친구를 만나야 해.` | 1 intact, flagged candidate; Korean compound splitting unsupported |

Titles retain the original casing/punctuation where possible and remain editable. Split candidates retain the full original sentence and a reason to check shared objects/deadlines. Dates are detected within each candidate; an ambiguous shared deadline is not silently copied. Quotes and parentheses protect internal coordination. Unknown conjunctions/shared objects remain together with a review reason.

Earlier work in this session added retry-safe task creation and a consistent Seoul browser date. These reliability fixes remain; they do not add scheduling or memory architecture.

## 3. Remaining limitations

- Rules are conservative, not a grammatical parser. Unknown bare imperatives may be missed; explicit `I need to ...` / `I intend to ...` supports unseen verbs. Some action/object ambiguities remain.
- Korean obligations and simple task endings work, but coordinated Korean clauses stay together for manual review. No real Korean Jev quality was measured.
- Negation/completion guards may suppress a whole compound sentence containing both positive and negative/completed clauses. This avoids inventing a new obligation but can miss an intended task.
- Shared deadlines/objects, unusual abbreviations and deeply nested punctuation need review. Vague dates such as “tonight” and “this weekend” stay unset. Only the first 15 candidates are analyzed, with a visible truncation warning.
- The tiny mock fixture set still misclassifies the dentist's category. Mock metrics are not Jev metrics. Unsaved drafts/retry ids do not survive full browser reloads.

## 4. Recommended Day 3 database additions

Use additive nullable columns; preserve `urgency_score`, `due_date`, all existing records and old clients. Never backfill unknown estimates with guessed values.

| Proposed field | Meaning / validation |
| --- | --- |
| `importance_score REAL NULL` | User-assessed importance, 0–3; separate from urgency |
| `estimated_duration_minutes INTEGER NULL` | Positive duration estimate; unknown blocks automatic placement |
| `estimated_effort TEXT NULL` | `low`, `medium`, `high`; cognitive effort, separate from duration |
| `proposed_start_at TEXT NULL` | Optional persisted placement proposal, timezone-aware, normalized to UTC; not a deadline or automatic calendar commitment |

Keep `due_date` as a date-only deadline. Do not infer an appointment time from it. Start with explicit, one-off user availability windows in a future `availability_windows(id, starts_at, ends_at)` table, with UTC timestamps and `ends_at > starts_at`. Display/edit using Asia/Seoul. Recurrence, calendar integration and memory can wait.

## 5. Proposed priority and placement interfaces

These are design signatures, not new endpoints or working code:

```text
rank_tasks(tasks, reference_date, policy)
  -> [{task_id, rank, explanation, reason_codes, missing_inputs}]

propose_placements(ranked_tasks, availability_windows, horizon, timezone)
  -> {placements: [{task_id, proposed_start_at, proposed_end_at, explanation}],
      unscheduled: [{task_id, reason_codes}]}
```

Ranking answers “what next?” using deadline, urgency and explicitly supplied importance. Keep today's deterministic policy as the default until importance is collected; do not invent weights or user preferences. Explain the actual factors and missing estimates.

Placement answers “when can it fit?” using duration, availability and existing accepted placements. It must avoid overlaps and return explicit reasons such as missing duration or no slot. Effort should affect placement only after users supply a preference or capacity policy. Proposals require review; ranking alone must never write a start time. Preserve `/api/ai/prioritize` and `/api/dashboard` responses; introduce optional request fields or new placement APIs only in separately authorized Day 3 work.

## 6. Tests executed and results

- 74 backend tests passed, including 14 stabilization tests with parameterized cases. Coverage includes all requested examples, guarded negation/completion, English/Korean text, source/deadline preservation, empty/invalid input, existing persistence/migrations, and unchanged Jev batching through `httpx.MockTransport`.
- 10 JavaScript tests and 19 Chrome workflow scenarios passed (20 browser tests including the parent). Production builds passed; the final build uses the default API address. Chrome used temporary SQLite data and ports 18000/15173.
- Offline evaluations completed: 20/20 actionability decisions, 11/12 categories and 12/12 dates on the small labeled fixture; both mixed journals' eight actionability labels match. These measure demo rules only.
- No live Jev calls, model downloads, application database writes/deletions, or deployments occurred. All analysis tests used mock rules or mocked HTTP. Existing migration/persistence checks passed.

### Modified files and purpose

| Files | Purpose |
| --- | --- |
| `backend/segmentation.py` | Pure candidate splitting, intention detection, conservative guards and source/reason metadata |
| `backend/ai.py` | Consume candidates in existing adapters; recognize cooking; preserve source/review data |
| `backend/tests/test_extraction_stabilization.py` | Day 2.5 regressions and mocked hosted-contract/persistence checks |
| `frontend/tests/browser.test.js` | Cooking/action-list review scenario, plus earlier retry/timezone browser checks |
| `backend/evaluation/mock-results.json`, `backend/evaluation/day2-mock-results.json` | Refreshed offline reports, explicitly marked as mock |
| `README.md`, `docs/STATUS.md`, `docs/DAY3_READINESS.md` | Behavior, evidence, limits and proposed architecture |
| `backend/main.py`, `backend/schemas.py`, `backend/storage.py` | Earlier optional task-save UUID, additive receipt storage and retry handling |
| `backend/tests/test_day3.py` | Earlier task reliability/recommendation regression checks; filename does not indicate implementation of the proposed architecture |
| `frontend/src/task-save.js`, `frontend/src/task-save.test.js` | Earlier retry-token retention and duplicate-submission tests |
| `frontend/src/main.jsx` | Earlier task-id merge on successful retry |
| `frontend/src/api.js`, `frontend/src/date.js`, `frontend/src/date.test.js` | Earlier consistent Seoul date helper and boundary tests |
| `frontend/package.json` | Include all JavaScript unit-test files |

`backend/jev_api.py`, `backend/scheduling.py`, `frontend/src/Review.jsx` and the existing Day 2 tests were inspected and remain unchanged. Stop here: Day 3 scheduling/schema additions above require a new implementation request.
