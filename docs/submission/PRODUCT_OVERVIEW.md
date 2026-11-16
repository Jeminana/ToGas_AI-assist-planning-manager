# ToGas 제품 개요 / Product Overview

**생각을 검토 가능한 할 일과 하루 계획으로 바꾸는 AI 보조 생산성 앱**  
An AI-assisted application for turning thoughts into reviewable tasks and daily plans.

## 프로젝트 소개와 문제 / Introduction and Problem

ToGas는 React/Vite, FastAPI, SQLite로 만든 로컬 단일 사용자 앱이다. 대상은 학업·업무·생활 책임을 함께 정리하거나 개인 기록에서 할 일을 찾으려는 개인이다. 자유로운 기록에는 감상·완료한 일·미래 의도·기한이 섞인다. 이를 목록으로 옮기고, 무엇부터 할지 정하고, 실제 가능한 시간에 배치하는 과정이 프로젝트가 다루는 문제다.

기록·목록·달력 사이의 전환을 연결하는 것이 설계 목표이며, 사용자 조사나 생산성 향상·타 제품 대비 우위를 검증한 결과는 아직 없다.

**English:** ToGas is a local planner for individual study, work and personal tasks. It addresses the effort of turning mixed notes into tasks, priorities and feasible schedules. User benefits and comparative superiority have not been measured.

## 해결 방식과 주요 기능 / Solution and Features

**기록 → 추출 → 검토·승인 → 추천 → 일정 제안·확정 → 집중 → 완료**의 흐름을 제공한다. 예를 들어 공부할 내용을 적고, 제안을 study 작업으로 수정·승인한 뒤, 가능한 20분에 배정하고 Focus에서 완료할 수 있다.

| 기능 | 사용자에게 제공하는 결과 |
| --- | --- |
| Journal | 분석과 독립된 기록 저장·이력·다시 열기 |
| Extraction / Review | 한·영 후보·원문·검토 이유, 편집·거절·승인·누락 수동 추가 |
| Tasks / Search | 수동 추가·편집·삭제·완료·재개, 제목·기록 검색과 상태 필터 |
| Today / Jump Start | 오늘 작업·진행률·기한·다음 작업 추천과 이유 |
| Planning | 날짜별 시간대·하루 한도 저장, 배정·미배정 이유와 명시적 확정 |
| Focus | 한 작업에 집중하고 완료 후 Today로 복귀 |

**English:** Capture notes, review suggestions, manage tasks, inspect a next-task recommendation, confirm a daily plan and complete one task in Focus. Suggestions and proposed schedules require approval.

## 구조와 기술 / Architecture and Technologies

React 화면이 FastAPI를 호출하고 SQLite에 기록·작업·가용 시간·확정을 저장한다. Jev는 공식 TypeSafe API로 후보의 행동 여부·분류·긴급도를 판단한다. 후보 분리·날짜 해석·우선순위·시간 배정은 앱의 규칙이다. Pydantic으로 입력을 검증하고 요청 확인 정보로 저장 재시도 중복을 방지한다.

추천은 기한 그룹 → 긴급도 → 중요도 → 기한 → ID 순이다. 일정은 우선순위 순 가장 이른 연속 빈 구간에 배정하고 기존 확정 예약을 보호한다. 예상 시간이 없으면 임시 30분을 표시한다. 오늘은 선택적으로 **Plan from now**를 켜 지난 시간을 제외할 수 있다.

기본 `mock`은 준비된 환경에서 키·외부 모델 호출 없이 동작하는 규칙 기반 데모다. `jev`는 인터넷·비공개 API 키가 필요하다. 로컬 OpenJevX 로더는 있지만 실제 가중치는 미검증이며 Qwen/Ollama는 아직 통합하지 않았다.

**English:** React/Vite → FastAPI/Pydantic → SQLite forms the local stack. Jev assists interpretation; rules handle ranking and greedy scheduling. Default mock mode runs offline after setup. Hosted Jev is optional; a verified local learned model remains future work.

## 현재 결과 / Current Results

2026-11-16 기준 기존 검증 기록을 요약했다. 문서 작성 중 새로 측정한 실행 결과는 아니다.

| 근거 | 결과와 해석 |
| --- | --- |
| 기능 검사 | 백엔드 108개·JavaScript 11개·브라우저 25개 시나리오 통과, 새 설치·프로덕션 빌드 확인 |
| 모의 NLP | 동일 합성 개발 기록 40건에서 규칙 기반 F1 0.7273 → 0.9647, 정확한 작업 개수 30/40 → 39/40 |
| 실제 Jev | 선택한 기록 3건의 예상 작업 수 1·2·0, 분류 3개·명시적 날짜 2개 일치; 입력 2,053·출력 364토큰 |
| 실제 전체 흐름 | 기록→실제 분석→수정·승인→일정 확정→Focus 완료→새로 고침 후 유지 통과 |

실제 제한 평가 지연은 186.150–512.811ms로 로컬 처리를 포함한다. 실제 표본은 작으며 모의 수치를 Jev 정확도로 해석할 수 없다. 전체 기록된 실제 요청 6회에는 연결 시험·브라우저 재실행이 포함된다. 원자료와 상세 해석은 [최종 보고서](FINAL_PRODUCT_REPORT.md)에 있다.

**English:** Recorded results include passing functional checks, improved rule-based mock extraction on 40 development journals, three selected live Jev cases and a passing live browser workflow. These separate results do not establish general model accuracy or productivity gains.

## 제한과 향후 개선 / Limitations and Future Work

한국어 활용·모호한 행동 경계·공유 기한·일부 날짜는 수동 검토가 필요하며 첫 15개 후보만 분석한다. 일정은 하루 단위이고 인증·클라우드 동기화·개인화 학습·영구 초안 복구는 없다. 현재 UI 버튼은 영어다.

오프라인을 우선하여 Qwen3-8B/Ollama의 한·영 품질·메모리·지연을 평가할 계획이다. 이어 독립 정답 평가, 초안 복구·로컬 백업, 간단한 Windows 실행, 일정 재배정·다일 계획, 한국어 UI·접근성과 사용자 연구를 검토한다. 모두 향후 계획이다.

**English:** Language rules and live evidence are limited. Scheduling is single-day, and the app has no authentication, cloud sync or durable draft recovery. Future work prioritizes local AI evaluation, reliability, better Korean support and usability studies.

빠른 확인: [실행·5분 시연](DEMO_GUIDE.md) · [최종 보고서](FINAL_PRODUCT_REPORT.md) · [스크린샷과 검증 현황](../STATUS.md).
