# ToGas — Day 4 자연어 처리 품질 및 화면 개선 보고서

2026년 11월 14일 로컬 구현·검증 완료 기록입니다. 11월 16일 승인받은 실제 Jev 요청 3회 평가와 실제 서비스 브라우저 검증도 완료했습니다. [STATUS.md](STATUS.md), [실제 흐름 결과](../backend/evaluation/live-workflow-results.json)를 참고하세요. 이후 제출 안내·스크린샷·최종 검사도 완료했으며 [DEMO_GUIDE.md](submission/DEMO_GUIDE.md)에 정리했습니다. 아래 과거 기록의 미실행·대기 표현은 해당 시점 기준입니다.

**English:** Day 4 improved extraction, review and planning. Later live evaluation, browser verification and submission preparation are complete. Historical pending statements below refer to the original checkpoint.

## 1. 완료 기능

시작 저장소는 깨끗한 `7b72baf`였고 Day 3 보고서의 중요도·노력 1–5, null 허용 예상 시간, 가용 시간 영구 저장, 서명 제안, 안전한 확정 재시도, 예약 보호와 일치했습니다. 문서에 없는 구현 차이는 없었습니다.

- D4-01: 모의 HTTP로 호스팅 규약·정규화·실패 보존·명시적 승인을 검사했습니다. 기존 TypeSafe 어댑터·요청 규약은 유지했습니다.
- D4-02/03: 영어·한국어·혼합 다중 작업 기록 40개로 평가를 확장하고 보호 규칙이 있는 분리를 개선했습니다. 필수 예제 12개 모두 모의 모드에서 정답 행동 구간을 생성합니다.
- D4-04/05: 누락 신뢰도 표시, 누락 작업 수동 승인, 추출 개수, 간결한 정보, 제목·시간 강조, All Tasks 필터, 펼치는 배정 이유를 추가했습니다.
- D4-06: 선택적 현재 시각부터 계획을 추가했습니다. 기본값은 하루 전체 계획입니다.
- D4-07: 감정만 있는 기록은 보존하고 행동 없음으로 안내합니다. 일별 에너지 영구 입력은 보류했으며 인터페이스는 아래에 있습니다.
- D4-08: 임시 데이터로 전체 회귀·프로덕션 UI·반응형 검사와 이 보고서를 완료했습니다.

**English:** The implementation preserves the official API contract and adds safer extraction, clearer review, task filters and optional planning from now.

## 2. 변경 파일

| 파일 | 목적 |
| --- | --- |
| `backend/segmentation.py` | 영어 시간 도입·축약 감상·독립절, 제한적 한국어 복합 행동, 모호한 문구의 이유 |
| `backend/ai.py` | 행동 구간 보존, 없는 신뢰도 null, 반복 의도 경고, 분석 시간, 모의 분류 일부 수정 |
| `backend/evaluate.py` | 기존 평가기에 일대일 다중 작업 지표·후보 및 분류 진단·정보·데이터 및 ID 선택·실제 호출 제한 추가 |
| `backend/evaluate_journals.py` | 같은 원문을 공유해도 제안을 합치지 않고 행동 구간을 일대일 대응 |
| `backend/evaluation/day4-journals.json` | 개수·구간·분류·날짜·검토 정책을 포함한 정답 기록 40개 |
| `backend/evaluation/day4-baseline-mock-results.json`, `backend/evaluation/day4-mock-results.json` | 모의 전용임을 표시한 전후 결과 |
| `backend/evaluation/mock-results.json`, `backend/evaluation/day2-mock-results.json` | 기존 오프라인 검사 갱신 |
| `backend/main.py`, `backend/planning.py`, `backend/schemas.py` | 엄격한 불리언 현재 시각 옵션·서울 기준 시각·남은 시간 이유·지나간 시작 확정 방지 |
| `backend/tests/test_day4.py` | 규약·언어·지표·고정 시각 회귀 15개 |
| `backend/tests/test_extraction_stabilization.py` | 기존 한국어 미지원 기대를 새 지원 동작으로 변경, 공유 목적어 검사 유지 |
| `frontend/src/Review.jsx`, `frontend/src/main.jsx` | 개수·신뢰도 및 모델·기록 연결 수동 추가와 재시도·초안·필터 |
| `frontend/src/TaskFields.jsx`, `frontend/src/style.css` | 제목·시간 강조, 짧은 상태 정보, 펼침 정보·키보드 포커스 |
| `frontend/src/Journal.jsx` | 호스팅·로컬·데모 모드별 정확한 분석 버튼 |
| `frontend/src/Planner.jsx` | 현재 시각부터 계획·펼침 우선순위 설명 |
| `frontend/tests/browser.test.js` | 누락 신뢰도·수동 저장 복구·필터·기록부터 Focus까지, 기존 상세 정보 펼침 검사 |
| `README.md`, `docs/STATUS.md`, 이 보고서 | 기능·근거·제한·당시 대기 중 실제 명령 |

