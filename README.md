# ToGas — Turn Your Thoughts Into Action

A local, single-user productivity app: **Brain Dump → Review → Jump Start → Single-Task Focus**.

React/Vite frontend, FastAPI backend, and SQLite storage. Task wording stays based on the original journal; suggested tasks are stored only after approval.

See the [submission and demo guide](docs/SUBMISSION.md) for the walkthrough, saved screenshots, final verification and known limits.

**Current status:** the P0 workflow runs in offline demo mode by default. The official TypeSafe Jev adapter passed an earlier smoke test and a three-journal live evaluation on November 16 using `jev-1.14.0`. Demo suggestions remain rule-based fixtures, not Jev predictions. No key is needed for mock mode; the complete real-service browser workflow also passed November 16. Broader model quality remains unmeasured.

## Run locally on Windows

Use Python 3.12 and Node.js 22+ (verified with Node 24). From the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

In a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs.

Using the Python executable directly and `npm.cmd` avoids PowerShell activation/script-policy problems. No global security-policy changes are required. Vite uses [Rollup's official WebAssembly replacement](https://rollupjs.org/migration/#compatibility) through an npm override, avoiding the native module blocked by Windows Application Control. The frontend lockfile records dependency versions.

For the exact verified Python dependency versions, add `-c backend/constraints.txt` to the install command. Core/test dependencies are separate from optional local-model packages. A fresh core/test environment was installed and verified without any local-model libraries.

## What you can do

- **Today:** view overdue, undated and due-today tasks, today's completed tasks, progress, and an explained next-task recommendation.
- **Journal:** save without analysis, reopen history, or preview suggestions. Open entry scrolls to and focuses the editor. Repeated analysis reuses the saved entry; save retries also reuse it when a response was lost after the server committed. Editing an entry saves a new version; history remains unchanged.
- **Review:** inspect extracted counts, edit titles/categories/deadlines/priority metadata, and approve or reject suggestions. Original source and genuine prediction details are expandable; unavailable confidence says “not provided.” Add a missing task with explicit manual approval without leaving review. Pending suggestions and failed input remain available while navigating. Empty extraction explains that the journal is saved.
- **Tasks:** the list is shown first; tap **+** beside All Tasks to open the new-task form. Filter all/active/completed/scheduled/unscheduled tasks. Titles and starting times are prominent; Task details reveals priority metadata. Close keeps the new-task draft; successful saves clear it and failures keep it for retry. Existing tasks support editing, complete/reopen and deletion. Manual saves and approvals reuse a UUID after a lost response, including after Reload workspace.
- **Search:** literal, case-insensitive keyword search across task titles and journal content, including Korean text.
- **Focus:** work on one task, mark it complete, and return to Today. A failed completion keeps the task open for retry.
- **Planning:** open Today → Plan your day, save one or more availability windows and a daily task limit, then Generate plan. Review proposed times and unplaced reasons before Confirm plan or Reject plan. Confirmed tasks appear chronologically with duration/provisional labels. Expand Planning details when adding, editing or approving a task to set importance (1–5), duration, effort (1–5), or an optional manual confirmed start. Unknown duration stays unknown; planning uses a labeled 30-minute fallback. Stale proposals require regeneration. See [the Day 3 report](docs/DAY3_REPORT.md).
- **Plan from now:** optionally enable it for today to exclude elapsed Seoul time from new placements. Full-day planning remains the default and future dates use full availability. Confirmed times remain fixed. If a proposed start passes before its first confirmation, regenerate the plan. Placement explanations are available under Why this task?.

## AI modes and the Jev connection

`TOGAS_AI_MODE` defaults to `mock`. The UI labels this as demo mode, hides simulated confidence values, and requires review. Normal development makes no Jev calls and downloads no model files.

Demo detection supports explicit intention grammar, including unseen verbs, and a limited imperative list including “cook.” Safe English coordination, temporal introductions, mixed reflection/intention clauses and guarded Korean compounds now split into reviewable candidates; shared objects stay together. For example, “내일 과제를 제출하고 친구를 만나야 해” yields two candidates. Split candidates keep the complete source sentence and explain shared-deadline/object uncertainty. Unknown bare imperatives, arbitrary Korean morphology and separator-free action lists remain limitations. Routine development and testing make no live Jev calls.

Environment settings are shown in `.env.example`. The backend automatically loads the project-root `.env` without overriding explicit shell environment settings. Keep credentials out of chat, source files, screenshots, and Git; `.env` is ignored.

The adapter follows TypeSafe's [official request/response contract](https://docs.typesafe.ai/api/system-one): `POST https://api.typesafe.ai/v1/systemone`, Bearer authentication, and `model`, `state`, `questions` fields. The key is used only in the server-side Authorization header. This host is fixed; the adapter does not try unrelated gateways or follow redirects.

For a deliberate live session, stop the backend and restart it from the root:

```powershell
$env:TOGAS_AI_MODE = "jev"
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

Refresh the browser; Journal shows **Live Jev mode** and **Organize with Jev**. `JEV_API_KEY` is read from the private `.env`, and `JEV_MODEL` defaults to `jev-latest`. To return to offline development, stop the backend, set `$env:TOGAS_AI_MODE = "mock"`, and restart. Saving journals, task CRUD, startup, health checks and recommendations do not call Jev.

One journal analysis batches up to 15 segments and their three decisions into **one HTTP request**. Successful identical requests are reused in memory for 30 minutes (maximum 32 entries, separated by credentials/model/text/questions/reference date). A cached response reports `request_count: 0`; its usage values describe the original request. Restarting clears the cache. The adapter uses a 30-second timeout and no automatic retries or redirects. Failures never silently switch to mock results.

`backend/evaluation/jev-smoke.json` records the one live smoke test: “Meet my friend tomorrow.” → personal task, action probability 0.98, urgency 1.88, and due date 2026-11-13. Lower urgency confidence correctly triggered review. No task was stored. This verifies connectivity and response handling, not general NLP quality.

An explicit one-request diagnostic is available as `python backend/check_jev.py` using the project virtual environment. **Running it makes a live request** with synthetic text; it leaves `.env` and application data unchanged. It was run once during integration and is not part of automated tests.

The legacy local OpenJevX path remains optional and **unverified with real weights**. It requires `backend/requirements-local-ai.txt`, `TOGAS_AI_MODE=local`, and `TOGAS_OPENJEVX_DIR` pointing to reviewed `openjevx.py`, `openjevx.w8.onnx`, `tokenizer.json`, and `config.json` files. The application does not download or execute remote Python automatically. OpenJevX is a community implementation, distinct from the classroom hosted Jev service. `disabled` mode returns a recoverable analysis error while manual features remain usable.

## Dates, recommendations and validation

- Date recognition supports ISO `YYYY-MM-DD`, today/tomorrow/day after tomorrow, weekdays, and their implemented Korean equivalents. Bare weekdays use the next occurrence including today; “next Friday” means Friday of the following calendar week. The browser supplies the reference date. Vague dates such as “this weekend” stay unset for user review.
- Jump Start considers only incomplete tasks: overdue → due today → due tomorrow → remaining tasks. Within each group, higher urgency wins, then higher importance, earlier deadline (undated last on a tie), and older task ID. Effort does not affect priority. It is deterministic and makes no model calls.
- Today includes active overdue/undated/due-today tasks, tasks with a confirmed start today even if their deadline is later, and tasks completed on that day. The browser's Today date, journal-analysis reference date and completion-day grouping all use Asia/Seoul, including when the browser uses another timezone. Other future tasks remain in All Tasks and remain eligible for recommendations under the priority rules above.
- Titles are trimmed and limited to 1–250 characters. Journal content must be nonblank and at most 10,000 characters; original formatting is preserved.
- Categories are study/work/personal/health/other. Urgency must be a finite JSON number from 0–3; completion requires a JSON boolean. Unknown fields, invalid dates and unsupported null updates are rejected. Deadline, estimated duration and scheduled start may explicitly be cleared with null.
- Invalid inputs return readable 422 responses. Empty task updates return 400, missing task IDs return 404, and unavailable analysis returns 503. Rejected updates do not change stored records.

## Tests and evaluation

Latest automated verification (Day 4): 108 backend tests, 11 JavaScript tests, twenty-five Chrome workflow scenarios, dependency checks, and the production build passed. This includes the complete journal-to-confirmed-schedule-to-Focus workflow with offline AI. Automated hosted tests use mocked HTTP responses. [Day 4 report](docs/DAY4_REPORT.md) records the mock baseline/improvement and the November 16 three-request live evaluation; the real-service browser workflow passed November 16 (see `backend/evaluation/live-workflow-results.json` and `docs/STATUS.md`).

From the root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe backend/evaluate.py --mode mock
.\.venv\Scripts\python.exe backend/evaluate.py --mode mock --dataset backend/evaluation/day4-journals.json --reference-date 2026-11-14
```

From `frontend`:

```powershell
npm.cmd test
npm.cmd run test:browser
```

The browser command builds production assets first. It requires installed Chrome and unused ports 8000/5173. It starts temporary servers and a temporary SQLite database; existing application data is untouched. Set `TOGAS_TEST_PYTHON` for a different backend Python executable, or `TOGAS_BROWSER_CHANNEL=msedge` for installed Edge. No browser download is needed. Tests cover both intercepted failure scenarios and the real backend's offline mock pipeline.

To test while the app is running, set `TOGAS_TEST_API_PORT=18000`, `TOGAS_TEST_UI_PORT=15173`, and `VITE_API_URL=http://127.0.0.1:18000/api` in the test terminal before running browser tests. The extra CORS origin is added only to the temporary test backend. Afterwards, remove `VITE_API_URL` from that terminal and run `npm.cmd run build` to restore the default production API address.

Screenshots are generated in `frontend/test-results/` (ignored by Git). The 20-example English/Korean labeled set is `backend/evaluation/examples.json`; the evaluator records predictions, errors and metrics. `mock-results.json` is explicitly **not a Jev evaluation**. Broader Jev quality, calibration and latency remain unmeasured. Do not use this small hand-written set to claim general accuracy.

Day 4 adds 40 multi-task journals in `backend/evaluation/day4-journals.json`, scored using one-to-one action spans, task precision/recall/F1, exact counts, categories, explicit dates and reflection/completion false positives. On this synthetic development fixture, mock F1 improved from 0.7273 to 0.9647 and exact counts from 30/40 to 39/40. These are **not Jev accuracy** or held-out generalization results. See `day4-baseline-mock-results.json` / `day4-mock-results.json` for per-example diagnostics. Hosted responses expose actual returned model/usage and measured whole-analysis latency; the selected live subset is recorded separately below.

Live evaluation is opt-in: for example, `python backend/evaluate.py --mode jev --limit 1` using the project virtual environment. An explicit `--limit` is required to cap calls. It stops on the first upstream/configuration failure, without retries. On November 16, the authorized three-journal subset (`d4-07,d4-10,d4-12`) passed with no service or extraction errors: three expected tasks/categories and two explicit dates matched; the negated intention produced no task. Total usage was 2,053 input / 364 output tokens, with whole-analysis latency of 186–513 ms. See `backend/evaluation/day4-jev-results.json`. These selected synthetic examples do not establish general accuracy or confidence calibration.

Day 2 also has two mixed journals in `backend/evaluation/day2-journals.json`: one English and one Korean, with eight labeled segments total (intentions, feelings and completed actions). Run `python backend/evaluate_journals.py --mode mock` for an offline pipeline check. The prepared live command is `python backend/evaluate_journals.py --mode jev --max-requests 2`; it sends at most two requests, uses only these synthetic examples, and stops after an error. This live command has **not** been run. The refreshed `day2-mock-results.json` matches all eight actionability labels after stabilization; this does not measure Jev quality.

See [the verification checkpoint](docs/STATUS.md) for tested scope and remaining work.

## Storage and architecture

SQLite data lives in `backend/togas.db` (ignored by Git). Startup adds deadline, completion-time, source-journal and journal-save request columns and a task-creation receipt table when missing without deleting existing records. Connections are committed/rolled back and closed explicitly. Journal creation accepts an optional UUID `request_id`: retries with the same id and text return the same entry, while different text with the same id returns 409. The UI reuses that id across retries within the current session; New entry starts a fresh save. Task creation also accepts an optional UUID: equivalent details return the existing task without undoing later edits or completion. Different details or a previously deleted task return 409. Task receipts survive server restarts and deletion, preventing delayed retries from recreating deleted tasks. Existing completed tasks without a historical timestamp remain in All Tasks but cannot be counted as completed on a known day. Back up an important database before upgrading.

```text
backend/
  main.py                 HTTP endpoints and orchestration
  schemas.py              Shared input validation
  storage.py              SQLite lifetime, migration, keyword search
  ai.py                   Decision adapters and normalization
  segmentation.py         Pure candidate splitting and conservative demo rules
  jev_api.py              Official hosted adapter, batching and bounded cache
  settings.py             Private .env loading; explicit shell settings win
  scheduling.py           Explicit dates, Today and recommendation rules
  tests/                  API, validation, migration and decision-output checks
  evaluation/             Labeled examples and clearly marked mock results
frontend/src/
  main.jsx                App state and workflow orchestration
  Journal.jsx / Review.jsx / Search.jsx / TaskList.jsx / TaskFields.jsx
  api.js / task-save.js    Requests and guarded task creation
```

Implemented endpoints: health, dashboard, task CRUD, journal save/list, search, `/api/ai/analyze` (also `/api/ai/extract`), deterministic `/api/ai/prioritize`, availability GET/PUT, and `/api/planning/propose` / `/api/planning/confirm`. Day 3 startup adds task metadata plus availability and confirmation-receipt tables without deleting existing data. Schedules use explicit Seoul local times; proposals do not write task times. Confirmed starts remain fixed, and overlapping manual changes return 409.

## Limitations

Local demo only: no authentication, cloud sync or deployment security. Unusual abbreviations, ambiguous coordination, arbitrary Korean compounds, shared objects and deadlines can still be misinterpreted. Unknown bare imperatives and separator-free action lists may be missed; unclear candidates stay intact with a review reason. The first 15 candidates are processed per analysis; longer input gets a visible warning. Invalid actionability probabilities fail safely; invalid category/urgency values use explained placeholders, and unavailable confidence is null. Long titles retain the original source for comparison. Repeated intentions are flagged, not automatically merged. Mock rules remain imperfect and do not measure Jev quality. Persistent daily energy/context storage remains deferred.

User drafts are retained while navigating within the app, but unsaved drafts and journal/task retry ids are not persisted across browser reloads. Saving a journal before analysis protects it from model failures. Journal and task retries within the session are protected against duplicate saves after lost responses. Changed task details use a new save request; after an uncertain failure, retry unchanged details first or inspect Tasks before editing and saving again. Reload workspace preserves current draft/retry state; a full browser reload does not.

The referenced `Jev_Tutorial(1).ipynb` was not present in the supplied workspace. No XP, timers, monetization, social features or analytics have been added.
