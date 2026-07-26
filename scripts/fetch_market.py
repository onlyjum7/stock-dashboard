"""시세를 모아 data/market.json 으로 저장한다. GitHub Actions에서 주기 실행."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "holdings.json"
OUTPUT_PATH = ROOT / "data" / "market.json"
KST = timezone(timedelta(hours=9))


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def collect_tickers(config: dict) -> list[str]:
    tickers: list[str] = []
    for section in ("holdings", "watchlist", "macro"):
        for row in config.get(section, []):
            if row["ticker"] not in tickers:
                tickers.append(row["ticker"])
    return tickers


def extract_quotes(frame, tickers: list[str]) -> dict[str, dict]:
    """일봉 프레임에서 티커별 최신 종가와 직전 종가를 뽑는다."""
    quotes: dict[str, dict] = {}
    for ticker in tickers:
        try:
            closes = frame[ticker]["Close"].dropna()
        except (KeyError, TypeError):
            continue
        if len(closes) == 0:
            continue
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else last
        change = last - prev
        pct = (change / prev * 100) if prev else 0.0
        quotes[ticker] = {
            "price": round(last, 4),
            "prev": round(prev, 4),
            "change": round(change, 4),
            "pct": round(pct, 2),
        }
    return quotes


def build_payload(config: dict, quotes: dict[str, dict]) -> dict:
    positions = []
    total_cost = 0.0
    total_value = 0.0

    for row in config.get("holdings", []):
        quote = quotes.get(row["ticker"])
        if not quote:
            continue
        cost = row["avg"] * row["qty"]
        value = quote["price"] * row["qty"]
        total_cost += cost
        total_value += value
        positions.append({
            "name": row["name"],
            "ticker": row["ticker"],
            "qty": row["qty"],
            "avg": row["avg"],
            "price": quote["price"],
            "pct": quote["pct"],
            "cost": round(cost),
            "value": round(value),
            "pnl": round(value - cost),
            "pnl_pct": round((value - cost) / cost * 100, 2) if cost else 0.0,
        })

    def decorate(section: str) -> list[dict]:
        out = []
        for row in config.get(section, []):
            quote = quotes.get(row["ticker"])
            if not quote:
                continue
            out.append({**row, **quote})
        return out

    return {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "source": "Yahoo Finance (약 15~20분 지연)",
        "portfolio": {
            "positions": positions,
            "total_cost": round(total_cost),
            "total_value": round(total_value),
            "total_pnl": round(total_value - total_cost),
            "total_pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost else 0.0,
        },
        "watchlist": decorate("watchlist"),
        "macro": decorate("macro"),
    }


def main() -> int:
    import yfinance as yf

    config = load_config()
    tickers = collect_tickers(config)

    frame = yf.download(
        tickers=tickers,
        period="10d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    quotes = extract_quotes(frame, tickers)
    if len(quotes) < max(1, len(tickers) // 2):
        print(f"수집 실패: {len(quotes)}/{len(tickers)} 종목만 응답. 기존 파일 유지.", file=sys.stderr)
        return 1

    payload = build_payload(config, quotes)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    print(f"저장 완료: {len(quotes)}/{len(tickers)} 종목, {payload['generated_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