새 의존성·DB 테이블·마이그레이션은 추가하지 않았습니다. `backend/jev_api.py`, `backend/storage.py`는 변경하지 않았습니다.

**English:** Changes extend existing components and evaluators. No new dependencies, database tables or migrations were added.

## 3. 자연어 작업 추출 구조

원본 기록 저장은 분석과 독립적입니다. 순수 후보 계층은 문장·목록·안전한 행동절을 나누고 포함 문장 전체를 검토용 원문으로 보존합니다. 후보는 기존 Jev의 행동 여부·분류·긴급도 일괄 판단에 전달합니다. 데모 규칙은 별도 제공자로 유지합니다.

축약 감상 도입부, 시간 도입절, `Tomorrow I have a meeting` 같은 명시적 약속, `then` 절, 감상·완료 뒤 독립적인 `I ...` 절을 인식합니다. 주어 없는 병렬 동사는 부정 범위를 초기화하지 않습니다. 한국어는 `제출하고` 같은 인식된 행동 연결형과 뒤 의무 표현이 있어야 분리합니다. `빵하고 우유`, `친구하고` 같은 목적어 연결은 유지합니다. 제한된 규칙이며 일반 문법 분석기가 아닙니다.

행동 구간과 원문을 그대로 보존하며 공유 기한을 다른 절에 임의 복사하지 않습니다. 날짜는 `scheduling.py`의 규칙으로 계산하며 모델이 지어낸 날짜를 쓰지 않습니다. 구분자 없는 모호한 문장은 유지하고 누락 작업 수동 추가 이유를 제공합니다. 반복 의도는 자동 병합하지 않고 중복 경고와 함께 남깁니다.

행동 확률은 유한한 0–1이어야 합니다. 기존 감지 0.5·검토 0.8 임계값은 보정하지 않은 기본값입니다. 잘못된 분류·긴급도는 검토용 임시값으로 바꿉니다. 누락·잘못된 분류 및 긴급도 신뢰도는 가짜 0이 아니라 `null`입니다. 실제 수치는 펼칠 때만 보여 주고 모의 수치는 숨깁니다. 명시적 승인 전에는 작업을 만들지 않습니다.

**English:** Conservative candidate splitting preserves source text and review reasons. Dates are resolved locally, missing confidence stays null, and no task is saved before approval.

## 4. 데이터와 지표

`day4-journals.json`에는 합성 기록 40개, 예상 행동 43개, 분류 정답 42개, 명시적 날짜 정답 14개가 있습니다. 직접·다중·비격식 작업, 감상, 완료·부정·모호·잠정 의도, 공유 목적어, 목록, 약어, 반복 의도와 영어·한국어·혼합 언어를 포함합니다. 각 항목에 원문·기준일·개수 및 구간·해당 분류 및 날짜·수동 검토 정책을 저장합니다. 긍정 예제의 승인 필요 표시는 확률 보정 주장이 아닙니다.

정규화된 구간을 일대일 대응하여 추가·병합·중복도 계산합니다. 정규화는 대소문자·공백·경계 문장부호만 바꿉니다. 개수만 맞아도 틀린 추출을 숨길 수 없습니다. 분류·날짜 분모에 추출하지 못한 정답도 포함합니다. 명시적 날짜 지표는 모호·미입력 날짜를 제외합니다. 후보 누락과 모델 분류 누락은 별도 진단이며 모든 오류를 배타적으로 나누는 분류는 아닙니다.

