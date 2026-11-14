# ToGas — Day 3 implementation report

November 14, 2026. D3-01 through D3-08 are implemented and verified for the local, single-user MVP. Day 4 has not started.

## Features completed

- Importance, optional duration, effort and a manually confirmed local starting time are available in expandable task fields, including review and editing. Urgency retains its 0–3 scale.
- Deterministic priority ranking considers deadline urgency, task urgency and importance. Every recommendation and proposed placement includes an explanation.
- Availability supports a date, up to 12 disjoint windows and a daily task limit. Explicitly saved preferences survive restarts.
- Today can generate a proposed schedule, show placement/rejection reasons and existing conflicts, and confirm or reject the proposal. Generation and rejection never write task times.
- Confirmed schedules appear chronologically on Today with duration and provisional labels. Unscheduled work, overdue tasks and conflicts remain visible. Jump Start and Focus remain available.
- Optional user context is accepted through a validated interface. No emotion detection, behavior learning or AI calls were added.

## Priority algorithm and rationale

`rank_tasks(tasks, reference_date)` excludes completed tasks and sorts ascending by:

1. Deadline bucket: overdue → today → tomorrow → everything else.
2. Urgency descending, using the existing 0–3 scale.
3. Importance descending, 1–5.
4. Deadline ascending; no deadline sorts after dated tasks when the preceding factors tie.
5. Task id ascending for deterministic ties.

Thus an undated task with higher urgency/importance can precede a later deadline, while overdue/today/tomorrow receive explicit attention. Effort and duration do not affect priority. Consequences of delay and manual ordering are not stored, so no such signals are invented. `recommend()` retains its existing task/explanation shape; `/api/ai/prioritize` remains rule-based.

## Scheduling algorithm and constraints

`propose_plan(tasks, reference_date, windows, max_tasks, existing_confirmed=None, context=None)` is a pure, greedy earliest-fit function, separate from ranking. It sorts availability windows and considers pending tasks in priority order. A task must fit in one uninterrupted gap; an unfittable task does not prevent smaller tasks from being considered.

All confirmed reservations are protected. Their times are never automatically moved. Reservations on the selected day count toward its limit, including completed confirmed tasks. Unknown durations use **30 provisional minutes for planning**; confirmation stores the reservation length but leaves `estimated_minutes` null. Users do not enter individual ending times.

Tasks whose deadline precedes the selected date remain unplaced with `deadline_passed`. Other reasons include `no_fitting_window`, `daily_limit` and `already_confirmed`. Existing overlaps, outside-availability reservations and deadline conflicts are reported separately without moving the affected tasks.

The app uses Asia/Seoul local wall time. Offset-bearing task datetime input is converted to Seoul; stored/returned starts use `YYYY-MM-DDTHH:MM:SS` without an offset and are explicitly labeled Seoul in the UI. Windows must begin and end on the same date. Manual schedule changes that overlap another confirmed task or cross a day boundary are rejected atomically. Changed availability or deadlines can reveal a conflict; they do not silently move existing starts.

## Database and API changes

Additive task columns:

| Column | Default / purpose |
| --- | --- |
| `importance INTEGER` | 3; validated 1–5 |
| `estimated_minutes INTEGER NULL` | Unknown; validated integer 1–1440 when supplied |
| `effort_level INTEGER` | 3; validated 1–5 |
| `scheduled_start TEXT NULL` | Confirmed Seoul local datetime |
| `scheduled_minutes INTEGER NULL` | Reserved duration, including provisional duration |
| `scheduled_provisional INTEGER` | 0; distinguishes planning fallback from a user estimate |
| `schedule_status TEXT` | `unscheduled`; server-maintained `confirmed` when a start is present |

`availability_preferences(date PRIMARY KEY, windows, max_tasks)` stores explicitly saved preferences. `schedule_confirmations(plan_id PRIMARY KEY, payload, result)` stores confirmation receipts. A task has one current reservation, so repeating confirmation updates no additional schedule row.

New endpoints:

| Endpoint | Input / behavior |
| --- | --- |
| `GET /api/availability?date=YYYY-MM-DD` | Read saved preferences; absent preferences return `saved: false` |
| `PUT /api/availability` | `{date, windows: [{start: "09:00", end: "12:00"}], max_tasks: 5}` |
| `POST /api/planning/propose` | `{date, context?: {energy_level, source: "user", valid_for_date}}`; uses saved availability |
| `POST /api/planning/confirm` | `{plan: <unchanged proposal response>}` |

