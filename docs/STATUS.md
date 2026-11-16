# ToGas 검증 현황 — 2026년 11월 16일

오프라인 P0 흐름을 구현·검증했습니다. 공식 TypeSafe Jev 어댑터는 초기 연결 시험과 11월 16일의 기록 3건 제한 평가를 통과했고, 실제 서비스를 사용하는 전체 브라우저 흐름도 같은 날 통과했습니다. 전반적인 실제 모델 품질은 측정하지 않았습니다.

**English:** The offline MVP, a three-journal live evaluation and the complete real-service browser workflow passed. General model quality remains unmeasured. Historical checkpoints below retain their original scope and call counts.

## 11월 16일 실제 서비스 브라우저 검증

[SUBMISSION.md](SUBMISSION.md)에 시연 순서·보존 스크린샷·범위·제한을 정리했습니다. 최종 새 설치, 백엔드 108개(새 임시 환경 포함), JavaScript 11개, 프로덕션 브라우저 시나리오 25개, 기본 API 주소 빌드가 통과했습니다. Review의 소수 긴급도를 실제 모델 값으로 표시하도록 수정했고, 모의 호스팅 브라우저 회귀로 표시값·저장값을 확인했습니다. 제출 준비 중 추가 실제 호출은 없었습니다. Day 4 구현·실제 검증·제출 자료는 커밋 `8326e61`로 함께 반영했습니다.

- **통과 흐름:** 합성 기록 독립 저장 → 실제 Jev 분석 → 제목·긴급도·중요도·시간 편집 → 명시적 승인 → 원본 기록 연결 저장 → 우선순위 배정 설명 → 가용 시간 저장 → 일정 확정 → Today 추천 → Focus 완료 → 새로 고침 후 완료 유지.
- 실제 분석·저장 작업은 [live-workflow-results.json](../backend/evaluation/live-workflow-results.json)에 있습니다. 포트 18000/15173의 임시 SQLite·임시 프로덕션 파일을 사용했습니다. 기존 DB·비공개 설정·기본 빌드는 변경하지 않았고 임시 서버·Chrome은 종료했습니다.
- 브라우저 세션 실제 요청은 정확히 2회이며 서비스 자동 재시도는 없었습니다. 첫 분석은 성공했지만 엄격한 Urgency 선택자 때문에 자동화가 중단되어 수정 후 별도 실행이 통과했습니다. 입력 1,170·출력 184토큰, 모델 `jev-1.14.0`, 전체 분석 지연 494.796ms(첫 시도)·353.412ms(전체 성공)입니다.
- 승인 전에는 작업이 없었습니다. 성공한 임시 DB에 기록 1개와 완료 작업 1개가 남았고 원본 연결·확정 시작을 유지했습니다. 처리되지 않은 브라우저 JavaScript 오류가 없고 390/1280 화면에서 가로 넘침이 없었습니다. 스크린샷을 확인했습니다.
- 이미지 경로는 `frontend/test-results/live-workflow/`(Git 제외)이며 제출용은 `docs/screenshots/`에 보존했습니다. 재현하려면 `frontend`에서 `$env:TOGAS_RUN_LIVE_WORKFLOW='1'` 설정 후 `node tests/live-workflow.mjs`를 실행합니다. 실행당 실제 분석 제출 1회를 허용하고 설정된 수업용 키를 사용합니다. 포트 18000/15173이 비어 있어야 합니다. 일반 오프라인 검사와 분리된 진단입니다.
- 하루 전체 계획을 사용했으므로 00:00 배정은 예상 동작입니다. 이 실행으로 실제 Jev의 현재 시각부터 계획 경로까지 검증한 것은 아닙니다. 일반 정확도·신뢰도 보정 수준은 여전히 측정하지 않았습니다.

**English:** The complete real-service workflow passed with isolated data and no browser errors. Two live requests were used because the first run stopped on an automation selector issue. Submission materials and final checks are complete.

## 11월 16일 실제 평가

