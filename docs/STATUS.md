# ToGas verification checkpoint — November 16, 2026

The offline P0 workflow is implemented and verified. The official TypeSafe Jev adapter passed the earlier smoke test and a capped three-journal live evaluation on November 16. The complete live browser workflow also passed on November 16. Broader real-model quality remains unmeasured.

## November 16 real-service browser verification

Submission follow-up: [SUBMISSION.md](SUBMISSION.md) now includes the demo walkthrough, preserved screenshots and scope/limits. Final clean installs, 108 backend tests (including a fresh temporary environment), 11 JavaScript tests, 25 production browser scenarios and the default production build passed. A final fractional-urgency display fix preserves the real model value in Review; its displayed label and saved value are covered by an intercepted-hosted browser regression. No additional live calls were made during this follow-up. The existing local Day 4 work, live evidence and submission package are being committed together.

- **Passed:** independently save synthetic journal, real Jev analysis, edit title/urgency/importance/duration, explicit approval, journal-linked task persistence, explained priority placement, availability save, schedule confirmation, Today recommendation, Focus completion and completed dashboard after reload.
- Saved [live-workflow-results.json](../backend/evaluation/live-workflow-results.json), including actual analysis and persisted task records. Used temporary SQLite and temporary production assets on isolated ports 18000/15173; existing application database, private configuration and default production assets were unchanged. Temporary servers and Chrome were stopped afterward.
- Exactly two live requests in this browser session, with no service retries: the first analysis succeeded but the automation stopped on an overly strict Urgency selector; after correcting the selector, a new isolated run passed. Total usage: 1,170 input / 184 output tokens. Model: `jev-1.14.0`; whole-analysis latency: 494.796 ms (first attempt), 353.412 ms (successful workflow).
- No task existed before explicit approval. One journal and one completed task remained in the successful temporary database, with their link and confirmed start intact. No uncaught browser JavaScript errors; 390/1280 layouts had no horizontal overflow and screenshots were inspected.
- Screenshots: `frontend/test-results/live-workflow/` (ignored by Git). Opt-in reproduction: from `frontend`, set `$env:TOGAS_RUN_LIVE_WORKFLOW='1'`, then `node tests/live-workflow.mjs`. Each invocation permits one live analysis submission, uses the configured classroom credential and requires free ports 18000/15173. This diagnostic is excluded from routine offline tests.
- Full-day planning was used (from-now off), so a midnight placement is expected; this does not validate the optional from-now path with real Jev. Broader model accuracy and confidence calibration remain unmeasured. Submission materials, final install checks and committing/pushing remain.

## November 16 live evaluation

- Completed the authorized three-request check with `jev-1.14.0`; all responses were uncached and no service errors occurred. Results: [day4-jev-results.json](../backend/evaluation/day4-jev-results.json).
- English mixed reflection/intention: one study task; Korean compound: two tasks (study/personal); English negated intention: no tasks. All three expected action spans/categories and both labeled explicit dates matched. Precision/recall/F1 and exact counts were 1.0 on this selected subset only.
- Whole-analysis latency: 512.811, 196.285 and 186.150 ms. Total usage: 2,053 input and 364 output tokens. These timings include local analysis, not isolated network latency.
- Kept the fixture reference date of November 14 for reproducibility; “tomorrow” resolves to November 15. The Korean second action deliberately retains no deadline and a shared-deadline review warning. Both Korean proposals retain uncertain-urgency warnings.
- No extraction errors were observed in these three examples. Reflection-only/completed-only behavior and confidence calibration were not evaluated by this subset; broad English/Korean quality remains unmeasured.
- No application database or private configuration was changed. The live browser workflow subsequently passed as recorded above. The sections below record the earlier Day 1–4 checkpoints and their historical call counts.

## Feature status