Proposals include a workspace fingerprint and server signature. Confirmation validates these inside a SQLite write transaction. Any changed task or saved availability makes an unconfirmed proposal stale (409). Modified/expired proposals also return 409. Confirmed receipts make lost-response/concurrent retries safe across restarts; replay never undoes later edits, completion or deletion. Unconfirmed proposals expire on server restart and must be regenerated. Rejecting simply discards the proposal in the UI.

Existing task-create retry receipts from before Day 3 are normalized using the new defaults, preserving retry behavior across migration. Existing task/journal records and endpoints remain valid. Migration was exercised only on temporary databases; the user's SQLite database was not opened for writing or deleted.

## Files changed for Day 3

| Files | Purpose |
| --- | --- |
| `backend/planning.py` | Placement, protected reservations, conflict detection and manual overlap checks |
| `backend/scheduling.py` | Priority ranking/explanations and chronological dashboard data |
| `backend/schemas.py` | Metadata, local datetime, availability, context and planning input validation |
| `backend/storage.py` | Additive columns and preference/confirmation tables |
| `backend/main.py` | Persistence, proposal signatures, atomic confirmation, stale/retry handling |
| `frontend/src/Planner.jsx` | Availability, preview, confirm/reject and recovery states |
| `frontend/src/TaskFields.jsx`, `frontend/src/TaskList.jsx` | Compact metadata editing, confirmed time and duration display |
| `frontend/src/main.jsx`, `frontend/src/style.css` | Today integration, chronological groups, conflict notices, responsive styles |
| `frontend/src/task-save.js`, `frontend/src/task-save.test.js` | Preserve planning metadata during manual saves/approvals |
| `backend/tests/test_planning.py` | 19 priority, placement, API, migration and persistence tests |
| `backend/tests/test_day3.py` | Update the earlier regression's expected undated/future tie ordering for the explicit Day 3 policy |
| `frontend/tests/browser.test.js` | Four new scheduling workflows using the real offline backend |
| `README.md`, `docs/STATUS.md`, `docs/DAY3_READINESS.md`, this report | Current behavior/evidence and link from the historical readiness proposal |

Earlier Day 2.5 extraction changes remain in the working tree. The official `backend/jev_api.py` adapter was not changed.

## Tests executed and results

- Full Python suite: **93 passed** using the clean Python 3.12 environment. Includes deadline buckets, deterministic ties, no deadlines/durations, oversized tasks, multiple/reversed windows, daily limits, existing overlaps, protected starts, confirmation/rejection, concurrent/repeated confirmation, stale plans, completion/editing, context, legacy migration and pre-Day 3 retry receipts. Existing journal/extraction/Jev/review regressions also passed.
- JavaScript unit tests: **11 passed**.
- Chrome production workflows: **23 scenarios passed** (24 tests including the parent). New scenarios cover availability failure/retry, rejection, unknown duration, lost confirmation response, chronological persistence/reload, overlap rejection, metadata editing, Focus completion and stale-plan regeneration.
- Responsive checks: no horizontal overflow at 320, 390 and 1280 pixels. Desktop/mobile planner screenshots were generated and inspected in `frontend/test-results/` (ignored by Git).
- Production builds passed; the final build restores the default API address. `pip check` passed. All browser writes used a temporary database and local ports 18000/15173. Node/Chrome checks required automatically approved execution outside the child-process-restricting sandbox.
- **Zero live Jev calls, external model downloads or deployments.** Existing application SQLite data was not modified or deleted. An earlier test of the old ranking initially failed because its expected tie policy changed; that regression now reflects the requested Day 3 policy and the final full suite passes.

## Known limitations

Single-day planning only; no recurrence, calendar sync, task splitting or optimization library. Planning considers the entire selected day rather than the current clock. The fixed 30-minute provisional estimate can be inaccurate. Completed reservations remain protected/count toward the limit until explicitly cleared. Manual starts can fall outside saved availability or after a deadline; these are visible conflicts rather than automatic rescheduling.

Effort is stored for future suitability policies. Valid user context is accepted but intentionally has no effect yet. No consequence-of-delay field or manual ordering exists. Any task edit conservatively invalidates unconfirmed plans. Unconfirmed proposals live only in the browser, do not survive navigation/reloads, and expire on backend restart. This remains a local single-user application without authentication or cloud synchronization.

## Recommended Day 4 work

Collect feedback on priority explanations and provisional durations; add explicit effort/energy suitability preferences only with user control. Consider an adjustable planning-only fallback duration, a “from now” planning option, and clearer rescheduling/clearing of historical reservations. Keep any future calendar/context/memory integration separately scoped and opt-in. No Day 4 work was started.