아래 두 열은 **같은 수작업 데이터의 모의 규칙 결과**이며 Jev 정확도나 독립 데이터 일반화가 아닙니다.

| 지표 | Day 3 기준 | Day 4 |
| --- | --- | --- |
| 작업 정밀도 | 82.35% | 97.62% |
| 작업 재현율 | 65.12% | 95.35% |
| 추출 F1 | 0.7273 | 0.9647 |
| 정확한 작업 개수 | 30/40 | 39/40 |
| 분류 정답 | 22/42 | 37/42 |
| 명시적 날짜 정답 | 9/14 | 14/14 |
| 감상·완료 전용 기록 오탐 | 5건에서 0개 | 5건에서 0개 |
| 분리 단계의 예상 구간 누락 | 14 | 2 |
| 후보는 있으나 행동으로 분류하지 못함 | 1 | 0 |

남은 개수 오류는 `d4-15`의 `meet friend cook dinner`입니다. 행동 2개 대신 모호한 제안 1개를 보존합니다. 엄격한 구간 채점에서는 추가 1개·누락 2개입니다. 분류 오류는 이 누락 2개, Dr. Kim / chapter 3.5 예제, 한국어 구매 예제를 포함합니다. 수동 수정은 여전히 필요합니다. 기존 모의 검사도 행동 여부 20/20·분류 12/12·날짜 12/12, Day 2 행동 여부 8개 일치입니다.

오프라인 재현 명령입니다.

```powershell
.\.venv-clean\Scripts\python.exe backend/evaluate.py --mode mock --dataset backend/evaluation/day4-journals.json --reference-date 2026-11-14 --output backend/evaluation/day4-mock-results.json
```

**English:** Mock F1 improved from 0.7273 to 0.9647 on the same 40-journal development set. These are rule-based development metrics, not Jev accuracy or held-out results.

## 5. 모의 결과와 실제 Jev 결과

### 11월 16일 후속 기록: 실제 제한 평가 완료

사용자가 준비된 평가를 승인하여 `jev-1.14.0`으로 캐시 없는 요청 정확히 3회를 완료했고 서비스 오류는 없었습니다. [실제 결과](../backend/evaluation/day4-jev-results.json)에 예측·사용량·전체 분석 지연을 모의 보고서와 분리했습니다.

| 기록 | 관찰 결과 | 입력·출력 토큰 | 분석 지연 |
| --- | --- | --- | --- |
| `d4-07`, 영어 감상·의도 혼합 | 학습 작업 1개·예상 날짜·검토 필요 | 584 / 92 | 512.811 ms |
| `d4-10`, 한국어 복합 | 학습·개인 작업 2개·검토 필요 | 884 / 180 | 196.285 ms |
| `d4-12`, 영어 부정 의도 | 예상대로 작업 없음 | 585 / 92 | 186.150 ms |

합계 입력 2,053·출력 364토큰입니다. 예상 행동 구간·분류 3개와 명시적 날짜 2개가 일치했고 선택된 기록 3건에서 정밀도·재현율·F1·정확한 개수 비율이 1.0입니다. 추출 오류는 없었습니다. 감상 전용·완료 전용 예제는 없고 일반 정확도나 임계값 보정 근거는 아닙니다.

실행일은 11월 16일이나 기준일 11월 14일을 유지하여 tomorrow는 11월 15일입니다. 날짜는 Jev가 아니라 로컬에서 계산합니다. 한국어 두 번째 작업은 null 기한·공유 기한 경고를 유지하고, 한국어 제안 2개 모두 긴급도 불확실성 경고가 있습니다. 시간은 네트워크만이 아니라 전체 분석입니다. 앱 DB·비공개 설정·구현은 바꾸지 않았습니다. **이 제한 평가 시점에는 브라우저 검증을 아직 실행하지 않았고, 이후 별도 완료했습니다.**

**English:** Three selected live journals passed without errors, using 2,053 input and 364 output tokens. This small subset does not establish general quality. The complete browser workflow passed later.

### 11월 14일 원래 기록과 준비 명령

