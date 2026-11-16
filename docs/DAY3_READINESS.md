# ToGas — Day 2.5 추출 안정화 및 Day 3 준비 기록

2026년 11월 14일의 **과거 Day 2.5 시점 기록**입니다. 당시 아래 Day 3 구조는 제안 단계였으며 구현하지 않았습니다. 이후 별도 요청으로 Day 3를 구현했습니다. 실제 스키마·정책·검증은 [DAY3_REPORT.md](DAY3_REPORT.md)를 참고하세요. 이후 요청이 이 문서의 필드 척도와 구현 중단 지침을 대체합니다.

**English:** This is a historical Day 2.5 checkpoint. The proposals below were not implemented at that time. Day 3 was later implemented separately; see its report for the actual design.

## 1. 당시 제공 기능

기록 저장·이력 → 후보 분석 → 수정 가능한 검토 → 명시적 승인·거절 → 작업 CRUD → Today/Jump Start → Focus 흐름을 유지했습니다. 분석만으로 작업을 저장하지 않습니다. 제목·원문·분류·긴급도·명시적 기한·검토 이유와 기존 데이터·API 형식을 보존했습니다.

TypeSafe Jev는 최대 15개 후보의 판단 3종을 요청 1회로 묶습니다. 어댑터·엔드포인트·인증·캐시·요청 및 응답 규약은 변경하지 않았습니다. 일반 개발은 모의 판단을 사용하며 모의 결과로 실제 모델 품질을 주장하지 않습니다.

당시 Today와 Jump Start는 미완료 작업을 기한 그룹·긴급도·기한·작업 ID로 정렬했습니다. 추천은 기한 그룹과 긴급도를 설명했으며, 이는 우선순위 선정이지 달력 시간 배정은 아니었습니다.

**English:** The existing journal-to-Focus flow remained intact. Analysis did not save tasks, and ranking did not assign calendar times. The Jev adapter was unchanged.

## 2. Day 2.5 변경 사항

`cook` 명령형 누락, 행동 단어의 부분 문자열 매칭, 불완전한 부정문 보호, 행동 목록 분리 부재를 확인했습니다. 새 순수 후보 분리 모듈은 문장·약어 처리를 유지하고 식별 가능한 행동절 경계만 나눕니다. 동사 목록만 늘리는 대신 명시적 의도 문법으로 처음 보는 동사도 처리합니다.

| 입력 | 당시 오프라인 결과 |
| --- | --- |
| `meet friend. cook for tonight.` | 제안 2개 |
| `Buy milk and clean my room.` | 제안 2개 |
| `Buy bread and butter.` | 제안 1개 |
| `Study Python, cook dinner, and call my mother.` | 제안 3개 |
| `I feel tired today.` | 제안 0개 |
| `I finished my assignment yesterday.` | 제안 0개 |
| `I am stressed because I need to submit my report.` | 의도 제안 1개, 전체 문장을 원문으로 보존 |
| `내일 과제를 제출하고 친구를 만나야 해.` | 검토 표시된 온전한 후보 1개, 당시 한국어 복합 행동 분리 미지원 |

제목의 대소문자·문장부호는 가능한 한 유지하며 수정할 수 있습니다. 분리 후보는 전체 문장과 공유 목적어·기한 검토 이유를 보존합니다. 날짜는 각 후보에서 감지하며 모호한 공유 기한을 임의로 복사하지 않습니다. 따옴표·괄호 안의 병렬 표현은 보호합니다. 모르는 접속 구조·공유 목적어는 함께 유지하고 검토 이유를 표시합니다.

이전 작업의 재시도 안전 작업 생성과 서울 기준 브라우저 날짜도 유지했습니다. 이 신뢰성 수정은 일정 배정이나 메모리 구조를 추가한 것이 아닙니다.

**English:** Safe English action lists were split while shared objects and source text were preserved. Korean compounds remained intact at this historical checkpoint.

## 3. 당시 남은 제한

- 보수적인 규칙이며 문법 분석기는 아닙니다. 모르는 단독 명령형은 놓칠 수 있습니다. `I need to ...` / `I intend to ...`는 처음 보는 동사도 지원하지만 행동·목적어의 모호성은 남습니다.
- 한국어 의무 표현과 단순 작업 종결은 지원하지만 병렬 절은 묶어 수동 검토하도록 했습니다. 실제 한국어 Jev 품질은 측정하지 않았습니다.
- 긍정 의도와 부정·완료 절이 섞이면 전체 문장을 억제할 수 있습니다. 새 의무를 만들어 내는 것을 피하지만 의도한 작업을 놓칠 수 있습니다.
- 공유 기한·목적어, 드문 약어, 깊은 중첩 문장부호는 검토가 필요합니다. `tonight`, `this weekend` 같은 모호한 날짜는 비워 둡니다. 첫 15개 후보만 분석하고 초과 경고를 표시합니다.
- 작은 모의 데이터에서 치과 방문 분류 오류가 남았습니다. 모의 지표는 Jev 지표가 아닙니다. 미저장 초안·재시도 ID는 전체 새로 고침 후 유지하지 않습니다.

**English:** Conservative rules could miss tasks or categories. Shared dates and ambiguous text required review. Mock results did not measure Jev quality.

## 4. 당시 제안한 Day 3 데이터베이스 확장

null 허용 열을 추가하고 `urgency_score`, `due_date`, 기존 데이터·클라이언트를 유지하도록 제안했습니다. 모르는 추정값을 추측으로 채우지 않습니다. **아래는 실제 구현 스키마가 아닌 과거 제안입니다.**

