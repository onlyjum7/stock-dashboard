# 진행 기록

## 2026-07-28 — paperbot 성과 대시보드 실동작

- ① 검증됨 — trades.db 실제 스키마 확인 결과 `pnl_pct` 컬럼은 **없다**. 기존
  push_paperbot_summary.py 는 없는 컬럼을 읽고 있어 실행해도 전부 0 이 나오는 상태였다.
  실제 컬럼: date/ticker/name/entry_time/exit_time/entry_price/exit_price/qty/
  exit_reason/condition/vwap_at_entry/mode/entry_* 지표들/max_runup_pct/max_drawdown_pct.
  → 손익을 entry/exit 가격과 수량에서 직접 계산하도록 재작성.
- 비용 모델을 자동매매 프로젝트 config.py 실측 상수와 동일하게 맞춤
  (매수 0.35% + 매도 0.35% + 거래세 0.20%, daily_report._calc_cost 와 같은 식).
  → 대시보드 수치와 봇 자체 일일 리포트가 어긋나지 않는다.
- 누적 손익률의 기준을 "매매별 수익률 복리 곱"에서 **시드 대비 %** 로 변경.
  1회 주문이 시드의 20%인 봇이라 복리 곱은 실제 계좌 수익률을 크게 왜곡한다.
  MDD도 일별 자산곡선(시드=100) 기준으로 다시 계산.
- 요약 JSON 확장: 기간·자산곡선(일별)·청산 사유별 기여도·최근 매매 12건·
  가격손익/비용손익 분리. 공개 저장소이므로 **금액(원)·수량·시드는 출력하지 않는다**(% 만).
- index.html paperbot 섹션 개편: KPI 4종 + 보조지표 5종 + 자산곡선 차트 +
  청산 사유별 기여도 막대 + 최근 매매 표.
- ① 검증됨 — 가짜 매매로 계산 로직 테스트 38개 전부 통과 (`test_paperbot_summary.py`).
  CI(계산 로직 테스트 스텝)에도 추가함.
- ① 검증됨 — 실제 DB(live-mock 53건)로 실행 → data/paperbot.json 생성.
  Playwright 로 로컬 렌더링 확인(콘솔 에러 0, 모바일 390px 가로스크롤 없음).
- 실측 결과 메모: 53건 / 승률 13.2% / 시드 대비 -7.28% / MDD -7.28%.
  이 중 **가격 손익은 -1.71%, 수수료·세금이 -5.58%** — 손실의 77%가 비용이다.
  자동매매 쪽 PROGRESS 의 "수수료 출혈" 진단과 같은 방향.

## 2026-07-27 (3차) — 보유종목 확대 차트 모달(분봉/일봉/주봉)

- 보유 종목 카드를 클릭하면 모달로 확대되고 분봉/일봉/주봉 탭을 전환할 수 있게 추가.
- fetch_market.py: 일봉 수집 기간을 6mo → 2y로 늘려 주봉(주 단위 리샘플)에 쓸 데이터 확보,
  보유종목 한정으로 5일치 15분봉을 별도 수집(yfinance 분봉은 장기 보관이 안 돼 최근 며칠만 가능).
  분봉 수집 실패 시에도 전체 파이프라인이 죽지 않도록 try/except로 격리.
- ① 검증됨 — Playwright로 로컬·실배포(GitHub Pages) 양쪽에서 카드 클릭 → 모달 오픈 →
  분봉/일봉/주봉 전환까지 스크린샷으로 확인. 콘솔 에러 2건(favicon, 아직 없는 paperbot.json)은
  기능과 무관한 예상된 404로 확인함.
- ① 검증됨 — GitHub Actions 워크플로우 재실행 성공(25초), data/market.json에 종목별
  daily/weekly/minute 히스토리 정상 포함.
- 참고 — GitHub Pages(legacy) 자동 리빌드가 봇 커밋 직후 바로 트리거되지 않는 현상이 이번에도
  발생. `POST /pages/builds`로 수동 리빌드해 반영 확인.

## 2026-07-27 (2차) — 실제 보유종목 반영 및 차트 UI 개편

- 사용자가 실제 보유 현황 스크린샷 제공 → config/holdings.json을 실제 5개 종목으로 교체:
  삼성전자(005930.KS), TIGER 미국테크TOP10 INDXX(381170.KS), TIGER 미국AI빅테크10(490090.KS),
  알파벳 A(GOOGL), 사운드하운드 AI(SOUN). 종목코드는 웹 검색으로 재확인.
- ① 검증됨 — 계산된 손익률이 스크린샷의 실제 손익률과 정확히 일치함을 확인
  (삼성전자 -19.52%, TIGER 미국테크 -2.55%, TIGER 미국AI -30.32%, 알파벳 -16.8%, SOUN -62.16%).
  단, 최초 입력 시 알파벳/SOUN의 USD 평단가가 서로 뒤바뀐 상태였고,
  결과 수익률(+1864%, -98.4%)이 비정상적으로 튀는 것을 근거로 사용자에게 확인을 요청해 정정함.
  → 평단가처럼 사용자가 직접 불러주는 숫자도 결과가 비상식적으로 나오면 재확인해야 함을 확인.
- Public 저장소 특성상 실보유수량 노출을 막기 위해 holdings의 qty를 전부 1로 고정
  (avg는 실제 평단가 유지 — pnl_pct 계산은 qty와 무관해 정확함).
