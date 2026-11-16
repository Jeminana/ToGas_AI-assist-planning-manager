# ToGas — Day 4: NLP quality and UI refinement

November 14, 2026 checkpoint. Local implementation and verification are complete. Update November 16: the authorized three-request live Jev evaluation is complete (see below). The real-service browser workflow subsequently passed November 16; see [STATUS.md](STATUS.md) and [live workflow results](../backend/evaluation/live-workflow-results.json). Remaining submission preparation is pending.

## 1. Features completed

The starting repository was clean at `7b72baf` and matched the Day 3 report: 1–5 importance/effort, nullable duration, persistent availability, signed proposals, retry-safe confirmation and protected reservations. No undocumented implementation drift was found.

- D4-01: hosted contract, normalization, failure preservation and explicit approval verified with mocked HTTP. Existing TypeSafe adapter/request contract is unchanged.
- D4-02/03: expanded evaluation to 40 multi-task English/Korean/mixed journals and improved guarded segmentation. All twelve required examples produce their labeled action spans in mock mode.
- D4-04/05: honest missing-confidence display, manual missing-task approval, extracted counts, compact task metadata, prominent titles/times, All Tasks filters and expandable placement explanations.
- D4-06: optional Plan from now; full-day planning remains the default.
- D4-07: feeling-only entries remain saved with a clear non-actionable result. Persistent daily energy input is deferred; its proposed interface is below.
- D4-08: full regression, production UI, responsive checks and this report completed using temporary data.

## 2. Files modified

| Files | Purpose |
| --- | --- |
| `backend/segmentation.py` | English temporal/contracted reflection/independent clauses; guarded Korean action compounds; ambiguous-wording reasons |
| `backend/ai.py` | Preserve action spans, nullable unavailable confidence, repeat-intention warnings, elapsed analysis metadata; small demo-category fixes |
| `backend/evaluate.py` | Extend the existing evaluator with one-to-one multi-task metrics, candidate/classification diagnostics, metadata, dataset/id selection and live call caps |
| `backend/evaluate_journals.py` | Match action spans one-to-one rather than collapse proposals sharing source text |
| `backend/evaluation/day4-journals.json` | Forty labeled journals with counts, spans, categories, dates and review policy |
| `backend/evaluation/day4-baseline-mock-results.json`, `backend/evaluation/day4-mock-results.json` | Before/after reports, both explicitly mock-only |
| `backend/evaluation/mock-results.json`, `backend/evaluation/day2-mock-results.json` | Refresh legacy offline checks |
| `backend/main.py`, `backend/planning.py`, `backend/schemas.py` | Optional strict-boolean from-now request, Seoul clock cutoff, remaining-time reasons and passed-start confirmation guard |
| `backend/tests/test_day4.py` | Fifteen contract, language, metric and fixed-clock regressions |
| `backend/tests/test_extraction_stabilization.py` | Update the earlier Korean limitation assertion to the newly supported behavior; retain shared-object checks |
| `frontend/src/Review.jsx`, `frontend/src/main.jsx` | Extracted counts, confidence/model details, retry-safe manual additions linked to their saved journal, retained drafts and task filters |
| `frontend/src/TaskFields.jsx`, `frontend/src/style.css` | Strong titles/start times, short status lines, expandable metadata and keyboard focus |
| `frontend/src/Journal.jsx` | Accurate hosted/local/demo analysis button labels |
| `frontend/src/Planner.jsx` | Optional from-now control and expandable priority explanations |
| `frontend/tests/browser.test.js` | Missing-confidence/manual-save recovery, filtering and complete journal-to-Focus scenario; open collapsed prediction details in the existing fixture test |
| `README.md`, `docs/STATUS.md`, this report | Current capabilities, evidence, limits and pending live command |

No new dependencies or database tables/migrations were added. `backend/jev_api.py` and `backend/storage.py` are unchanged.

## 3. NLP extraction architecture

Original journal saving remains independent from analysis. The pure candidate layer separates sentences/bullets and safe action clauses, retaining the complete containing sentence for review. All candidates still enter the existing batched Jev actionability/category/urgency decisions; demo rules remain a separate provider.

New rules recognize contracted reflection prefixes, temporal introductions, explicit commitments such as “Tomorrow I have a meeting,” `then` clauses and independent `I ...` clauses after a reflection/completed activity. Bare coordinated verbs do not reset negation scope. Korean splitting requires a recognized action suffix such as `제출하고` plus a following obligation; object conjunctions such as `빵하고 우유` and `친구하고` stay together. These are limited rules, not a general parser.

Candidates preserve literal action spans and original source. No shared deadline is silently copied to another clause. Date resolution remains deterministic in `scheduling.py`, never an upstream model's invented date field. Unclear separator-free text stays intact with a reason to add a missing task manually. Repeated intentions remain separate, with a duplicate warning, rather than being silently merged.

