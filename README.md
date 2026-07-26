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

노트북에서 한 번만 확인:

```bash
python scripts/push_paperbot_summary.py --db "C:/경로/trades.db"
```

숫자가 맞으면 `--push`를 붙여 실제로 올린다.
매일 자동으로 올리고 싶으면 Windows 작업 스케줄러에 등록하면 된다.
이 스크립트는 DB를 **읽기 전용**으로만 열고 매매 로직에는 손대지 않는다.

## 알아둘 한계

- 시세는 Yahoo Finance 기준 **약 15~20분 지연**. 체결 판단용이 아니라 상황 파악용.
- GitHub Actions의 cron은 정확히 15분마다가 아니라 **몇 분씩 밀릴 수 있다**(무료 러너 특성).
- 장 마감 후에는 종가가 그대로 유지된다.
- Public 레포면 보유 수량·평단이 **누구나 볼 수 있다**. 숨기고 싶으면 Private 레포 +
  Pages 대신 로컬에서 열거나, `holdings.json`에서 수량을 1로 두고 수익률만 본다.