- 관심종목(watchlist) 섹션 전체 제거 (config/fetch_market.py/index.html 모두 정리).
- ① 검증됨 — 보유종목·지수/환율/원자재를 표 대신 SVG 스파크라인(6개월 일봉) 차트로 개편.
  로컬 스크린샷 및 실배포(GitHub Pages) 스크린샷으로 렌더링 확인.
- fetch_market.py의 yf.download 기간을 10d → 6mo로 확장해 차트용 히스토리 확보.
- ① 검증됨 — GitHub Actions 워크플로우 재실행 성공(테스트 13/13 포함), data/market.json 자동 커밋 확인.
- 참고: GitHub Pages(legacy)가 봇 커밋에 대해 자동 빌드를 바로 트리거하지 않는 지연이 있었음.
  `POST /pages/builds`로 수동 리빌드 트리거 후 반영 확인. 다음에도 봇 커밋 직후 화면이 안 바뀌면
  같은 방법으로 수동 리빌드하면 됨.

## 2026-07-27 — GitHub 배포 및 공개 검증

- GitHub 레포 생성(public) 및 Pages 배포 완료:
  https://onlyjum7.github.io/stock-dashboard/
- ① 검증됨 — yfinance 실제 호출 성공 (로컬 12/12 종목, GitHub Actions에서도 12/12 종목 수신 확인).
  이전 PROGRESS.md의 "② 코드상 완료" 항목을 ①로 갱신함.
- ① 검증됨 — 씨에스윈드(112610.KS)는 `.KS` 표기로 정상 수신됨. `.KQ`로 바꿀 필요 없음.
  이전 "③ 가설" 항목을 ①로 갱신하고 결론을 확정함 (수정 불필요).
- ① 검증됨 — GitHub Actions 워크플로우("시세 갱신") 수동 실행 성공, data/market.json 자동 커밋 확인.
  단, 최초 실행 시 `actions/setup-python`의 `cache: pip` 옵션이 requirements.txt 부재로 실패하여
  requirements.txt를 신규 추가해 해결함 (사용자 승인 후 적용).
- ① 검증됨 — GitHub Pages 실제 서빙 확인 (200 응답, market.json의 generated_at이
  Actions 실행 시각과 일치).
- 공개 저장소이므로 개별 보유 종목의 실제 수량/평가금액이 노출되는 문제를 사용자와 협의:
  config/holdings.json의 각 보유종목 qty를 1로 변경(수익률 %는 수량에 무관하게 정확),
  index.html에서 총자산 요약 카드와 개별 금액 표시를 제거하고 수익률(%)만 노출하도록 수정.
- ② 코드상 완료 — paperbot 요약(push_paperbot_summary.py)은 노트북에서 아직 실행 안 함.
  data/paperbot.json 미생성 상태로, 대시보드에는 안내 문구만 표시됨.

## 2026-07-26 — 초기 구축

- 구조 확정: GitHub Actions(15분 주기) → `data/market.json` → GitHub Pages HTML
- 데이터 소스를 pykrx 대신 yfinance로 선택.
  이유: GitHub 러너가 미국 IP라 KRX 직접 조회가 차단될 위험이 있음.
- 작성 파일: `index.html`, `scripts/fetch_market.py`,
  `scripts/push_paperbot_summary.py`, `config/holdings.json`, `.github/workflows/update.yml`

검증 상태

- ① 검증됨 — 손익·등락률·MDD 계산 로직: 가짜 데이터로 테스트 21개 전부 통과
  (`test_fetch_market.py` 13개, paperbot 요약 8개)
- ① 검증됨 — paperbot 스크립트가 SQLite를 읽기 전용으로 열고 mode 필터가 동작함
- ① 검증됨 (2026-07-27 갱신) — yfinance 실제 호출. 로컬 및 GitHub Actions에서 12/12 종목 수신 확인됨.
- ① 검증됨 (2026-07-27 갱신) — GitHub Actions 워크플로우, Pages 배포. 실제 배포 화면 확인 완료.
- ① 검증됨 (2026-07-27 갱신) — 한국 종목 티커 `.KS` 표기가 전 종목에서 정상 동작함. 씨에스윈드(112610.KS)도
  `.KS`로 정상 수신되어 `.KQ`로 바꿀 필요 없음.

## 다음 할 일

- [x] 첫 workflow 수동 실행 → 누락된 티커 있는지 확인 (2026-07-27, 12/12 정상)
- [x] paperbot trades.db 실제 컬럼명 확인 → `pnl_pct` 없음, 가격에서 계산으로 해결 (2026-07-28)
- [x] 자산곡선 차트 추가 (paperbot 일별 자산곡선, 2026-07-28)
- [ ] paperbot 요약 자동 갱신 — 지금은 노트북에서 수동으로
      `python scripts/push_paperbot_summary.py --push` 를 돌려야 한다.
      장 마감 후(예: 16:10) Windows 작업 스케줄러에 걸면 자동화 가능.
- [ ] trades.db 의 name 컬럼이 종목코드로만 저장돼 있어 대시보드에도 코드로 나온다.
      종목명 매핑이 필요하면 자동매매 쪽에서 name 을 제대로 넣도록 고쳐야 함.