- 승인받은 요청 3회를 `jev-1.14.0`으로 완료했습니다. 모두 캐시가 아닌 응답이고 서비스 오류는 없습니다. [day4-jev-results.json](../backend/evaluation/day4-jev-results.json)에 저장했습니다.
- 영어 감상·의도 혼합 문장은 학습 작업 1개, 한국어 복합 문장은 학습·개인 작업 2개, 영어 부정 의도는 작업 0개였습니다. 예상 구간·분류 3개와 명시적 날짜 2개가 일치했습니다. 이 선택된 부분집합에서만 정밀도·재현율·F1·정확한 개수 비율이 1.0입니다.
- 전체 분석 지연은 512.811·196.285·186.150ms, 입력 2,053·출력 364토큰입니다. 네트워크만이 아니라 로컬 분석도 포함한 시간입니다.
- 재현을 위해 기준일 11월 14일을 유지하여 tomorrow는 11월 15일입니다. 한국어 두 번째 행동은 기한을 비워 두고 공유 기한 경고를 유지합니다. 한국어 제안 2개 모두 긴급도 불확실성 경고가 있습니다.
- 추출 오류는 없었지만 감상 전용·완료 전용 문장과 신뢰도 보정은 이 부분집합으로 검사하지 않았습니다. 일반적인 영어·한국어 품질은 알 수 없습니다.
- 앱 DB·비공개 설정을 바꾸지 않았습니다. 이후 실제 브라우저 검증도 위와 같이 통과했습니다. **이하 Day 1–4 항목은 과거 시점의 검증 기록이며 호출 수·미완료 표현도 당시 기준입니다.**

**English:** Three selected live journals matched expected tasks, categories and explicit dates with no service errors. These results do not establish general accuracy.

## 기능 현황

| 기능 | 상태 | 근거·제한 |
| --- | --- | --- |
| Today 대시보드 | 동작·검증 완료 | 오늘 작업·완료 수·진행률·추천 이유 |
| 기록 저장·이력 | 동작·검증 완료 | 독립 저장·편집기 포커스·실패 입력 유지·안전한 재시도·분석 재사용 |
| 작업 관리 | 동작·검증 완료 | 추가·편집·분류·긴급도·기한·완료·재개·삭제·저장 |
| 우선순위·일정 | 로컬 동작·검증 완료 | 중요도·시간·노력·다중 가용 시간·제안 및 확정·오래된 계획과 재시도 보호 |
| 작업 추출 | 구현·연결 시험 및 실제 기록 3건 검증 | 선택된 영어·한국어·부정 사례 통과, 일반 품질 미측정 |
| AI 검토 | 오프라인·응답 가로채기 검증 완료 | 정보 편집·원문·실제 및 누락 신뢰도·수동 추가·승인 및 거절·중복 방지 |
| Jump Start | 동작·검증 완료 | 기한·긴급도·중요도 규칙, Jev 호출 없음 |
| 단일 작업 Focus | 동작·검증 완료 | 한 작업·완료·대시보드·실패 재시도 |
| 검색 | 동작·검증 완료 | 제목·기록의 대소문자 무시 문자열 검색 |
| 로컬 OpenJevX | 구현, 실제 가중치 미검증 | 검토한 로컬 파일만 사용, 자동 다운로드 없음 |
| 수업용 Jev API | 연결·제한 평가 검증 | 공식 TypeSafe·Bearer 키·`jev-1.14.0`, 광범위 평가 미완료 |

**English:** Core journal, task, review, planning, search and Focus features are verified. Local OpenJevX and broader model quality remain unverified.

## 자동 검증과 이전 연결 근거

- 깨끗한 Python 3.12 환경에서 백엔드 108개 통과. Day 1–3 회귀 및 Day 4 언어·지표·모의 호스팅 정규화·신뢰도·실패 보존·고정 시각 현재 시각부터 계획을 포함합니다.
- JavaScript 11개 통과. 계획 정보·작업 저장 재시도 ID·서울 자정 경계를 포함합니다.
- 프로덕션 파일·임시 SQLite로 Chrome 25개 시나리오 통과. 응답 유실 후 수동 추가, 누락 신뢰도, 필터, 현재 시각부터 계획 UI, 기록 → 검토 → 작업 → 우선순위 → 확정 일정 → Today → Focus → 완료를 포함합니다.
- 잠금 파일·WebAssembly Rollup으로 프로덕션 빌드와 깨끗한 `npm ci` 통과. 의존성 검사도 통과했으며 깨끗한 환경에는 Hugging Face·ONNX Runtime·토크나이저 패키지가 없습니다.
- 기존 시작 스키마를 두 번 시작하여 마이그레이션을 검사했고 이전 작업 행을 유지했습니다.
- 생성·승인·기록 저장·분석·편집·Focus 완료 실패에도 입력·저장 기록이 사라지지 않음을 확인했습니다.
- 320·390·1280 너비 검사와 모바일·데스크톱 이미지 확인을 완료했고 처리되지 않은 JavaScript 오류가 없었습니다.
- 데이터 쓰기 검사는 임시 DB를 사용했으며 사용자 앱 DB를 수정하지 않았습니다.
- 11월 16일 추가 검증 전 실제 근거는 합성 문장 연결 요청 1회였습니다. 당시 추가 실제 평가·모델 다운로드·원격 Python 실행·게시·배포는 없었습니다. 자동 HTTP 검사는 모의 전송을 사용합니다.