Actionability must be finite and within 0–1; the existing 0.5 detection / 0.8 review thresholds remain uncalibrated defaults. Invalid category/urgency fall back to reviewable placeholders. Missing/invalid category or urgency confidence is now `null`, not fabricated zero. Genuine returned numbers are shown only on demand; mock numbers remain hidden. No proposal creates a task until explicit approval.

## 4. Dataset and metrics

`day4-journals.json` has 40 synthetic journals, 43 expected actions, 42 category labels and 14 explicit-date labels. It includes all requested examples plus direct/multiple/informal tasks, reflections, completed/negated/vague/tentative intentions, shared objects, bullets, abbreviations, repeated intentions, English, Korean and mixed language. Every record includes original text, reference date, expected count/action spans, applicable category/date and a manual-review policy. Positive examples require human approval; this label is not a claim of probability calibration.

One-to-one normalized action-span matching counts extras, merged actions and duplicates. Normalization changes casing, whitespace and boundary punctuation only. Count accuracy alone cannot hide a wrong extraction. Category/date denominators include labeled actions missed by extraction. Explicit-date accuracy excludes vague/absent dates. Candidate-level missing spans and model-classification misses are separate diagnostics; they do not partition every possible error.

Both columns below are **mock rules on the same hand-written set**, not Jev accuracy or held-out generalization:

| Metric | Day 3 baseline | Day 4 |
| --- | --- | --- |
| Task precision | 82.35% | 97.62% |
| Task recall | 65.12% | 95.35% |
| Extraction F1 | 0.7273 | 0.9647 |
| Exact task count | 30/40 | 39/40 |
| Category correctness | 22/42 | 37/42 |
| Explicit-date correctness | 9/14 | 14/14 |
| False positives on reflection/completed-only journals | 0 across 5 journals | 0 across 5 journals |
| Expected spans missing from segmentation | 14 | 2 |
| Expected spans present but not classified as actions | 1 | 0 |

The remaining count error is `d4-15`, “meet friend cook dinner”: one preserved ambiguous proposal instead of two actions. Strict span scoring counts that as one extra and two missed actions. Category errors include those two misses plus the Dr. Kim / chapter 3.5 example and the Korean buying example. Manual correction remains necessary. Legacy mock checks also pass: 20/20 actionability, 12/12 category and 12/12 date labels, plus all eight Day 2 mixed-journal actionability labels.

Offline reproduction:

```powershell
.\.venv-clean\Scripts\python.exe backend/evaluate.py --mode mock --dataset backend/evaluation/day4-journals.json --reference-date 2026-11-14 --output backend/evaluation/day4-mock-results.json
```

## 5. Mock versus real Jev results

### November 16 follow-up: capped live evaluation completed

The user authorized the prepared evaluation, which completed exactly three uncached requests with `jev-1.14.0` and zero service errors. [Saved live results](../backend/evaluation/day4-jev-results.json) retain actual predictions, returned usage and whole-analysis latency separately from mock reports.

| Journal | Observed result | Input/output tokens | Analysis latency |
| --- | --- | --- | --- |
| `d4-07`, English mixed reflection/intention | One study task, expected date; review required | 584 / 92 | 512.811 ms |
| `d4-10`, Korean compound | Two expected tasks, study/personal; review required | 884 / 180 | 196.285 ms |
| `d4-12`, English negated intention | No task, as expected | 585 / 92 | 186.150 ms |

Totals: 2,053 input / 364 output tokens. All three expected action spans/categories and both explicit dates matched; task precision/recall/F1 and exact count accuracy were 1.0 on these three selected synthetic journals only. There were no observed extraction errors. This subset contains no reflection-only/completed-only examples and cannot establish general accuracy or calibrate confidence thresholds.

The fixture reference date remains November 14, so tomorrow resolves to November 15 despite execution on November 16. Dates are resolved locally rather than generated by Jev. The Korean second action retains a null deadline and shared-deadline warning; both Korean proposals have uncertain-urgency warnings. Timings measure whole analysis rather than network alone. No application database, private configuration or implementation changed. The real-service browser workflow was not run.

The following paragraphs preserve the original November 14 checkpoint and prepared command; their pending/live-call statements describe that earlier date.

Configuration inspection confirmed mock mode and a configured hosted credential, without printing it. A credential's presence is not authorization to spend shared usage. No additional live request was made. All automated hosted tests used synthetic keys and `httpx.MockTransport`; browser hosted-mode responses were intercepted fixtures. Their model names, token counts and predictions are simulated test data.

The only actual hosted evidence remains the November 12 smoke record, `backend/evaluation/jev-smoke.json`: model `jev-1.14.0`, 581 input / 92 output tokens, one request. That record did not capture latency and does not establish current service availability or general NLP quality.

Successful analysis responses now include measured `analysis_latency_ms` (whole analysis, not isolated network latency) alongside sanitized returned model, usage, request count and cache state. A cache hit's usage belongs to its original request. Real Day 4 model name/latency/token results remain pending.