이 절은 당시 상태를 보존합니다. 설정 점검으로 모의 모드와 호스팅 키 존재를 확인했지만 키를 출력하지 않았습니다. 키 존재만으로 공유 사용 권한을 추정하지 않았고 추가 실제 요청을 하지 않았습니다. 자동 호스팅은 합성 키·`httpx.MockTransport`, 브라우저는 가로챈 응답을 사용했습니다. 테스트의 모델명·토큰·예측은 모의 데이터입니다.

당시 실제 근거는 11월 12일 `backend/evaluation/jev-smoke.json`의 `jev-1.14.0`, 입력 581·출력 92토큰, 요청 1회뿐이었습니다. 지연은 기록하지 않았고 현재 가용성·일반 품질을 뜻하지 않습니다.

성공 응답에는 실제 측정 `analysis_latency_ms`와 정리된 모델·사용량·요청 수·캐시 상태를 추가했습니다. 캐시 사용량은 원래 요청의 것입니다. 당시 Day 4 실제 모델명·지연·토큰은 대기였습니다.

당시 **미실행 준비안**은 합성 기록 `d4-07`(영어 혼합), `d4-10`(한국어 복합), `d4-12`(부정 의도)의 최대 3회 요청, 자동 재시도 없음, 오류 후 중단입니다. 앱 DB를 읽거나 쓰지 않으며 명시적 공유 서비스 승인 후 실행하도록 했습니다. 이 명령은 이후 11월 16일 실행했습니다.

```powershell
.\.venv-clean\Scripts\python.exe backend/evaluate.py --mode jev --dataset backend/evaluation/day4-journals.json --ids 'd4-07,d4-10,d4-12' --limit 3 --reference-date 2026-11-14 --output backend/evaluation/day4-jev-results.json
```

당시 보고서에는 실제 Day 4 결과나 품질 주장이 없었으며 별도 실제 브라우저 흐름도 대기였습니다. 가로챈 브라우저 응답을 실제 검증으로 취급하지 않았습니다.

**English:** On November 14, only the earlier smoke request was live evidence. The capped command was prepared but not executed until November 16. Mocked browser responses were never treated as live verification.

## 6. 화면과 계획 변경

Review는 추출 수, 필요할 때 펼치는 원문·예측·모델, 짧은 검토 이유를 보여 줍니다. 없는 신뢰도는 `not provided`입니다. 누락 작업 양식은 분류·기한·우선순위·명시적 수동 승인을 지원합니다. 실패 입력과 기존 저장 UUID를 유지해 응답 유실을 재시도하며 초안은 원래 저장 기록과 연결합니다.

제목을 강조하고 확정 시작·시간·기한 초과 및 도래·배정 상태를 표시합니다. 긴급도·중요도·노력은 Task details로 옮겼습니다. All Tasks는 전체·진행·완료·배정·미배정 필터를 제공합니다. 완료 작업은 취소선을 유지합니다. 배정 이유는 펼칠 수 있고 기본 버튼·레이블·details와 보이는 포커스를 사용합니다.

Plan from now는 기본 꺼짐입니다. 오늘이면 서버가 서울 시각을 읽고 분 단위로 올림하여 새 배정 구간을 자릅니다. 미래 날짜는 전체 가용 시간을 씁니다. 기존 확정 예약·한도를 보호하며 지난 예약이 기준 시각 때문에 가용 시간 밖으로 잘못 표시되지 않게 합니다. 안 들어가는 작업은 남은 시간 이유를 제공합니다. 자정 올림 후에도 과거 배정은 없습니다. 최초 확정은 지나간 제안 시작을 409로 거절하지만 이미 확정된 재시도는 이후에도 안전합니다. 오래 기다렸으면 다시 생성하세요. 시각·에너지는 우선순위를 바꾸지 않습니다.

**English:** Review is clearer and supports missing-task entry. Planning from now excludes elapsed time for new placements, preserves confirmed reservations and rejects expired proposed starts.

## 7. 검증과 해결한 문제

