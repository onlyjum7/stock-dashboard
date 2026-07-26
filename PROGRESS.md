# 진행 기록

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
- ② 코드상 완료 — yfinance 실제 호출. 샌드박스에서 외부망이 막혀 있어 미검증.
  첫 workflow 수동 실행으로 확인 필요
- ② 코드상 완료 — GitHub Actions 워크플로우, Pages 배포
- ③ 가설 — 한국 종목 티커 `.KS` 표기가 전 종목에서 동작할 것. 씨에스윈드(112610)는
  코스닥이라 `.KQ`일 가능성 있음. 첫 실행 후 누락 종목 확인할 것

## 다음 할 일

- [ ] 첫 workflow 수동 실행 → 누락된 티커 있는지 확인
- [ ] paperbot trades.db 실제 컬럼명 확인 (`pnl_pct`가 맞는지)
- [ ] 필요하면 자산곡선 차트 추가
