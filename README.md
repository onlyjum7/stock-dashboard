# 포트폴리오 상황판

GitHub Actions가 시세를 주기적으로 받아 `data/market.json`에 저장하고,
GitHub Pages에 올라간 `index.html`이 그 파일을 읽어 화면을 그린다.
노트북이 꺼져 있어도 시세 부분은 계속 갱신된다.

## 구조

```
GitHub Actions (15분마다)          내 노트북 (켜져 있을 때만)
   fetch_market.py                   push_paperbot_summary.py
        ↓                                     ↓
  data/market.json                    data/paperbot.json
        └──────────────┬──────────────────────┘
                  index.html  (GitHub Pages)
```

## 설치 (한 번만)

1. GitHub에서 새 레포 `stock-dashboard` 생성 (Public).
2. 이 폴더 전체를 올린다.
3. 레포 → Settings → Pages → Source를 `Deploy from a branch` / `main` / `/ (root)`로 지정.
4. 레포 → Settings → Actions → General → Workflow permissions를
   **Read and write permissions**로 변경. (봇이 갱신 결과를 커밋해야 하므로 필수)
5. 레포 → Actions 탭 → "시세 갱신" → **Run workflow** 버튼으로 첫 실행.
6. `https://onlyjum7.github.io/stock-dashboard/` 접속.

## 내 보유 종목 바꾸기

`config/holdings.json`만 고치면 된다. 코드는 안 건드려도 됨.

- `qty` 수량, `avg` 평균단가(원)
- 국내 종목 티커는 `종목코드.KS` (코스닥은 `.KQ`)
- 미국 종목은 심볼 그대로 (`MU`, `NVDA`)

## paperbot 성과 연결

노트북에서 실행한다. DB 경로는 기본값이 잡혀 있어 그냥 돌리면 된다.

```bash
python scripts/push_paperbot_summary.py           # 숫자만 확인
python scripts/push_paperbot_summary.py --push    # 커밋 + 푸시까지
```

- 다른 DB를 보려면 `--db "C:/경로/trades.db"`, 전체 모드를 보려면 `--mode ""`.
- 손익은 `entry_price`/`exit_price`/`qty`에서 직접 계산하고,
  **매수 0.35% + 매도 0.35% + 거래세 0.20%** 를 뺀 순손익이다
  (자동매매 쪽 `config.py` 실측 상수와 동일).
- 누적 손익률·MDD는 **시드 대비 %**. 매매별 수익률을 복리로 곱하면
  1회 주문이 시드의 20%인 봇에서는 수치가 크게 부풀려지기 때문.
- 올라가는 JSON에는 **금액(원)·수량·시드가 들어가지 않는다.** 퍼센트와 건수만 나간다.
- 매일 자동으로 올리고 싶으면 장 마감 후 시각으로 Windows 작업 스케줄러에 등록하면 된다.
- 이 스크립트는 DB를 **읽기 전용**으로만 열고 매매 로직에는 손대지 않는다.

## 알아둘 한계

- 시세는 Yahoo Finance 기준 **약 15~20분 지연**. 체결 판단용이 아니라 상황 파악용.
- GitHub Actions의 cron은 정확히 15분마다가 아니라 **몇 분씩 밀릴 수 있다**(무료 러너 특성).
- 장 마감 후에는 종가가 그대로 유지된다.
- Public 레포면 보유 수량·평단이 **누구나 볼 수 있다**. 숨기고 싶으면 Private 레포 +
  Pages 대신 로컬에서 열거나, `holdings.json`에서 수량을 1로 두고 수익률만 본다.