- Python 전체 **108개 통과**. Day 1–3·Day 4 15개·호스팅·마이그레이션·저장·배정·확정 복구를 포함합니다.
- JavaScript **11개 통과**.
- Chrome **25개 시나리오 통과**(부모 포함 26개). 임시 SQLite·프로덕션 파일로 기록 → 추출 → 수정 검토 → 승인 → DB → 우선순위 → 가용 시간 → 제안 → 확정 → Today → Focus → 완료, 수동 저장 응답 유실 복구, 신뢰도·필터를 검사했습니다.
- 320·390·1280 반응형 통과. `frontend/test-results/`(Git 제외)에 이미지를 생성·확인했습니다. 빌드·`pip check`·공백 검사 통과, 기본 API 빌드 복원 완료.
- 새 브라우저 테스트 2개에서 엄격한 선택자 오류를 수정했고, 후속 검사에서 고정 시각 컨텍스트가 새 실제 날짜 흐름에 영향을 주는 문제를 확인하여 새 컨텍스트로 분리했습니다. 최종 전체 통과입니다. 한국어 미지원 검사는 삭제하지 않고 새 지원 동작을 검증하도록 바꿨습니다.
- 데이터 작성 초기에 PowerShell 표준 입력의 한글 인코딩 손실을 발견했습니다. 기준 결과 기록 전 UTF-8로 수정했고 필수 예제 테스트가 실제 구간을 확인합니다. 전후 보고서는 모두 수정된 데이터를 사용합니다.
- **당시 실제 Jev·모델 다운로드·배포·기존 데이터 쓰기 및 삭제 0회**입니다. 쓰기 검사는 임시 SQLite를 사용했습니다. 제한된 Node·Chrome 실행은 자동 승인된 샌드박스 외 실행으로 검사했습니다.

**English:** All automated checks passed using temporary data. Selector, clock-isolation and encoding issues were fixed before final results were recorded.

## 8. 남은 제한과 보류한 상황 정보

임의의 한국어 활용·생략 주어 및 시제·모르는 단독 명령형·구분자 없는 목록은 지원하지 못할 수 있습니다. 공유 기한·목적어·모호한 분류는 검토가 필요합니다. 첫 15개 후보만 처리하고 경고하며 `tonight`, `this weekend`는 비워 둡니다. 작고 합성된 개발 데이터이며 신뢰도 임계값과 일반적인 실제 한국어 품질은 측정하지 않았습니다.

DB·UI 범위를 넓히지 않기 위해 일별 에너지 영구 입력은 보류했습니다. 기존 선택적 인터페이스는 `{energy_level: "low" | "medium" | "high", source: "user", valid_for_date: "YYYY-MM-DD"}`입니다. 향후 medium을 “Normal”로 표시하고 날짜별 `daily_context`를 GET/PUT으로 명시적 저장할 수 있습니다. 장기 선호와 분리하고 사용자 확인을 받아야 하며 감정을 추론하거나 우선순위를 몰래 바꾸지 않아야 합니다. 진단·프로파일링·학습·감정 이력은 추가하지 않았습니다.

Day 3의 하루 계획·임시 시간·완료 예약·로컬 단일 사용자 제한은 유지합니다. 전체 새로 고침 후 미저장 초안·제안은 유지하지 않습니다. 실제 평가·브라우저 승인은 당시 대기였고 이후 완료 내역은 위와 상태 문서에 있습니다.

**English:** Language rules remain limited and require review. Persistent daily energy is deferred. No emotion inference, profiling or learning was added.

## 9. 당시 제안한 Day 5 제출 작업

승인 후 제한 평가를 실행하고 영어·한국어 오류와 실제 모델·지연·사용량을 모의 지표와 분리하도록 제안했습니다. 실제 브라우저 흐름, 제출 스크린샷·시연 안내, 제한 검토, 깨끗한 설치 확인도 제안했습니다. 소수 데이터로 일반 정확도를 주장하지 않도록 했습니다. **원래 Day 4 기록 시점에는 Day 5를 시작하지 않았습니다.** 이후 제한 평가·실제 흐름·제출 자료·최종 검사 완료는 [STATUS.md](STATUS.md), [DEMO_GUIDE.md](submission/DEMO_GUIDE.md)를 참고하세요.

**English:** The original Day 5 suggestions were live evaluation, browser verification and submission preparation. Those selected tasks have since been completed; broader model validation remains future work.
