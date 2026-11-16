# ToGas — Day 3 구현 보고서

2026년 11월 14일 기준, 로컬 단일 사용자 MVP의 D3-01부터 D3-08까지 구현·검증했습니다. **이 문서는 Day 3 완료 당시의 과거 기록이며, 당시 Day 4는 시작하지 않았습니다.** 이후 작업은 Day 4 보고서와 상태 문서를 참고하세요.

**English:** This historical report records the completed Day 3 implementation. Day 4 had not started at this checkpoint.

## 완료 기능

- 중요도·선택적 예상 시간·노력 수준·수동 확정 시작 시간을 검토·편집을 포함한 펼침 필드에서 입력합니다. 긴급도 척도는 기존 0–3을 유지합니다.
- 기한·긴급도·중요도로 결정적 우선순위를 계산하고 모든 추천·배정에 이유를 제공합니다.
- 날짜별 가용 시간은 최대 12개 비중첩 구간과 하루 작업 수 제한을 지원합니다. 명시적으로 저장한 설정은 재시작 후에도 유지됩니다.
- Today에서 일정을 제안하고 배정·미배정 이유와 기존 충돌을 표시하며 확정·거절할 수 있습니다. 생성·거절은 작업 시간을 저장하지 않습니다.
- 확정 일정은 시간순으로 소요 시간·임시 추정 표시와 함께 나타납니다. 미배정·기한 초과·충돌도 보이며 Jump Start와 Focus를 유지합니다.
- 검증된 인터페이스로 선택적 사용자 상황을 받습니다. 감정 감지·행동 학습·AI 호출은 추가하지 않았습니다.

**English:** Day 3 added task metadata, saved availability, explained priority ranking and explicitly confirmed schedules. Existing Jump Start and Focus continued to work.

## 우선순위 알고리즘과 이유

`rank_tasks(tasks, reference_date)`는 완료 작업을 제외하고 다음 순서로 정렬합니다.

1. 기한 그룹: 기한 초과 → 오늘 → 내일 → 나머지.
2. 긴급도 내림차순, 기존 0–3 척도.
3. 중요도 내림차순, 1–5 척도.
4. 기한 오름차순. 앞 조건이 같으면 기한 없는 작업은 기한 있는 작업 뒤입니다.
5. 작업 ID 오름차순으로 동률을 결정합니다.

따라서 기한이 없더라도 긴급도·중요도가 높으면 더 나중 기한 작업보다 앞설 수 있으며 기한 초과·오늘·내일은 별도 우선 처리합니다. 노력·시간은 순위에 영향을 주지 않습니다. 지연 결과나 수동 순서는 저장하지 않으므로 그런 신호를 지어내지 않습니다. `recommend()`의 작업·설명 응답 형식을 유지하며 `/api/ai/prioritize`는 규칙 기반입니다.

**English:** Rank incomplete tasks by deadline group, urgency, importance, deadline and ID. Effort and duration do not affect priority.

## 시간 배정 알고리즘과 제약

`propose_plan(tasks, reference_date, windows, max_tasks, existing_confirmed=None, context=None)`는 순위와 분리된 순수 함수이며, 우선순위 순으로 가장 이른 빈 구간에 넣는 탐욕 방식입니다. 가용 구간을 정렬하고 작업을 순서대로 고려합니다. 하나의 연속 구간에 들어가야 하며 큰 작업이 안 들어가도 뒤의 작은 작업은 검토합니다.

기존 확정 예약은 모두 보호하고 자동 이동하지 않습니다. 선택일의 확정 작업은 완료된 것도 하루 한도에 포함합니다. 예상 시간이 없으면 계획에 **임시 30분**을 사용합니다. 확정 시 예약 길이는 저장하지만 `estimated_minutes`는 null로 유지합니다. 개별 종료 시간은 입력하지 않습니다.

기한이 선택일보다 이르면 `deadline_passed`로 미배정합니다. 다른 이유는 `no_fitting_window`, `daily_limit`, `already_confirmed`입니다. 기존 겹침·가용 시간 밖 예약·기한 충돌은 별도로 보고하며 작업을 옮기지 않습니다.

Asia/Seoul 현지 시각을 사용합니다. 오프셋을 포함한 입력은 서울 시각으로 변환하고, 저장·반환 값은 오프셋 없는 `YYYY-MM-DDTHH:MM:SS`이며 UI에 서울 시각임을 표시합니다. 가용 구간의 시작·끝은 같은 날짜여야 합니다. 다른 확정 작업과 겹치거나 날짜 경계를 넘는 수동 변경은 원자적으로 거절합니다. 가용 시간·기한 변경으로 충돌이 생겨도 기존 시작을 몰래 옮기지 않습니다.