| Feature | Status | Evidence / limit |
| --- | --- | --- |
| Today dashboard | Working and verified | Today's queue, completion count, progress, explained recommendation |
| Journal saving and history | Working and verified | Independent save, reopen with editor focus, retained failed input, retry-safe saves and analysis reuse |
| Task management | Working and verified | Add/edit/category/urgency/deadline, complete/reopen, delete, persistence |
| Priority and scheduling | Working and verified locally | Importance, duration, effort, persistent multi-window availability, proposed/confirmed schedules, stale-plan and retry protection |
| Task extraction | Implemented; smoke plus three live journals verified | Selected English/Korean/negated cases passed; broader quality unmeasured |
| AI review | Working and verified offline / intercepted hosted responses | Editable metadata, original text, genuine/missing confidence handling, manual additions, approve/reject, duplicate guards |
| Jump Start | Working and verified | Deterministic deadline/urgency/importance ranking; never calls Jev |
| Single-task Focus | Working and verified | One task, completion, dashboard update, failure remains retryable |
| Search | Working and verified | Literal case-insensitive matching across task titles and journal text |
| Local OpenJevX adapter | Implemented but unverified | Explicit reviewed local files only; no automatic downloads |
| Shared classroom Jev API | Connected; capped live evaluation verified | Official TypeSafe endpoint, Bearer key, `jev-1.14.0`; broader evaluation pending |

## Verification

- 108 backend tests passed in the clean Python 3.12 virtual environment, including all Day 1–3 regressions and Day 4 language, metrics, mocked hosted normalization, confidence, failure-preservation and fixed-clock from-now checks.
- Eleven JavaScript tests passed, including planning metadata, task-save retry identities and the Seoul midnight boundary.
- Twenty-five Chrome browser scenarios passed against production assets and temporary SQLite data. This includes all earlier workflows, manual review additions after a lost committed response, missing confidence, task filters, optional from-now UI and the complete journal → review → task → priority → confirmed schedule → Today → Focus → completion flow.
- Production build and clean frontend `npm ci` passed using the lockfile and WebAssembly Rollup.
- Backend dependency check passed. The clean environment contains no Hugging Face, ONNX Runtime or tokenizer packages.
- Existing-starter schema migration was tested across two startups; old task rows remain intact.
- Failed task creation, approval, journal saving, analysis, editing and Focus completion were exercised without losing the affected input or saved record.
- Responsive checks passed at widths 320, 390 and 1280; mobile and desktop screenshots were inspected. No uncaught browser JavaScript errors were observed.
- All tests used a temporary database. The user's application database was not used or modified.
- Exactly one authorized live Jev request was made using synthetic text. No additional live evaluation, model downloads, remote Python execution, publication or deployment occurred. All automated HTTP tests use mocked transports.

The browser runner has one parent test plus twenty-five scenario subtests; its summary therefore reports twenty-six passing tests.

## Day 2 checkpoint

The local journal and AI-review implementation is complete for this checkpoint. Day 2 is **not fully verified with real Jev** until the prepared mixed-journal quality check is run.

- Journal input, independent saving, history, repeat analysis and model failure handling are implemented and tested.
- Save requests now include a UUID. A lost response after committing a journal can be retried without another row; changing text with an already-used UUID returns 409. Intentional new identical entries are still possible. This is an additive schema upgrade, tested with existing journal data.
- Segmentation regression checks cover common abbreviations such as Dr./Prof., decimal values, URLs, bullets, semicolons, Korean punctuation and explicit first-person action clauses.
- Review cards preserve the original candidate sentence and explain low confidence, placeholder category/urgency values, and shortened titles. Mock suggestions have a single demo explanation rather than presenting simulated confidence as model evidence.
- Open entry scrolls to and focuses the editor. Empty extraction and finished review have different messages. The review can return to its saved journal, and cached Jev results are explicitly identified.
- The English/Korean mixed-journal check is prepared in `backend/evaluate_journals.py` and `backend/evaluation/day2-journals.json`. Its default mock run completed without external calls; the mock rules missed one Korean intention, which reinforces that mock quality is not Jev quality.
- **No additional live calls were made for Day 2.** A proposed next step uses at most two live requests, one per synthetic journal, with no automatic retries. It does not read or modify application data.

## Earlier reliability checkpoint

Before the Day 2.5 checklist arrived, local work covered task-management reliability and the Today → Jump Start → Focus workflow. Those fixes remain. This does not implement the proposed Day 3 scheduling architecture.

