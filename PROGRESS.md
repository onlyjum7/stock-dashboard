# 진행 기록

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

- [ ] 첫 workflow 수동 실행 → 누락된 티커 있는지 확인
- [ ] paperbot trades.db 실제 컬럼명 확인 (`pnl_pct`가 맞는지)
- [ ] 필요하면 자산곡선 차트 추가