**English:** Place tasks in the earliest available continuous gap without moving confirmed reservations. Unknown durations use a labeled 30-minute fallback. Times are stored and shown as Seoul local time.

## 데이터베이스와 API 변경

작업 테이블에 추가한 열입니다.

| 열 | 기본값·목적 |
| --- | --- |
| `importance INTEGER` | 기본 3, 1–5 검증 |
| `estimated_minutes INTEGER NULL` | 미입력은 알 수 없음, 입력 시 정수 1–1440 |
| `effort_level INTEGER` | 기본 3, 1–5 검증 |
| `scheduled_start TEXT NULL` | 확정된 서울 현지 시작 시각 |
| `scheduled_minutes INTEGER NULL` | 임시 시간을 포함한 예약 길이 |
| `scheduled_provisional INTEGER` | 기본 0, 계획용 대체값과 사용자 추정 구분 |
| `schedule_status TEXT` | 기본 `unscheduled`, 시작이 있으면 서버가 `confirmed`로 관리 |

`availability_preferences(date PRIMARY KEY, windows, max_tasks)`는 명시적으로 저장한 설정을, `schedule_confirmations(plan_id PRIMARY KEY, payload, result)`는 확정 요청 확인 정보를 보관합니다. 작업에는 현재 예약 하나가 있으므로 반복 확정이 일정 행을 추가하지 않습니다.

새 엔드포인트입니다.

| 엔드포인트 | 입력·동작 |
| --- | --- |
| `GET /api/availability?date=YYYY-MM-DD` | 설정 조회, 없으면 `saved: false` |
| `PUT /api/availability` | `{date, windows: [{start: "09:00", end: "12:00"}], max_tasks: 5}` |
| `POST /api/planning/propose` | `{date, context?: {energy_level, source: "user", valid_for_date}}`, 저장한 가용 시간 사용 |
| `POST /api/planning/confirm` | `{plan: <unchanged proposal response>}` |

제안에는 작업 공간 상태 지문과 서버 서명이 들어갑니다. 확정 시 SQLite 쓰기 트랜잭션 안에서 검증합니다. 작업이나 저장된 가용 시간이 바뀌면 미확정 제안은 오래된 것으로 보고 409를 반환합니다. 변조·만료 제안도 409입니다. 확정 확인 정보로 응답 유실·동시 재시도가 재시작 후에도 안전하며, 재요청은 이후 수정·완료·삭제를 되돌리지 않습니다. 미확정 제안은 서버 재시작 시 만료되어 다시 생성해야 합니다. 거절은 UI에서 제안을 버립니다.

Day 3 이전 생성 재시도 확인 정보는 새 기본값으로 정규화하여 마이그레이션 뒤에도 보호합니다. 기존 작업·기록·API는 유효합니다. 마이그레이션은 임시 DB에서만 검사했으며 사용자 SQLite를 쓰기용으로 열거나 삭제하지 않았습니다.

**English:** Additive schema changes preserve old data and retry receipts. Signed proposals are checked atomically; stale or modified proposals return 409. Confirmed retries never undo later changes.

## Day 3 변경 파일

| 파일 | 목적 |
| --- | --- |
| `backend/planning.py` | 배정·확정 예약 보호·충돌·수동 겹침 검사 |
| `backend/scheduling.py` | 우선순위·이유·시간순 대시보드 |
| `backend/schemas.py` | 메타데이터·현지 시각·가용 시간·상황·계획 검증 |
| `backend/storage.py` | 추가 열·설정 및 확정 테이블 |
| `backend/main.py` | 저장·서명·원자적 확정·오래된 제안 및 재시도 처리 |
| `frontend/src/Planner.jsx` | 가용 시간·미리 보기·확정·거절·복구 상태 |
| `frontend/src/TaskFields.jsx`, `frontend/src/TaskList.jsx` | 간결한 정보 편집·확정 시각·소요 시간 표시 |
| `frontend/src/main.jsx`, `frontend/src/style.css` | Today 연결·시간순 그룹·충돌 안내·반응형 |
| `frontend/src/task-save.js`, `frontend/src/task-save.test.js` | 수동 저장·승인 시 계획 정보 유지 |
| `backend/tests/test_planning.py` | 우선순위·배정·API·마이그레이션·저장 테스트 19개 |
| `backend/tests/test_day3.py` | 기한 없음·미래 기한 동률의 기대값을 명시적 Day 3 정책에 맞춤 |
| `frontend/tests/browser.test.js` | 실제 오프라인 백엔드의 새 일정 흐름 4개 |
| `README.md`, `docs/STATUS.md`, `docs/DAY3_READINESS.md`, 이 보고서 | 현재 동작·근거와 과거 준비안의 연결 |

