# ToGas — 생각을 행동으로 바꾸는 일정 관리 도우미

혼자 사용하는 로컬 생산성 앱입니다. **생각 기록 → 제안 검토 → 다음 할 일 추천 → 한 가지 작업에 집중**하는 흐름을 지원합니다.

React/Vite 프런트엔드, FastAPI 백엔드, SQLite 저장소로 구성됩니다. 할 일 문구는 원래 기록을 바탕으로 만들며, 사용자가 승인해야 실제 할 일로 저장됩니다. 시연 순서, 스크린샷, 검증 결과는 [제출 및 시연 안내](docs/SUBMISSION.md)를 참고하세요.

**English:** ToGas is a local, single-user planner. Write a journal, review task suggestions, plan your day, and focus on one task. Suggestions become tasks only after approval.

**현재 상태:** 기본 모드는 오프라인 데모(`mock`)입니다. 공식 TypeSafe Jev 연동은 초기 연결 시험과 2026년 11월 16일 기록 3건 평가를 통과했습니다. 사용 모델은 `jev-1.14.0`이며, 실제 서비스로 전체 브라우저 흐름도 검증했습니다. 데모는 규칙 기반 결과이며 Jev 예측이 아닙니다. 데모에는 키가 필요하지 않습니다. 일반적인 모델 품질은 아직 측정하지 않았습니다.

## Windows에서 실행하기

Python 3.12와 Node.js 22 이상이 필요합니다. Node 24에서 검증했습니다. 저장소 루트에서 실행하세요.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

두 번째 터미널에서 실행합니다.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

앱: http://127.0.0.1:5173 · API 문서: http://127.0.0.1:8000/docs