브라우저 실행기는 부모 1개와 시나리오 25개이므로 요약은 테스트 26개 통과입니다.

**English:** Automated checks use isolated data and mocked transports. The earlier single smoke request is historical evidence; the later five live requests are recorded above.

## Day 2 당시 기록

로컬 기록·AI 검토는 완료했지만 준비된 혼합 기록 실제 검사를 실행하기 전까지 **Day 2의 실제 Jev 검증은 완전하지 않다**고 기록했습니다.

- 입력·독립 저장·이력·반복 분석·모델 실패 처리를 구현·검사했습니다.
- 저장 UUID로 커밋 후 응답 유실을 재시도해도 행이 늘지 않습니다. 같은 UUID에 다른 내용은 409이며 의도적인 새 동일 기록은 가능합니다. 기존 데이터로 추가형 스키마를 검사했습니다.
- Dr./Prof.·소수·URL·목록·세미콜론·한국어 문장부호·명시적 1인칭 행동절을 검사했습니다.
- 검토 카드는 원문과 낮은 신뢰도·임시 분류 및 긴급도·잘린 제목을 설명합니다. 모의 신뢰도를 모델 근거로 제시하지 않고 데모 설명을 표시합니다.
- Open entry는 편집기로 이동·포커스합니다. 빈 추출과 검토 완료를 구분하고 저장 기록으로 돌아갈 수 있으며 캐시 결과임을 표시합니다.
- `backend/evaluate_journals.py`와 `backend/evaluation/day2-journals.json`에 영어·한국어 혼합 기록 검사를 준비했습니다. 당시 모의 실행은 한국어 의도 1개를 놓쳤으며 모의 품질과 Jev 품질은 다름을 보여 줍니다.
- **Day 2 추가 실제 호출은 없었습니다.** 합성 기록별 1회, 최대 2회·자동 재시도 없음·앱 데이터 접근 없음의 후속 검사를 제안했습니다.

**English:** Day 2 implemented independent journal saving and review reliability. Its prepared mixed-journal live check was not run at that checkpoint.

## 이전 신뢰성 개선 기록

Day 2.5 목록 이전에는 작업 관리와 Today → Jump Start → Focus 신뢰성을 다뤘습니다. 다음 수정은 유지되지만 당시 제안한 Day 3 일정 구조 구현은 아니었습니다.

- 선택적 작업 UUID로 응답 유실 재시도는 기존 행을 반환하고 동시 요청도 하나만 생성합니다. 수동 저장·승인의 ID를 세션 내 유지합니다.
- 추가 요청 확인 테이블로 기존 작업·원본 기록을 보존합니다. 재시작 후에도 남고 충돌 내용·삭제 작업 재시도는 409입니다. 수정·완료를 되돌리지 않으며 기본값·공백 제거 제목을 정규화해 비교합니다.
- Reload workspace로 커밋 작업을 발견한 뒤 ID로 병합하여 중복 목록을 막습니다. 별도 성공 저장은 새 ID라 의도적 동일 작업은 가능합니다.
- 브라우저 날짜는 Asia/Seoul로 맞춰 다른 시간대에서도 백엔드 완료 수와 일치시켰습니다.
- 당시 기한 초과 → 오늘 → 내일 → 기한 없음 → 미래 순서, 긴급도·기한·ID 동률, 완료·반복 완료·재개·다음 날 수를 추가 검사했습니다. 모델 호출은 없습니다.
- 백엔드 60개·JavaScript 10개·Chrome 18개·의존성·빌드 통과. Node 자식 프로세스 제한은 자동 승인된 외부 실행으로 검사했습니다. 포트 18000/15173·임시 SQLite를 사용하고 기본 API 빌드를 복원했습니다.
- 실제 Jev·모델 다운로드·배포·기존 앱 DB 변경은 없었습니다. 실제 모델·브라우저 검증은 당시 별도 대기 항목이었습니다.

재시도 ID는 브라우저 세션 내에서만 유지합니다. 내용을 바꾸면 새 요청이므로 불확실한 실패 뒤에는 그대로 재시도하거나 Tasks를 먼저 확인하세요.

**English:** Retry IDs and durable receipts prevent duplicates without undoing edits or completion. At this checkpoint, 60 backend tests, 10 JavaScript tests and 18 browser scenarios passed.