- Task creation now accepts optional UUID request ids. An unchanged retry after a committed but lost response returns the existing record; concurrent requests create one row. Both manual saves and approvals retain retry ids within the app session.
- A separate additive receipt table preserves existing tasks and source journals. Receipts survive server restarts. Conflicting payloads and retries for deleted tasks return 409; retries never undo edits or completion. Defaults and trimmed titles are compared after normalization.
- Reload workspace can discover a committed task before a retry. The UI merges the retry response by task id, avoiding a duplicate list row. Successful independent saves receive new request ids, so intentionally identical tasks remain possible.
- Browser dates now use Asia/Seoul, matching backend completion counts even when the browser is in a different timezone.
- Additional regression checks cover the full overdue → today → tomorrow → undated → future recommendation order, urgency/deadline/id tie-breaks, completion, repeated completion, reopening and next-day counts. These paths make no model calls.
- Final verification passed: 60 backend tests, 10 JavaScript tests, 18 Chrome scenarios, dependency checks and production builds. The sandbox blocked Node child-process launches; automatically approved elevated execution completed the build/browser checks. Test API/UI ports were 18000/15173, with a temporary SQLite database. The final production build was restored to the default API address.
- No live Jev calls, model downloads, deployment or application-database changes were made for this checkpoint. Live-model evaluation and the real hosted browser workflow remain separate pending work.

Task retry ids are retained only within the current browser session. Changing task details uses a new request; after an uncertain failure, retry unchanged details or inspect Tasks before editing and saving again.

## Day 2.5 checkpoint

Extraction stabilization was completed before Day 3. See [Day 3 readiness](DAY3_READINESS.md) for that historical checkpoint's example outcomes, limitations and architecture proposals. Scheduling was design-only at that point; it has since been implemented under the separate Day 3 request below.

- `meet friend. cook for tonight.` now produces two reviewable proposals. Safe English action lists split; shared objects, quoted text and parentheses remain intact. Split candidates keep their full original sentence with review reasons.
- Explicit intention grammar supports unseen verbs; mock detection now rejects the tested reflections, completed actions and negations. The official Jev adapter is unchanged; split candidates use its existing batch contract.
- Korean compound splitting remains unsupported: `내일 과제를 제출하고 친구를 만나야 해.` produces one intact, flagged candidate. Basic Korean obligations and standalone tasks are covered by offline regression tests.
- Final verification: 74 backend tests, 10 JavaScript tests, 19 Chrome scenarios and production builds passed. All data-writing checks used temporary SQLite databases. No live Jev calls or existing application-data changes occurred.
- This checkpoint stopped at readiness/design; subsequent Day 3 implementation was explicitly requested.

## Day 3 checkpoint

Day 3 implementation and verification are complete. [DAY3_REPORT.md](DAY3_REPORT.md) records features, algorithms, schema/API changes, files, verification and limits.

- Importance/duration/effort and manual confirmed starts are editable in expandable task fields. Unknown estimates remain null; scheduling labels its 30-minute provisional fallback.
- Availability and a daily task limit are saved per date with multiple non-overlapping windows. Proposed placements remain uncommitted until confirmation; rejection leaves task times unchanged.
- Deterministic priority and earliest-fit placement protect confirmed starts, respect availability/capacity and return unplaced/conflict reasons. Effort and optional user context do not alter priority.
- Confirmation is atomic, retry-safe and protected against changed tasks/availability. Completion and edits preserve starts; overlapping duration/time edits are rejected. Legacy records and pre-Day 3 retry receipts survive additive migration.
- Today displays chronological confirmed tasks, other work and overdue/conflict notices. Existing Jump Start, review and Focus workflows remain verified.
- Final checks: 93 backend tests, 11 JavaScript tests, 23 Chrome scenarios, production builds and dependency checks passed. No live Jev calls or existing application SQLite changes/deletions occurred.
- Day 3 stopped here; Day 4 was subsequently requested separately.

## Day 4 checkpoint

Local implementation and verification are complete. [DAY4_REPORT.md](DAY4_REPORT.md) records changes, metrics, test evidence, known limits and the exact capped live command.