Python 실행 파일과 `npm.cmd`를 직접 사용하면 PowerShell의 활성화·스크립트 실행 정책 문제를 피할 수 있습니다. 시스템 보안 정책 변경은 필요하지 않습니다. Vite는 npm 재정의를 통해 [Rollup 공식 WebAssembly 대체 패키지](https://rollupjs.org/migration/#compatibility)를 사용하여 Windows Application Control에서 차단될 수 있는 네이티브 모듈을 대체합니다. 프런트엔드 버전은 잠금 파일에 기록되어 있습니다.

검증 당시와 같은 Python 의존성을 설치하려면 설치 명령에 `-c backend/constraints.txt`를 추가하세요. 기본·테스트 의존성과 선택적인 로컬 모델 패키지는 분리되어 있습니다. 로컬 모델 라이브러리 없이 새 환경을 설치하고 검증했습니다.

**English:** Run the backend and frontend in separate terminals. Open port 5173. Add `-c backend/constraints.txt` to install the verified Python dependency versions.

## 주요 기능

화면의 버튼 이름은 영어로 표시됩니다. 실제 화면 이름을 함께 안내합니다.

- **오늘(Today):** 기한 초과·오늘 기한·기한 없는 작업, 오늘 완료한 작업과 진행률을 표시합니다. 다음 할 일과 추천 이유도 확인할 수 있습니다.
- **기록(Journal):** 분석 없이 저장하거나 이전 기록을 열고 제안을 미리 봅니다. **Open entry**는 편집기로 이동해 입력 포커스를 맞춥니다. 같은 기록의 반복 분석은 저장된 항목을 재사용합니다. 저장 후 응답만 유실되어도 재시도 시 중복 저장하지 않습니다. 기록 수정은 새 버전으로 저장하며 기존 이력을 유지합니다.
- **검토(Review):** 추출 개수와 원문을 확인하고 제목·분류·기한·우선순위를 수정한 뒤 승인·거절합니다. 예측 상세 정보는 펼쳐 볼 수 있으며 없는 신뢰도는 `not provided`입니다. 누락된 작업도 직접 추가하고 승인할 수 있습니다. 화면 이동 중 미검토 제안과 실패 입력을 유지하며, 추출 결과가 없어도 기록 저장 여부를 안내합니다.
- **할 일(Tasks):** **All Tasks** 옆 **+**로 추가 양식을 엽니다. 전체·미완료·완료·일정 확정·미배정 필터를 제공합니다. **Task details**에서 우선순위를 확인합니다. 닫아도 초안은 유지하며 저장 성공 시 초기화합니다. 수정·완료·다시 열기·삭제를 지원합니다. 응답 유실 후 수동 저장·승인 재시도는 UUID를 재사용하며 **Reload workspace** 후에도 중복을 방지합니다.
- **검색(Search):** 작업 제목과 기록 내용에서 대소문자 구분 없이 문자열을 검색합니다. 한국어도 검색할 수 있습니다.
- **집중(Focus):** 한 작업에 집중하고 완료한 뒤 Today로 돌아갑니다. 완료 실패 시 작업을 열린 상태로 유지하여 재시도할 수 있습니다.
- **일정 계획(Planning):** **Today → Plan your day**에서 가능한 시간대와 하루 최대 작업 수를 저장합니다. **Generate plan**으로 만든 제안의 시간·미배정 이유를 확인한 뒤 **Confirm plan** 또는 **Reject plan**을 선택합니다. 확정 작업은 시간순으로 표시하며 소요 시간과 임시 추정 여부를 보여 줍니다. **Planning details**에서 중요도(1–5), 예상 시간, 노력 수준(1–5), 선택적인 수동 확정 시작 시간을 설정합니다. 예상 시간이 없으면 null로 유지하며 계획에 임시 30분을 사용한다고 표시합니다. 오래된 제안은 다시 생성해야 합니다. [Day 3 보고서](docs/DAY3_REPORT.md)를 참고하세요.
- **현재 시각부터 계획(Plan from now):** 오늘에만 선택할 수 있으며 서울 현재 시각 이전에 새 작업을 배정하지 않습니다. 기본값은 하루 전체 계획이고 미래 날짜는 전체 가용 시간을 사용합니다. 기존 확정 시간은 유지합니다. 제안 시작 시간이 확정 전에 지나면 다시 생성해야 합니다. **Why this task?**에서 배정 이유를 확인합니다.

**English:** Save journals, review suggestions, manage and search tasks, and focus. Save availability before generating a plan, then confirm it. “Plan from now” skips elapsed time today.

## AI 모드와 Jev 연결

`TOGAS_AI_MODE`의 기본값은 `mock`입니다. 화면에 데모 모드임을 표시하고 모의 신뢰도는 숨깁니다. 제안은 사용자 검토를 거칩니다. 일반 개발·자동 테스트에서는 Jev를 호출하거나 모델을 다운로드하지 않습니다.

데모 규칙은 명시적인 의도 표현과 `cook`을 포함한 제한적인 명령형을 감지합니다. 안전하게 분리할 수 있는 영어 병렬 행동·시간 도입절·감상과 의도가 섞인 문장·일부 한국어 복합 행동을 후보로 나누고 공유 목적어는 유지합니다. “내일 과제를 제출하고 친구를 만나야 해”는 후보 2개를 만듭니다. 분리 후보는 전체 원문과 공유 기한·목적어의 불확실성을 보존합니다. 알려지지 않은 단독 명령형, 임의의 한국어 활용, 구분자 없는 행동 나열은 제한 사항입니다.

환경 설정 예시는 `.env.example`입니다. 백엔드는 루트 `.env`를 읽되 명시적인 셸 환경 변수는 덮어쓰지 않습니다. 키를 채팅·소스·스크린샷·Git에 포함하지 마세요. `.env`는 Git에서 제외됩니다.

어댑터는 TypeSafe의 [공식 요청·응답 규약](https://docs.typesafe.ai/api/system-one)을 따릅니다. `POST https://api.typesafe.ai/v1/systemone`에 Bearer 인증과 `model`, `state`, `questions` 필드를 사용합니다. 키는 서버의 Authorization 헤더에만 넣습니다. 호스트는 고정이며 다른 게이트웨이나 리디렉션은 사용하지 않습니다.

실제 서비스를 사용할 때는 백엔드를 종료하고 루트에서 다시 실행하세요.

```powershell
$env:TOGAS_AI_MODE = "jev"
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

브라우저를 새로 고치면 Journal에 **Live Jev mode**와 **Organize with Jev**가 표시됩니다. `JEV_API_KEY`는 비공개 `.env`에서 읽고 `JEV_MODEL` 기본값은 `jev-latest`입니다. 오프라인으로 돌아가려면 백엔드를 종료하고 `$env:TOGAS_AI_MODE = "mock"`으로 설정한 뒤 재시작하세요. 기록 저장·작업 CRUD·앱 시작·상태 확인·추천에는 Jev를 호출하지 않습니다.

분석 1회는 최대 15개 후보와 각 후보의 판단 3종을 **HTTP 요청 1회**로 묶습니다. 성공한 동일 요청은 30분간 메모리에서 재사용합니다. 최대 32개이며 키·모델·텍스트·질문·기준 날짜로 구분합니다. 캐시 응답의 `request_count`는 0이며 사용량은 원래 요청 값입니다. 재시작하면 캐시가 초기화됩니다. 제한 시간은 30초이고 자동 재시도·리디렉션은 없습니다. 실패 시 모의 결과로 자동 전환하지 않습니다.

`backend/evaluation/jev-smoke.json`은 초기 연결 시험입니다. “Meet my friend tomorrow.”에서 개인 작업을 추출했고 행동 확률 0.98, 긴급도 1.88, 기한 2026-11-13을 기록했습니다. 낮은 긴급도 신뢰도로 검토 표시가 붙었으며 작업은 저장하지 않았습니다. 연결·응답 처리 검증이며 일반 자연어 처리 품질 평가는 아닙니다.

가상 환경에서 `python backend/check_jev.py`를 실행하면 합성 문장으로 **실제 요청 1회**가 발생합니다. `.env`와 앱 데이터는 바꾸지 않습니다. 연동 중 한 번 실행했으며 자동 테스트에 포함되지 않습니다.

로컬 OpenJevX는 선택 사항이며 **실제 가중치로 검증하지 않았습니다**. `backend/requirements-local-ai.txt`, `TOGAS_AI_MODE=local`, 검토된 `openjevx.py`·`openjevx.w8.onnx`·`tokenizer.json`·`config.json`을 가리키는 `TOGAS_OPENJEVX_DIR`가 필요합니다. 원격 Python 코드를 자동 다운로드·실행하지 않습니다. OpenJevX는 수업용 호스팅 Jev와 다른 커뮤니티 구현입니다. `disabled` 모드에서는 복구 가능한 분석 오류를 표시하며 수동 기능은 유지합니다.

**English:** Mock mode is offline. Use `TOGAS_AI_MODE=jev` and a private key for real analysis. Requests are batched and cached; failures never silently switch to mock. Local OpenJevX remains unverified.

## 날짜·추천·입력 검증

- 날짜는 ISO `YYYY-MM-DD`, 오늘·내일·모레, 요일과 구현된 영어 표현을 인식합니다. 단순 요일은 오늘을 포함한 다음 해당 요일이고 `next Friday`는 다음 달력 주의 금요일입니다. 기준일은 브라우저가 전달합니다. “이번 주말” 같은 모호한 날짜는 비워 두어 검토하게 합니다.
- Jump Start는 미완료 작업만 **기한 초과 → 오늘 기한 → 내일 기한 → 나머지** 순서로 고려합니다. 같은 그룹은 높은 긴급도, 높은 중요도, 빠른 기한, 오래된 ID 순입니다. 기한이 없는 작업은 기한 비교 동률에서 뒤에 둡니다. 노력 수준은 우선순위에 영향을 주지 않으며 모델 호출도 없습니다.
- Today는 진행 중인 기한 초과·기한 없음·오늘 기한 작업, 기한이 늦더라도 오늘 시작이 확정된 작업, 오늘 완료한 작업을 보여 줍니다. Today 날짜·분석 기준일·완료일 분류는 브라우저 시간대와 무관하게 Asia/Seoul입니다. 나머지 미래 작업은 All Tasks와 추천 대상에 남습니다.
- 제목은 앞뒤 공백 제거 후 1–250자입니다. 기록은 공백만일 수 없고 최대 10,000자이며 원래 형식을 보존합니다.
- 분류는 `study/work/personal/health/other`, 긴급도는 0–3의 유한한 JSON 숫자, 완료 여부는 JSON 불리언입니다. 알 수 없는 필드·잘못된 날짜·미지원 null 갱신은 거절합니다. 기한·예상 시간·확정 시작 시간은 명시적인 null로 지울 수 있습니다.
- 잘못된 입력은 읽을 수 있는 422, 빈 작업 갱신은 400, 없는 작업은 404, 분석 불가는 503을 반환합니다. 거절된 변경은 데이터를 바꾸지 않습니다.

**English:** Dates use Seoul time. Recommendations follow fixed deadline, urgency and importance rules. Inputs are validated; rejected updates leave data unchanged.

## 테스트와 평가

최종 검증에서 백엔드 108개, JavaScript 11개, Chrome 시나리오 25개, 의존성 검사와 프로덕션 빌드가 통과했습니다. 새 Python 환경과 깨끗한 `npm ci` 설치도 검증했습니다. 오프라인 전체 흐름은 기록부터 일정 확정·Focus 완료까지 포함합니다. 자동 호스팅 테스트는 모의 HTTP 응답을 사용합니다. [Day 4 보고서](docs/DAY4_REPORT.md)에 모의 결과 개선과 11월 16일 실제 평가를 기록했습니다. 실제 브라우저 결과는 `backend/evaluation/live-workflow-results.json`과 `docs/STATUS.md`에 있습니다.

루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe backend/evaluate.py --mode mock
.\.venv\Scripts\python.exe backend/evaluate.py --mode mock --dataset backend/evaluation/day4-journals.json --reference-date 2026-11-14
```

`frontend`에서 실행합니다.

```powershell
npm.cmd test
npm.cmd run test:browser
```

브라우저 명령은 먼저 프로덕션 파일을 빌드합니다. Chrome 설치 및 빈 포트 8000/5173이 필요합니다. 임시 서버·SQLite를 사용하므로 기존 앱 데이터는 바꾸지 않습니다. 다른 Python은 `TOGAS_TEST_PYTHON`, 설치된 Edge는 `TOGAS_BROWSER_CHANNEL=msedge`로 지정하세요. 브라우저 다운로드는 필요하지 않습니다. 실패 응답을 가로채는 시나리오와 실제 백엔드의 모의 파이프라인을 검사합니다. 부모 테스트를 포함한 요약은 26개 통과로 표시됩니다.

앱을 켠 채 검사하려면 테스트 터미널에 `TOGAS_TEST_API_PORT=18000`, `TOGAS_TEST_UI_PORT=15173`, `VITE_API_URL=http://127.0.0.1:18000/api`를 설정하세요. 추가 CORS 출처는 임시 백엔드에만 적용합니다. 종료 후 `VITE_API_URL`을 제거하고 `npm.cmd run build`로 기본 API 주소를 복원하세요.

생성 스크린샷은 Git에서 제외된 `frontend/test-results/`, 제출용 보존 파일은 `docs/screenshots/`에 있습니다. 영어·한국어 정답 예제 20개는 `backend/evaluation/examples.json`입니다. 평가기는 예측·오류·지표를 기록합니다. `mock-results.json`은 **Jev 평가가 아닙니다**. 작은 수작업 데이터로 일반 정확도를 주장할 수 없습니다. 전반적인 품질·신뢰도 보정·지연 시간 분포는 측정하지 않았습니다.

Day 4의 `backend/evaluation/day4-journals.json`에는 다중 작업 기록 40개가 있습니다. 행동 구간 일대일 대응으로 정밀도·재현율·F1, 정확한 작업 개수, 분류, 명시적 날짜, 감상·완료 문장의 오탐을 평가합니다. 합성 개발 데이터에서 모의 F1은 0.7273 → 0.9647, 정확한 개수는 30/40 → 39/40으로 개선되었습니다. **Jev 정확도나 독립 데이터에 대한 일반화 성능은 아닙니다.** 상세 결과는 `day4-baseline-mock-results.json`과 `day4-mock-results.json`입니다. 실제 응답에는 모델·사용량·전체 분석 지연 시간이 포함됩니다.

실제 평가는 명시적으로 실행합니다. 예: 가상 환경에서 `python backend/evaluate.py --mode jev --limit 1`. 호출 제한을 위해 `--limit`이 필수이며 첫 서비스·설정 오류 후 재시도 없이 중단합니다. 11월 16일 승인받은 기록 3건(`d4-07,d4-10,d4-12`)은 오류 없이 통과했습니다. 예상 작업 3개와 분류, 명시적 날짜 2개가 일치했고 부정 의도는 작업을 만들지 않았습니다. 입력 2,053·출력 364토큰, 전체 분석 186–513ms입니다. 결과는 `backend/evaluation/day4-jev-results.json`에 있습니다. 소수 합성 예제로 일반 정확도나 신뢰도 보정 수준을 판단할 수 없습니다.

Day 2의 `backend/evaluation/day2-journals.json`은 영어·한국어 기록 각 1개와 정답 구간 8개(의도·감정·완료 행동)입니다. `python backend/evaluate_journals.py --mode mock`으로 오프라인 검사합니다. 준비된 실제 명령 `python backend/evaluate_journals.py --mode jev --max-requests 2`는 최대 2회 합성 요청을 보내고 오류 후 중단합니다. 이 명령은 **실행하지 않았습니다**. `day2-mock-results.json`은 행동 여부 정답 8개와 일치하지만 Jev 품질 측정은 아닙니다.

검증 범위와 남은 제한은 [상태 기록](docs/STATUS.md)을 참고하세요.

**English:** Offline checks passed: 108 backend tests, 11 JavaScript tests and 25 browser scenarios. Three selected live journals also passed, but do not establish general accuracy. Live evaluation requires an explicit call limit.

## 저장 방식과 구조

SQLite는 Git에서 제외된 `backend/togas.db`에 저장합니다. 시작 시 필요한 기한·완료 시각·원본 기록·기록 저장 요청 열과 작업 생성 요청 확인 테이블을 추가하며 기존 기록을 삭제하지 않습니다. 연결은 명시적으로 커밋·롤백하고 닫습니다.

기록 생성은 선택적 UUID `request_id`를 받습니다. 같은 ID·내용의 재시도는 기존 항목을 반환하고 다른 내용은 409입니다. UI는 현재 세션에서 ID를 재사용하며 **New entry**는 새 요청을 시작합니다. 작업 생성도 선택적 UUID를 사용합니다. 동일 요청은 기존 작업을 반환하고 이후 수정·완료 상태를 되돌리지 않습니다. 다른 내용이나 삭제된 작업 재시도는 409입니다. 확인 정보는 서버 재시작·작업 삭제 후에도 남아 지연 재시도의 작업 재생성을 막습니다.

완료 시각이 없는 이전 작업은 All Tasks에 남지만 특정 날짜 완료 수에 넣을 수 없습니다. 중요한 DB는 업그레이드 전 백업하세요.

```text
backend/
  main.py                 HTTP 엔드포인트와 처리 흐름
  schemas.py              공통 입력 검증
  storage.py              SQLite 연결·마이그레이션·검색
  ai.py                   판단 어댑터와 결과 정규화
  segmentation.py         후보 분리와 보수적인 데모 규칙
  jev_api.py              공식 어댑터·일괄 요청·제한된 캐시
  settings.py             비공개 .env 로딩, 셸 설정 우선
  scheduling.py           날짜·Today·추천 규칙
  planning.py             우선순위·시간 배정·충돌 검사
  tests/                  API·입력·마이그레이션·판단 테스트
  evaluation/             정답 예제와 모드가 표시된 결과
frontend/src/
  main.jsx                앱 상태와 작업 흐름
  Journal.jsx / Review.jsx / Search.jsx / TaskList.jsx / TaskFields.jsx
  api.js / task-save.js    요청과 중복 생성 방지
```

구현 API: 상태 확인, 대시보드, 작업 CRUD, 기록 저장·목록, 검색, `/api/ai/analyze`(별칭 `/api/ai/extract`), 규칙 기반 `/api/ai/prioritize`, 가용 시간 GET/PUT, `/api/planning/propose`·`/api/planning/confirm`. Day 3에서 메타데이터·가용 시간·확정 요청 확인 테이블을 기존 데이터 삭제 없이 추가했습니다. 서울 현지 시각을 사용하며 제안만으로 시간은 저장하지 않습니다. 확정 시작은 유지하고 겹치는 수동 변경은 409로 거절합니다.

**English:** SQLite stores data locally. Additive migrations preserve records, and request IDs prevent duplicate saves. Schedules are saved only after confirmation.

## 향후 개선

오프라인 사용을 우선합니다. Qwen3-8B/Ollama 기반 로컬 AI를 Jev 대체 후보로 평가하고, 한국어 추출·독립 정답 평가, 새로 고침 후 초안 복구·로컬 백업, Windows 실행 간소화, 일정 재배정, 한국어 화면·접근성을 순서대로 개선할 계획입니다. 모두 향후 계획이며 현재 구현된 기능이 아닙니다. 현재 오프라인 분석은 규칙 기반 `mock`입니다. 자세한 구현 방향과 확인 기준은 [제출 안내의 향후 개선 계획](docs/SUBMISSION.md#향후-개선-계획)을 참고하세요.

**English:** Offline use comes first. Planned work includes local AI evaluation, better Korean extraction, draft recovery and backups, simpler Windows startup, rescheduling, and localization/accessibility. Qwen/Ollama is not integrated yet.

## 제한 사항

로컬 데모로 인증·클라우드 동기화·배포 보안은 없습니다. 드문 약어, 모호한 병렬 구조, 다양한 한국어 복합 표현, 공유 목적어·기한은 오해할 수 있습니다. 알려지지 않은 명령형이나 구분자 없는 행동 나열은 놓칠 수 있습니다. 모호한 후보는 원문과 검토 이유를 유지합니다. 분석당 첫 15개 후보만 처리하며 긴 입력은 경고합니다.

잘못된 행동 확률은 안전하게 오류로 처리합니다. 잘못된 분류·긴급도는 설명이 있는 임시값, 없는 신뢰도는 null입니다. 긴 제목은 원문과 비교할 수 있고 반복 의도는 자동 병합하지 않고 표시합니다. 모의 규칙은 불완전하며 Jev 품질을 나타내지 않습니다. 일별 에너지·상황 정보 영구 저장은 보류했습니다.

앱 내 화면 이동은 초안을 유지하지만 전체 브라우저 새로 고침은 미저장 초안과 기록·작업 재시도 ID를 유지하지 않습니다. 분석 전에 기록을 저장하면 모델 실패로부터 내용을 보호합니다. 같은 세션 재시도는 응답 유실 후 중복을 방지합니다. 작업 내용 변경은 새 요청이므로 불확실한 실패 뒤에는 그대로 재시도하거나 Tasks에서 저장 여부를 확인한 뒤 수정하세요. **Reload workspace**는 초안·재시도 상태를 유지하지만 전체 새로 고침은 유지하지 않습니다.

참조된 `Jev_Tutorial(1).ipynb`는 제공된 작업 공간에 없었습니다. XP·타이머·수익화·소셜·분석 기능은 추가하지 않았습니다.

**English:** This is a local demo without authentication or cloud sync. Review ambiguous language and dates manually. Only the first 15 candidates are analyzed. Save journals before analysis; unsaved drafts do not survive a full browser reload.