## Day 2.5 당시 기록

Day 3 전 추출 안정화를 완료했습니다. 예제·제한·제안 구조는 [Day 3 준비 기록](DAY3_READINESS.md)에 있습니다. 당시 일정은 설계뿐이었고 이후 별도 요청으로 구현했습니다.

- `meet friend. cook for tonight.`는 제안 2개입니다. 안전한 영어 행동 목록만 나누고 공유 목적어·인용·괄호는 유지합니다. 전체 원문·검토 이유를 보존합니다.
- 명시적 의도 문법으로 새 동사를 지원하고 검사한 감상·완료·부정을 거절합니다. 공식 Jev 어댑터와 기존 일괄 요청은 유지했습니다.
- **당시** 한국어 복합 분리는 미지원이어서 `내일 과제를 제출하고 친구를 만나야 해.`는 온전한 후보 1개였습니다. 기본 의무·단독 작업은 오프라인 검사했습니다.
- 백엔드 74개·JavaScript 10개·Chrome 19개·빌드 통과. 임시 DB만 쓰고 실제 호출·기존 데이터 변경은 없었습니다.
- 이 시점은 준비·설계에서 중단했고 이후 Day 3 구현은 별도 요청받았습니다.

**English:** Day 2.5 stabilized extraction and passed 74 backend tests, 10 JavaScript tests and 19 browser scenarios. Korean compound splitting was still unsupported then.

## Day 3 당시 기록

구현·검증을 완료했습니다. [DAY3_REPORT.md](DAY3_REPORT.md)에 기능·알고리즘·스키마·API·파일·근거·제한이 있습니다.

- 중요도·시간·노력·수동 확정 시작을 펼침 필드에서 편집합니다. 모르는 추정은 null, 계획 임시값은 30분으로 표시합니다.
- 날짜별 다중 비중첩 시간대·하루 한도를 저장합니다. 확정 전에는 배정이 저장되지 않고 거절해도 시간은 바뀌지 않습니다.
- 결정적 순위·가장 이른 빈 구간 배정이 확정 시작·가용 시간·수용량을 보호하고 미배정·충돌 이유를 제공합니다. 노력·상황은 순위를 바꾸지 않습니다.
- 원자적 확정·재시도·오래된 작업 및 설정 보호가 있습니다. 완료·편집은 시작을 유지하고 겹침 변경은 거절합니다. 기존 데이터·이전 요청 확인 정보는 추가 마이그레이션으로 보존합니다.
- Today의 시간순 확정 작업·그 밖의 작업·기한 초과·충돌 및 Jump Start·검토·Focus를 검사했습니다.
- 백엔드 93개·JavaScript 11개·Chrome 23개·빌드·의존성 통과. 실제 호출·기존 DB 변경 및 삭제 없음. 이후 Day 4는 별도 요청받았습니다.

**English:** Day 3 added scheduling and passed 93 backend tests, 11 JavaScript tests and 23 browser scenarios, without live calls.

## Day 4 당시 기록

로컬 구현·검증을 완료했습니다. [DAY4_REPORT.md](DAY4_REPORT.md)에 변경·지표·검증·제한·정확한 제한 호출 명령이 있습니다.

- 시작 커밋 `7b72baf`는 Day 3 문서와 일치했습니다. 공식 어댑터·규약·DB 스키마는 유지했습니다.
- 영어 절·감상·시간 도입과 제한적 한국어 복합 분리를 개선했습니다. 필수 예제 12개가 모의 모드에서 통과하고 원문·명시적 날짜·이유를 유지합니다. 구분자 없는 모호한 문장은 후보 1개와 경고로 남깁니다.
- 기존 평가기를 합성 기록 40개·행동 구간 일대일 대응·후보 누락 및 분류 누락 진단으로 확장했습니다. 모의 정밀도 97.62%, 재현율 95.35%, F1 0.9647, 개수 39/40, 분류 37/42, 날짜 14/14입니다. 감상·완료 전용 5건의 오탐은 0이며 실제 Jev 품질은 아닙니다.
- 누락 작업 수동 추가·재시도 보호, 없는 신뢰도 null/`not provided`, 실제 수치·모델·사용량·분석 시간 펼침을 제공합니다. 모의 신뢰도는 숨깁니다.
- 제목·시간 강조, 간결한 정보·필터, 선택적 현재 시각부터 계획을 추가했습니다. 고정 시각 검사로 서울 기준·자정·미래·확정 보호·지나간 시작 거절을 확인했습니다. 하루 전체가 기본입니다.
- 감정만 있는 기록을 보존하며 작업을 지어내지 않습니다. 일별 에너지·상황 영구 저장은 보류했고 감정 추론·학습은 없습니다.
- 백엔드 108개·JavaScript 11개·Chrome 25개·빌드·의존성·공백 검사 통과. 임시 DB만 쓰고 실제 호출·다운로드·배포·기존 데이터 변경 및 삭제는 없었습니다.
- 당시에는 실제 3회 평가·브라우저 검증이 승인 대기였고 실제 근거는 11월 12일 연결 시험 1회뿐이었습니다. Day 4에서 중단했고 Day 5는 시작하지 않았습니다. 이후 완료 사항은 위 11월 16일 기록을 따릅니다.