이전 Day 2.5 추출 변경은 당시 작업 트리에 남아 있었습니다. 공식 `backend/jev_api.py` 어댑터는 변경하지 않았습니다.

**English:** Changes covered planning, validation, persistence, UI and regression tests. The official Jev adapter was unchanged.

## 실행 검사와 결과

- 깨끗한 Python 3.12 환경에서 **93개 통과**. 기한 그룹·결정적 동률·기한 및 시간 없음·큰 작업·다중 및 역순 구간·하루 한도·기존 겹침·확정 시작 보호·확정 및 거절·동시 및 반복 확정·오래된 제안·완료 및 편집·상황·구형 데이터와 재시도 마이그레이션을 포함합니다. 기존 기록·추출·Jev·검토 회귀도 통과했습니다.
- JavaScript 단위 테스트 **11개 통과**.
- Chrome 프로덕션 흐름 **23개 통과**(부모 포함 24개). 가용 시간 실패·재시도, 거절, 예상 시간 없음, 확정 응답 유실, 시간순 저장·새로 고침, 겹침 거절, 정보 편집, Focus 완료, 오래된 계획 재생성을 검사했습니다.
- 320·390·1280픽셀에서 가로 넘침 없음. `frontend/test-results/`에 데스크톱·모바일 이미지를 생성하고 확인했습니다. 해당 경로는 Git에서 제외합니다.
- 프로덕션 빌드와 `pip check` 통과. 마지막 빌드는 기본 API 주소를 복원했습니다. 브라우저 쓰기는 임시 DB와 포트 18000/15173을 사용했습니다. Node·Chrome은 자식 프로세스 제한으로 자동 승인된 샌드박스 외 실행을 사용했습니다.
- **실제 Jev 호출·외부 모델 다운로드·배포 0회**, 기존 앱 SQLite 변경·삭제 없음. 이전 순위 회귀가 바뀐 동률 정책 때문에 처음 실패했으나 요청된 Day 3 정책으로 수정한 뒤 전체 검사를 통과했습니다.

**English:** At this checkpoint, 93 backend tests, 11 JavaScript tests and 23 browser scenarios passed. No live Jev calls, deployments or existing application-data changes occurred.

## 당시 알려진 제한

하루 단위 계획만 지원하며 반복·달력 동기화·작업 분할·최적화 라이브러리는 없습니다. 당시에는 현재 시각이 아닌 선택일 전체를 고려했습니다. 임시 30분 추정은 부정확할 수 있습니다. 완료 예약도 명시적으로 해제하기 전까지 보호하고 한도에 포함합니다. 수동 시작은 가용 시간 밖이나 기한 뒤일 수 있으며 자동 변경 대신 충돌로 표시합니다.

노력은 향후 적합도 정책용으로 저장합니다. 유효한 사용자 상황을 받지만 아직 반영하지 않습니다. 지연 결과 필드·수동 순서는 없습니다. 모든 작업 편집은 보수적으로 미확정 제안을 무효화합니다. 미확정 제안은 브라우저 안에만 있고 화면 이동·새로 고침 후 유지하지 않으며 백엔드 재시작 시 만료됩니다. 인증·클라우드 동기화가 없는 로컬 단일 사용자 앱입니다.

**English:** Day 3 planning covered one full day, with no recurrence or calendar sync. Unconfirmed plans were temporary. Effort and context were stored or accepted without affecting priority.

## 당시 권장한 Day 4 작업

우선순위 설명·임시 시간에 대한 피드백을 모으고, 노력·에너지 적합도 선호는 사용자 통제하에서만 추가하도록 제안했습니다. 계획 전용 대체 시간 조정, 현재 시각부터 계획, 과거 예약의 재배정·해제 안내도 검토 대상으로 삼았습니다. 향후 달력·상황·메모리는 별도 범위와 선택적 사용으로 유지하도록 했습니다. **이 시점에는 Day 4를 시작하지 않았습니다.**

**English:** Suggested follow-up included clearer explanations, optional planning from now and user-controlled suitability preferences. These were future ideas at this historical checkpoint.
