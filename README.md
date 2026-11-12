# ToGas — Turn Your Thoughts Into Action

A local, single-user productivity app: **Brain Dump → Review → Jump Start → Single-Task Focus**.

React/Vite frontend, FastAPI backend, and SQLite storage. Task wording stays based on the original journal; suggested tasks are stored only after approval.

**Current status:** the P0 workflow runs in offline demo mode by default. The official TypeSafe Jev adapter is implemented and the classroom key passed one live smoke test using `jev-1.14.0`. Demo suggestions remain rule-based fixtures, not Jev predictions. No key is needed for mock mode; a broader real-model evaluation is still pending.

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
- **Review:** edit titles, categories, urgency and deadlines; inspect the original sentence and specific review reasons; approve or reject suggestions. Pending suggestions remain accessible while navigating. Failed saves preserve the edited input. Empty analysis explains that the journal is safe, and Back to journal returns to its editor.
- **Tasks:** the list is shown first; tap **+** beside All Tasks to open the new-task form. Close hides the form and keeps the draft; a successful save clears and closes it. Failed saves leave the form open for retry. Existing tasks support editing, complete/reopen and deletion. Pending submissions are guarded against repeated clicks; successful saves use the returned server record.
- **Search:** literal, case-insensitive keyword search across task titles and journal content, including Korean text.
- **Focus:** work on one task, mark it complete, and return to Today. A failed completion keeps the task open for retry.

## AI modes and the Jev connection

`TOGAS_AI_MODE` defaults to `mock`. The UI labels this as demo mode, hides simulated confidence values, and requires review. Normal development makes no Jev calls and downloads no model files.

Demo detection does not require the word “need”: examples include “Finish my NLP project,” “Meet my friend,” “Visit the doctor,” and “Attend the lecture.” It still uses a limited action-word list and can miss other natural phrasing. Use live mode for deliberate Jev tests.

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
- Jump Start considers only incomplete tasks: overdue → due today → due tomorrow → undated → later deadlines. Within each group, higher urgency wins, then earlier deadline and older task ID. It is deterministic and makes no model calls.
- Today includes active overdue/undated/due-today tasks and tasks completed on that day. Completion-day grouping uses Asia/Seoul; future tasks remain in All Tasks and can still be recommended if no earlier task is available.
- Titles are trimmed and limited to 1–250 characters. Journal content must be nonblank and at most 10,000 characters; original formatting is preserved.
- Categories are study/work/personal/health/other. Urgency must be a finite JSON number from 0–3; completion requires a JSON boolean. Unknown fields, invalid dates and null task updates are rejected; `due_date: null` explicitly clears a deadline.
- Invalid inputs return readable 422 responses. Empty task updates return 400, missing task IDs return 404, and unavailable analysis returns 503. Rejected updates do not change stored records.

## Tests and evaluation

Latest verification: 51 backend tests, fifteen Chrome workflow scenarios, dependency checks, and the production build passed. Automated hosted tests use mocked HTTP responses; the separate recorded smoke test made exactly one live request. Day 2's additional work made no live calls.

From the root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe backend/evaluate.py --mode mock
```

From `frontend`:

```powershell
npm.cmd test
npm.cmd run test:browser
```

The browser command builds production assets first. It requires installed Chrome and unused ports 8000/5173. It starts temporary servers and a temporary SQLite database; existing application data is untouched. Set `TOGAS_TEST_PYTHON` for a different backend Python executable, or `TOGAS_BROWSER_CHANNEL=msedge` for installed Edge. No browser download is needed. Tests cover both intercepted failure scenarios and the real backend's offline mock pipeline.

To test while the app is running, set `TOGAS_TEST_API_PORT=18000`, `TOGAS_TEST_UI_PORT=15173`, and `VITE_API_URL=http://127.0.0.1:18000/api` in the test terminal before running browser tests. The extra CORS origin is added only to the temporary test backend. Afterwards, remove `VITE_API_URL` from that terminal and run `npm.cmd run build` to restore the default production API address.

Screenshots are generated in `frontend/test-results/` (ignored by Git). The 20-example English/Korean labeled set is `backend/evaluation/examples.json`; the evaluator records predictions, errors and metrics. `mock-results.json` is explicitly **not a Jev evaluation**. Broader Jev quality, calibration and latency remain unmeasured. Do not use this small hand-written set to claim general accuracy.

Live evaluation is opt-in: for example, `python backend/evaluate.py --mode jev --limit 1` using the project virtual environment. An explicit `--limit` is required to cap calls. It stops on the first upstream/configuration failure, without retries. No live evaluation beyond the single smoke test has been run.

Day 2 also has two mixed journals in `backend/evaluation/day2-journals.json`: one English and one Korean, with eight labeled segments total (intentions, feelings and completed actions). Run `python backend/evaluate_journals.py --mode mock` for an offline pipeline check. The prepared live command is `python backend/evaluate_journals.py --mode jev --max-requests 2`; it sends at most two requests, uses only these synthetic examples, and stops after an error. This live command has **not** been run. The saved `day2-mock-results.json` does not measure Jev quality; the mock rules miss one Korean intention in this small set.

See [the verification checkpoint](docs/STATUS.md) for tested scope and remaining work.

## Storage and architecture

SQLite data lives in `backend/togas.db` (ignored by Git). Startup adds deadline, completion-time, source-journal and journal-save request columns when missing without deleting existing records. Connections are committed/rolled back and closed explicitly. Journal creation accepts an optional UUID `request_id`: retries with the same id and text return the same entry, while different text with the same id returns 409. The UI reuses that id across retries within the current session; New entry starts a fresh save. Existing completed tasks without a historical timestamp remain in All Tasks but cannot be counted as completed on a known day. Back up an important database before upgrading.

```text
backend/
  main.py                 HTTP endpoints and orchestration
  schemas.py              Shared input validation
  storage.py              SQLite lifetime, migration, keyword search
  ai.py                   Decision adapters, segmentation, normalization
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

Implemented endpoints: health, dashboard, task CRUD, journal save/list, search, `/api/ai/analyze` (also `/api/ai/extract`), and deterministic `/api/ai/prioritize`.

## Limitations

Local demo only: no authentication, cloud sync or deployment security. Segmentation preserves common titles/abbreviations, decimals and URLs, and splits explicit first-person action clauses. Unusual abbreviations, shared-object conjunctions, negation and vague deadlines can still be misinterpreted. The first 15 segments are processed per analysis; longer input gets a visible warning. Invalid actionability probabilities fail safely; invalid categories/urgency/confidence fall back to reviewable values with an explanation. Long suggested titles are shortened with the original sentence available for comparison. Mock rules are intentionally simple and make mistakes, including some negation and category cases.

User drafts are retained while navigating within the app, but unsaved drafts and journal retry ids are not persisted across browser reloads. Saving a journal before analysis protects it from model failures. Journal retries within the session are protected against duplicate saves after lost responses; task-creation failures after a server commit can still leave an uncertain result, so inspect Tasks before retrying in that case.

The referenced `Jev_Tutorial(1).ipynb` was not present in the supplied workspace. No XP, timers, monetization, social features or analytics have been added.