**English:** Day 4 improved extraction and review, added optional planning from now, and passed 108 backend tests, 11 JavaScript tests and 25 browser scenarios. Live checks were pending then and completed later as recorded above.

## 자연어 처리 평가 준비 기록

`backend/evaluation/examples.json`의 영어·한국어 정답 예제 20개를 `backend/evaluate.py`로 평가해 예측·오류·행동 여부·분류·명시적 날짜를 기록합니다.

갱신된 기존 `mock-results.json`은 **모의 전용**으로 행동 여부 20/20·행동 예제 분류 12/12·날짜 12/12이며 혼합 기록 행동 여부 8개도 일치합니다. Day 4의 더 큰 데이터·전후 비교는 위에 있습니다. 작고 수작업인 규칙 결과이며 Jev 품질·일반 정확도가 아닙니다.

이전 부정·치과 분류 오류는 수정했지만 구분자 없는 경계·일부 분류는 남습니다. 당시 실제 품질·신뢰도 보정·호스팅 지연은 대기였습니다. 이후 소수 실제 지연은 기록했지만 전반적인 품질·보정은 여전히 알 수 없습니다.

**English:** Mock metrics measure rules on small handwritten fixtures. They do not establish Jev quality or calibrated confidence.

## 초기 실제 연결 시험

`https://api.typesafe.ai/v1/systemone`이 로컬 수업용 키를 수락했습니다. 판단 3종을 묶은 요청 1회에서 `jev-1.14.0`을 반환했습니다.

- 입력: “Meet my friend tomorrow.”, 기준일 2026-11-12.
- 행동 확률 0.98, 분류 personal, 긴급도 1.88.
- 분류 신뢰도 0.91, 긴급도 신뢰도 0.48, 검토 표시.
- 규칙으로 계산한 기한 2026-11-13.
- 입력 581·출력 92토큰.
- 자동 작업 저장 없음. `.env`는 mock 상태를 유지했고 키는 출력·결과 저장하지 않았습니다.

정리된 근거는 `backend/evaluation/jev-smoke.json`입니다. 이 초기 시점에는 이후 실제 호출이 없었으며 11월 16일의 추가 5회는 위에 별도 기록했습니다.

**English:** The earlier smoke request verified connectivity and response handling, not broad NLP quality.

## 현재 남은 검토 사항

1. 실제 전체 브라우저 흐름, 제한 평가, 제출 안내·스크린샷, 최종 설치 검사는 완료했습니다. 일반 개발은 모의 모드로 유지합니다.
2. 더 넓은 정답 데이터의 실제 평가는 향후 선택 작업이며 공유 서비스 사용을 명시적으로 결정해야 합니다. 모의 지표와 분리해 기록하세요.
3. 실제 결과가 더 쌓이면 신뢰도 임계값과 영어·한국어 예제를 재검토하세요. 연결 시험 1건이나 소수 평가로 일반 정확도를 추론하지 않습니다.

**English:** Submission preparation and current verification are complete. Broader live evaluation and confidence calibration remain optional future work.

## 제출 범위의 제한

인증·클라우드 동기화 없는 로컬 단일 사용자 데모입니다. 전체 새로 고침 후 미저장 초안은 유지하지 않습니다. 문장 분리·부정·날짜는 보수적인 규칙이며 긴 입력은 첫 15개만 분석한다고 경고합니다. `this weekend` 등은 수동 검토해야 합니다. 일반적인 실제 한국어 품질을 주장할 근거는 없습니다.

처음 제공된 시작 파일에는 Git 저장소가 없었습니다. 이 문서는 초기 Git 가져오기 전 엔지니어링 기록도 포함하며 이후 작업은 커밋으로 추적할 수 있습니다.

**English:** This remains a local demo with conservative language rules and limited model evidence. Historical pre-import checkpoints are documented here; later changes are tracked by Git.