- Starting code at `7b72baf` matched Day 3 documentation. The official hosted adapter, its API contract and database schema were preserved.
- Improved English clauses/reflections/temporal introductions and guarded Korean compounds. All twelve required examples pass in mock mode; original sentence, explicit dates and review reasons remain available. Ambiguous separator-free writing remains one flagged candidate.
- Extended the existing evaluator to 40 synthetic journals with one-to-one task spans and separate missing-candidate/classification diagnostics. Mock precision/recall/F1 are 97.62% / 95.35% / 0.9647, count accuracy 39/40, category correctness 37/42 and explicit dates 14/14. There were no false positives on the five reflection/completed-only examples. These are demo-rule results, not real Jev quality.
- Review supports manually adding a missing task with retry protection. Unavailable confidence is null / “not provided”; genuine returned numbers and model/usage/analysis time are expandable. Mock confidence remains hidden.
- Task lists have stronger titles/start times, compact details and All Tasks filters. Plan from now is optional; fixed-clock tests cover Seoul cutoff, midnight, future dates, preserved confirmations and passed-start rejection. Existing full-day planning remains the default.
- Feeling-only journals are retained without inventing tasks. Persistent user-confirmed daily energy/context storage is deferred; no emotional inference or learning was added.
- Final verification: 108 backend tests, 11 JavaScript tests, 25 Chrome scenarios, production build, dependency and whitespace checks passed. All data-writing checks used temporary SQLite. No live Jev calls, downloads, deployments or existing application-data changes/deletions occurred.
- The prepared three-request real Jev evaluation and real-service browser workflow remain pending explicit authorization. Historical evidence is still the November 12 single smoke request only. Stop after Day 4; Day 5 has not started.

## NLP evaluation preparation

`backend/evaluation/examples.json` contains 20 labeled English/Korean examples. `backend/evaluate.py` records individual predictions, errors, actionability metrics, category correctness and explicit-date correctness.

The refreshed legacy `mock-results.json` reports **mock-only** results: 20/20 actionability decisions, 12/12 categories on actionable examples, and 12/12 dates on actionable examples. The mixed-journal report matches all eight actionability labels. The larger Day 4 fixture and before/after results are described above. These numbers measure simple rules on tiny hand-written sets, not Jev quality or general accuracy.

The earlier negation and dentist-category demo errors are fixed. Day 4 still misses separator-free action boundaries and some categories. Real-model quality, confidence calibration and actual hosted latency measurement remain pending.

## Live smoke result

The documented endpoint `https://api.typesafe.ai/v1/systemone` accepted the local classroom key. A single request with all three decision types returned model `jev-1.14.0`:

- Input: “Meet my friend tomorrow.” Reference date: 2026-11-12.
- Action probability: 0.98; category: personal; urgency: 1.88.
- Category confidence: 0.91; urgency confidence: 0.48. The proposal was flagged for review.
- Deterministically resolved due date: 2026-11-13.
- Reported usage: 581 input tokens, 92 output tokens.
- No task was automatically saved. `.env` remains in mock mode; the key was not printed or stored in results.

The sanitized report is `backend/evaluation/jev-smoke.json`. No further live calls were made after this success.

## Remaining work

1. During a deliberate live session, check the complete journal → real analysis → edited approval → recommendation → Focus browser workflow. Continue routine development in mock mode.
2. The selected three-journal capped evaluation is complete. Broader labeled evaluation remains optional future work requiring a deliberate shared-service session; keep results separate from mock metrics.
3. Use real results to revisit confidence thresholds and English/Korean examples; do not infer broad accuracy from the one smoke example.

## Submission limits

Single-user local demo; no authentication or cloud sync. Unsaved drafts do not survive a browser reload. Segmentation, negation and date recognition remain conservative. Longer entries warn that only the first 15 segments are analyzed. Dates such as “this weekend” need manual review. No claim of real Korean model quality is currently supported.

The extracted starter did not contain a Git repository. This document records the engineering checkpoints included in the project's initial Git import; subsequent work can be tracked through Git commits.
