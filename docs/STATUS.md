# ToGas verification checkpoint — November 14, 2026

The offline P0 workflow is implemented and verified. The official TypeSafe Jev adapter is implemented, and the classroom key passed one live smoke test. Broad real-model evaluation and a complete live browser workflow remain pending before final submission.

## Feature status

| Feature | Status | Evidence / limit |
| --- | --- | --- |
| Today dashboard | Working and verified | Today's queue, completion count, progress, explained recommendation |
| Journal saving and history | Working and verified | Independent save, reopen with editor focus, retained failed input, retry-safe saves and analysis reuse |
| Task management | Working and verified | Add/edit/category/urgency/deadline, complete/reopen, delete, persistence |
| Priority and scheduling | Working and verified locally | Importance, duration, effort, persistent multi-window availability, proposed/confirmed schedules, stale-plan and retry protection |
| Task extraction | Implemented; one live example verified | Mock pipeline and hosted contract tested; live model returned a reviewable personal task |
| AI review | Working and verified with mock decisions | Edit metadata, original text, explicit review reasons, approve/reject, no automatic task writes, duplicate guard |
| Jump Start | Working and verified | Deterministic deadline/urgency/importance ranking; never calls Jev |
| Single-task Focus | Working and verified | One task, completion, dashboard update, failure remains retryable |
| Search | Working and verified | Literal case-insensitive matching across task titles and journal text |
| Local OpenJevX adapter | Implemented but unverified | Explicit reviewed local files only; no automatic downloads |
| Shared classroom Jev API | Connected; one live smoke verified | Official TypeSafe endpoint, Bearer key, `jev-1.14.0`; broader evaluation pending |

## Verification

- 93 backend tests passed in the clean Python 3.12 virtual environment, including Day 3 priority/placement/confirmation/migration tests and all existing extraction, persistence, validation and mocked hosted-adapter regressions.
- Eleven JavaScript tests passed, including planning metadata, task-save retry identities and the Seoul midnight boundary.
- Twenty-three Chrome browser scenarios passed against production assets and temporary SQLite data, including the existing workflows plus persistent multiple windows, schedule rejection, lost committed confirmation, chronological schedules, overlap rejection, scheduled editing/Focus completion and stale-plan regeneration.
- Production build and clean frontend `npm ci` passed using the lockfile and WebAssembly Rollup.
- Backend dependency check passed. The clean environment contains no Hugging Face, ONNX Runtime or tokenizer packages.
- Existing-starter schema migration was tested across two startups; old task rows remain intact.
- Failed task creation, approval, journal saving, analysis, editing and Focus completion were exercised without losing the affected input or saved record.
- Responsive checks passed at widths 320, 390 and 1280; mobile and desktop screenshots were inspected. No uncaught browser JavaScript errors were observed.
- All tests used a temporary database. The user's application database was not used or modified.
- Exactly one authorized live Jev request was made using synthetic text. No additional live evaluation, model downloads, remote Python execution, publication or deployment occurred. All automated HTTP tests use mocked transports.

The browser runner has one parent test plus twenty-three scenario subtests; its summary therefore reports twenty-four passing tests.

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
- Stop after Day 3. Day 4 has not started.

## NLP evaluation preparation

`backend/evaluation/examples.json` contains 20 labeled English/Korean examples. `backend/evaluate.py` records individual predictions, errors, actionability metrics, category correctness and explicit-date correctness.

The refreshed `mock-results.json` reports **mock-only** results: 20/20 actionability decisions, 11/12 categories on actionable examples, and 12/12 dates on actionable examples. The refreshed mixed-journal report matches all eight actionability labels, including the previously missed Korean intention. These numbers measure simple rules on tiny hand-written sets. They are not Jev results and should not be presented as model accuracy.

The earlier “Do not buy anything today” error is fixed. The category for “Call the dentist tomorrow” remains a mock mistake. Real-model evaluation across this set, confidence calibration, and latency measurement remain pending.

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
2. Run a capped evaluation of the labeled examples when ready to use the shared service; record errors and limitations separately from mock results. The live evaluator requires an explicit `--limit` and stops on the first service/configuration failure.
3. Use real results to revisit confidence thresholds and English/Korean examples; do not infer broad accuracy from the one smoke example.

## Submission limits

Single-user local demo; no authentication or cloud sync. Unsaved drafts do not survive a browser reload. Segmentation, negation and date recognition remain conservative. Longer entries warn that only the first 15 segments are analyzed. Dates such as “this weekend” need manual review. No claim of real Korean model quality is currently supported.

The extracted starter did not contain a Git repository. This document records the engineering checkpoints included in the project's initial Git import; subsequent work can be tracked through Git commits.