| 제안 필드 | 의미·검증 |
| --- | --- |
| `importance_score REAL NULL` | 사용자가 판단한 중요도 0–3, 긴급도와 분리 |
| `estimated_duration_minutes INTEGER NULL` | 양의 예상 시간, 모르면 자동 배정하지 않음 |
| `estimated_effort TEXT NULL` | `low`, `medium`, `high`, 시간과 분리한 인지적 노력 |
| `proposed_start_at TEXT NULL` | 선택적인 제안 저장 시각, 시간대를 포함하고 UTC로 정규화, 기한이나 자동 일정 확정과 구분 |

`due_date`는 날짜 전용 기한으로 유지하며 약속 시각을 추론하지 않도록 했습니다. 향후 `availability_windows(id, starts_at, ends_at)`에 사용자가 명시한 일회성 시간대를 UTC로 저장하고 `ends_at > starts_at`를 검증하며 Asia/Seoul로 표시·편집하도록 제안했습니다. 반복 일정·달력 연동·메모리는 후순위였습니다.

**English:** These proposed nullable fields were historical design ideas, not the final schema. The later Day 3 report defines the implemented scales and behavior.

## 5. 우선순위·배정 인터페이스 제안

아래는 설계용 시그니처이며 당시 새 엔드포인트나 동작 코드가 아니었습니다.

```text
rank_tasks(tasks, reference_date, policy)
  -> [{task_id, rank, explanation, reason_codes, missing_inputs}]

propose_placements(ranked_tasks, availability_windows, horizon, timezone)
  -> {placements: [{task_id, proposed_start_at, proposed_end_at, explanation}],
      unscheduled: [{task_id, reason_codes}]}
```

순위는 기한·긴급도·명시적 중요도로 “무엇을 먼저 할지”를 답합니다. 중요도를 수집하기 전에는 기존 결정적 정책을 유지하며 가중치나 선호를 지어내지 않습니다. 실제 요인과 누락된 추정값을 설명합니다.

배정은 예상 시간·가용 시간·확정 배치로 “언제 가능한지”를 답합니다. 겹침을 막고 시간 미입력·빈 구간 없음 같은 이유를 반환해야 합니다. 노력은 사용자 선호나 수용량 정책을 제공받은 후에만 반영하도록 제안했습니다. 제안은 검토가 필요하고 순위만으로 시작 시간을 저장하지 않습니다. `/api/ai/prioritize`, `/api/dashboard` 응답을 유지하며 선택적 필드나 배정 API는 별도 승인된 Day 3 작업에서만 추가하도록 했습니다.

**English:** Ranking chooses what comes next; placement finds a time slot. Neither should invent preferences, and placement proposals require review.

## 6. 당시 검증 결과

- 백엔드 **74개 통과**. 매개변수별 사례를 포함한 안정화 테스트 14개로 요청 예제, 부정·완료 보호, 영어·한국어, 원문·기한 보존, 빈 입력·잘못된 입력, 기존 저장·마이그레이션, `httpx.MockTransport`를 통한 Jev 일괄 요청 유지 등을 확인했습니다.
- JavaScript **10개**, Chrome 시나리오 **19개** 통과(부모 포함 브라우저 테스트 20개). 프로덕션 빌드를 통과했으며 마지막 빌드는 기본 API 주소입니다. 임시 SQLite와 포트 18000/15173을 사용했습니다.
- 작은 오프라인 정답 데이터에서 행동 여부 20/20, 분류 11/12, 날짜 12/12, 혼합 기록 2건의 행동 여부 8개 일치. 데모 규칙만 측정했습니다.
- 실제 Jev 호출·모델 다운로드·기존 앱 DB 쓰기 및 삭제·배포는 없었습니다. 분석은 모의 규칙·모의 HTTP를 사용했으며 기존 마이그레이션·저장 검사도 통과했습니다.

### 변경 파일과 목적

| 파일 | 목적 |
| --- | --- |
| `backend/segmentation.py` | 순수 후보 분리, 의도 감지, 보수적 보호, 원문·이유 정보 |
| `backend/ai.py` | 기존 어댑터에 후보 전달, 요리 인식, 원문·검토 정보 보존 |
| `backend/tests/test_extraction_stabilization.py` | Day 2.5 회귀·모의 호스팅 규약·저장 검사 |
| `frontend/tests/browser.test.js` | 요리·행동 목록 검토, 이전 재시도·시간대 검사 |
| `backend/evaluation/mock-results.json`, `backend/evaluation/day2-mock-results.json` | 모의 결과임을 표시한 갱신 보고서 |
| `README.md`, `docs/STATUS.md`, `docs/DAY3_READINESS.md` | 동작·근거·제한·구조 제안 |
| `backend/main.py`, `backend/schemas.py`, `backend/storage.py` | 이전 선택적 저장 UUID·추가 요청 확인 저장·재시도 처리 |
| `backend/tests/test_day3.py` | 이전 작업 신뢰성·추천 회귀, 파일명은 제안 구조 구현을 뜻하지 않음 |
| `frontend/src/task-save.js`, `frontend/src/task-save.test.js` | 재시도 토큰 유지·중복 제출 검사 |
| `frontend/src/main.jsx` | 재시도 성공 시 작업 ID 병합 |
| `frontend/src/api.js`, `frontend/src/date.js`, `frontend/src/date.test.js` | 서울 날짜 도우미·경계 검사 |
| `frontend/package.json` | 전체 JavaScript 단위 테스트 포함 |

`backend/jev_api.py`, `backend/scheduling.py`, `frontend/src/Review.jsx`, 기존 Day 2 테스트는 검토했으며 변경하지 않았습니다. 당시 중단 범위는 여기까지였고, 위 일정·스키마 구현은 새 요청이 필요했습니다. 이후 별도 요청으로 구현되었습니다.

**English:** At this checkpoint, 74 backend tests, 10 JavaScript tests and 19 browser scenarios passed without live calls or changes to existing application data.
