# ToGas verification checkpoint — November 12, 2026

The offline P0 workflow is implemented and verified. The official TypeSafe Jev adapter is implemented, and the classroom key passed one live smoke test. Broad real-model evaluation and a complete live browser workflow remain pending before final submission.

## Feature status

| Feature | Status | Evidence / limit |
| --- | --- | --- |
| Today dashboard | Working and verified | Today's queue, completion count, progress, explained recommendation |
| Journal saving and history | Working and verified | Independent save, reopen with editor focus, retained failed input, retry-safe saves and analysis reuse |
| Task management | Working and verified | Add/edit/category/urgency/deadline, complete/reopen, delete, persistence |
| Task extraction | Implemented; one live example verified | Mock pipeline and hosted contract tested; live model returned a reviewable personal task |
| AI review | Working and verified with mock decisions | Edit metadata, original text, explicit review reasons, approve/reject, no automatic task writes, duplicate guard |
| Jump Start | Working and verified | Deterministic deadline/urgency ranking; never calls Jev |
| Single-task Focus | Working and verified | One task, completion, dashboard update, failure remains retryable |
| Search | Working and verified | Literal case-insensitive matching across task titles and journal text |
| Local OpenJevX adapter | Implemented but unverified | Explicit reviewed local files only; no automatic downloads |
| Shared classroom Jev API | Connected; one live smoke verified | Official TypeSafe endpoint, Bearer key, `jev-1.14.0`; broader evaluation pending |

## Verification

- 51 backend tests passed in the clean Python 3.12 virtual environment, including retry-safe journal saves, legacy journal upgrades, segmentation, review reasons, hosted batching/cache behavior, malformed responses, sanitized service errors, and evaluation call limits.
- Seven task-saving JavaScript tests passed.
- Fifteen Chrome browser scenarios passed against production assets and temporary SQLite data, including cached live-mode review with an intercepted response, a committed journal save with a lost response, editor focus, empty analysis and source-text review.
- Production build and clean frontend `npm ci` passed using the lockfile and WebAssembly Rollup.
- Backend dependency check passed. The clean environment contains no Hugging Face, ONNX Runtime or tokenizer packages.
- Existing-starter schema migration was tested across two startups; old task rows remain intact.
- Failed task creation, approval, journal saving, analysis, editing and Focus completion were exercised without losing the affected input or saved record.
- Responsive checks passed at widths 320, 390 and 1280; mobile and desktop screenshots were inspected. No uncaught browser JavaScript errors were observed.
- All tests used a temporary database. The user's application database was not used or modified.
- Exactly one authorized live Jev request was made using synthetic text. No additional live evaluation, model downloads, remote Python execution, publication or deployment occurred. All automated HTTP tests use mocked transports.

The browser runner has one parent test plus fifteen scenario subtests; its summary therefore reports sixteen passing tests.

## Day 2 checkpoint

The local journal and AI-review implementation is complete for this checkpoint. Day 2 is **not fully verified with real Jev** until the prepared mixed-journal quality check is run.

- Journal input, independent saving, history, repeat analysis and model failure handling are implemented and tested.
- Save requests now include a UUID. A lost response after committing a journal can be retried without another row; changing text with an already-used UUID returns 409. Intentional new identical entries are still possible. This is an additive schema upgrade, tested with existing journal data.
- Segmentation regression checks cover common abbreviations such as Dr./Prof., decimal values, URLs, bullets, semicolons, Korean punctuation and explicit first-person action clauses.
- Review cards preserve the original candidate sentence and explain low confidence, placeholder category/urgency values, and shortened titles. Mock suggestions have a single demo explanation rather than presenting simulated confidence as model evidence.
- Open entry scrolls to and focuses the editor. Empty extraction and finished review have different messages. The review can return to its saved journal, and cached Jev results are explicitly identified.
- The English/Korean mixed-journal check is prepared in `backend/evaluate_journals.py` and `backend/evaluation/day2-journals.json`. Its default mock run completed without external calls; the mock rules missed one Korean intention, which reinforces that mock quality is not Jev quality.
- **No additional live calls were made for Day 2.** A proposed next step uses at most two live requests, one per synthetic journal, with no automatic retries. It does not read or modify application data.

## NLP evaluation preparation

`backend/evaluation/examples.json` contains 20 labeled English/Korean examples. `backend/evaluate.py` records individual predictions, errors, actionability metrics, category correctness and explicit-date correctness.

The checked-in `mock-results.json` reports **mock-only** results: 19/20 actionability decisions, 11/12 categories on actionable examples, and 12/12 dates on actionable examples. These numbers measure simple rules on a tiny hand-written set. They are not Jev results and should not be presented as model accuracy.

Known mock mistakes in this set include “Do not buy anything today” and the category for “Call the dentist tomorrow.” Real-model evaluation across this set, confidence calibration, and latency measurement remain pending.

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