Prepared live plan, **not executed**: three synthetic journals (`d4-07` English mixed, `d4-10` Korean compound, `d4-12` negated intention), at most three HTTP requests, no automatic retries, stop after any error. It reads/writes no application database. Run only after explicit shared-service authorization:

```powershell
.\.venv-clean\Scripts\python.exe backend/evaluate.py --mode jev --dataset backend/evaluation/day4-journals.json --ids 'd4-07,d4-10,d4-12' --limit 3 --reference-date 2026-11-14 --output backend/evaluation/day4-jev-results.json
```

The report will contain returned model/usage/analysis time and actual predictions. No Day 4 live result file or real-service quality claim is supplied. A full real-service browser workflow remains pending separately; do not treat the intercepted browser fixture as that verification.

## 6. UI and planning changes

Review shows extracted counts, source text on demand, short review reasons and expandable prediction/model details. Missing confidence says “not provided.” The missing-task form supports category/deadline/priority metadata and explicit manual approval. Failed saves retain input and reuse the existing task-save UUID across lost responses. A retained draft stays linked to its original saved journal.

Task titles are stronger; confirmed start/duration, overdue/due status and scheduling state are visible. Urgency/importance/effort move into Task details. All Tasks offers all/active/completed/scheduled/unscheduled filters; completed tasks remain struck through. Placement rationale is expandable. Keyboard controls use native buttons/labels/details and visible focus outlines.

Plan from now defaults off. On today's date, the backend captures Seoul time and rounds up to a minute before clipping new placement windows. Future dates retain full availability. Confirmed reservations and their capacity are protected; past confirmed times are not falsely marked outside availability because of the cutoff. Unfittable work receives a remaining-time reason. Midnight rounding produces no past placements. First confirmation rejects passed proposed starts (409); already-confirmed retries remain safe even later. Regenerate after waiting too long. No time or energy signal changes priority.

## 7. Verification and problems resolved

- Full Python suite: **108 passed**, including all Day 1–3 tests, 15 Day 4 tests, existing hosted checks, migrations/persistence, placement and confirmation recovery.
- JavaScript unit tests: **11 passed**.
- Chrome: **25 workflow scenarios passed** (26 tests including the parent) against production assets and temporary SQLite. This includes the complete journal → extraction → edited review → explicit approval → database → priority → availability → proposal → confirmation → Today → Focus → completion scenario, manual-save lost-response recovery, honest confidence display and filters.
- Responsive checks passed at 320, 390 and 1280 pixels; screenshots were generated in ignored `frontend/test-results/` and inspected. Production builds, `pip check` and whitespace checks passed. The final production build restores the default API address.
- Two new browser tests initially used overly strict select-label selectors. A follow-up run exposed fixed-clock context leakage into the new real-date flow. Selectors were corrected and the end-to-end scenario isolated in a fresh browser context; the final full suite passes. The former Korean-limit tests were updated to assert the now-supported behavior, not removed.
- The initial dataset-writing attempt exposed PowerShell stdin encoding loss for Korean. The fixture was corrected to UTF-8 before recording the baseline; required-example tests now check literal spans. Both saved reports use the corrected dataset.
- **Zero live Jev calls, model downloads, deployments or writes/deletions to existing application data.** Every data-writing verification used a temporary SQLite database. Sandbox-blocked Node/Chrome launches ran with automatic approval outside the sandbox.

## 8. Remaining limits and deferred context

Rules do not cover arbitrary Korean morphology, implicit subject/tense, unknown bare imperatives or separator-free action lists. Shared deadlines/objects and ambiguous categories still need review. Only the first 15 candidates are analyzed, with a visible warning. Vague dates such as “tonight” and “this weekend” remain unset. The dataset is small, synthetic and used during development; confidence thresholds and real Jev Korean quality remain unmeasured.

Persistent daily energy input was deferred to avoid expanding the database/UI scope. The existing optional context interface remains `{energy_level: "low" | "medium" | "high", source: "user", valid_for_date: "YYYY-MM-DD"}`; a future UI could label medium “Normal” and explicitly save a dated `daily_context` row via GET/PUT. It must remain separate from durable preferences, require user confirmation, and not infer emotions or silently change priority. No diagnosis, profiling, learning or emotion history was added.

Day 3's single-day scheduling, provisional-duration, completed-reservation and local single-user limits remain. Unsaved drafts/proposals do not survive full browser reloads. Live authorization/evaluation and real-service browser validation remain pending.

## 9. Suggested Day 5 submission tasks

With explicit authorization, run the capped evaluation, inspect English/Korean errors and record real model/latency/usage separately from mock metrics. Then deliberately validate one real-service browser workflow, prepare submission screenshots/demo instructions, review known limits and confirm a clean dependency install. Do not infer broad accuracy from the small fixture. Day 5 work has not started.
