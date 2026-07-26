"""가짜 일봉 데이터로 손익 계산 로직을 검증한다. (네트워크 불필요)"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_market import build_payload, collect_tickers, extract_quotes, load_config

PASS = 0
FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {label}: {got}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got={got} want={want}")


def fake_frame():
    tickers = ["005930.KS", "000660.KS", "012450.KS", "^KS11", "KRW=X"]
    closes = {
        "005930.KS": [76000, 80000],
        "000660.KS": [200000, 190000],
        "012450.KS": [600000, 660000],
        "^KS11": [3100.0, 3131.0],
        "KRW=X": [1380.0, 1374.9],
    }
    cols = pd.MultiIndex.from_product([tickers, ["Close"]])
    data = {(t, "Close"): closes[t] for t in tickers}
    return pd.DataFrame(data, columns=cols), tickers


def main():
    frame, tickers = fake_frame()
    quotes = extract_quotes(frame, tickers)

    print("[1] 등락률 계산")
    check("삼성전자 pct (76000->80000)", quotes["005930.KS"]["pct"], 5.26)
    check("SK하이닉스 pct (200000->190000)", quotes["000660.KS"]["pct"], -5.0)
    check("원달러 pct", quotes["KRW=X"]["pct"], -0.37)

    print("[2] 포트폴리오 손익")
    config = {
        "holdings": [
            {"name": "삼성전자", "ticker": "005930.KS", "qty": 10, "avg": 78000},
            {"name": "SK하이닉스", "ticker": "000660.KS", "qty": 3, "avg": 210000},
        ],
        "watchlist": [{"name": "삼성전자", "ticker": "005930.KS"}],
        "macro": [{"name": "KOSPI", "ticker": "^KS11"}],
    }
    payload = build_payload(config, quotes)
    p = payload["portfolio"]
    # 삼성: 80000*10=800000, 원가 780000 -> +20000
    # 하이닉스: 190000*3=570000, 원가 630000 -> -60000
    check("총 매입금액", p["total_cost"], 1410000)
    check("총 평가금액", p["total_value"], 1370000)
    check("총 손익", p["total_pnl"], -40000)
    check("총 수익률 %", p["total_pnl_pct"], -2.84)
    check("삼성 개별 손익", p["positions"][0]["pnl"], 20000)
    check("하이닉스 개별 수익률", p["positions"][1]["pnl_pct"], -9.52)

    print("[3] 결측 종목 방어")
    partial = extract_quotes(frame, tickers + ["없는종목.KS"])
    check("없는 티커는 건너뜀", "없는종목.KS" in partial, False)
    check("나머지는 정상 수집", len(partial), 5)

    print("[4] 실제 설정 파일 파싱")
    real = load_config(Path(__file__).resolve().parent.parent / "config" / "holdings.json")
    check("티커 중복 제거", len(collect_tickers(real)), len(set(collect_tickers(real))))
    check("보유종목 3개", len(real["holdings"]), 3)

    print(f"\n결과: {PASS} 통과 / {FAIL} 실패")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
