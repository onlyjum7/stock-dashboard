"""시세를 모아 data/market.json 으로 저장한다. GitHub Actions에서 주기 실행."""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
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
    for section in ("holdings", "macro"):
        for row in config.get(section, []):
            if row["ticker"] not in tickers:
                tickers.append(row["ticker"])
    return tickers


def extract_quotes(frame, tickers: list[str]) -> dict[str, dict]:
    """일봉 프레임에서 티커별 최신 종가·직전 종가·차트용 일별 히스토리를 뽑는다."""
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
        history = [
            {
                "date": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
                "close": round(float(v), 4),
            }
            for ts, v in closes.items()
        ]
        quotes[ticker] = {
            "price": round(last, 4),
            "prev": round(prev, 4),
            "change": round(change, 4),
            "pct": round(pct, 2),
            "history": history,
        }
    return quotes


def extract_history(frame, tickers: list[str], fmt: str) -> dict[str, list[dict]]:
    """일봉이 아닌 다른 간격(분봉 등)의 프레임에서 날짜/종가 배열만 뽑는다."""
    out: dict[str, list[dict]] = {}
    for ticker in tickers:
        try:
            closes = frame[ticker]["Close"].dropna()
        except (KeyError, TypeError):
            continue
        out[ticker] = [
            {
                "date": ts.strftime(fmt) if hasattr(ts, "strftime") else str(ts),
                "close": round(float(v), 4),
            }
            for ts, v in closes.items()
        ]
    return out


def resample_weekly(daily_history: list[dict]) -> list[dict]:
    """일봉 히스토리를 주 단위 마지막 종가로 뭉친다. 날짜 형식이 아니면 원본을 그대로 둔다."""
    weeks: OrderedDict[str, dict] = OrderedDict()
    for point in daily_history:
        try:
            d = date.fromisoformat(point["date"])
        except ValueError:
            return daily_history
        iso = d.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        weeks[key] = point
    return list(weeks.values())


def build_payload(
    config: dict,
    quotes: dict[str, dict],
    minute_history: dict[str, list[dict]] | None = None,
) -> dict:
    minute_history = minute_history or {}
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
            "chart": {
                "daily": quote["history"],
                "weekly": resample_weekly(quote["history"]),
                "minute": minute_history.get(row["ticker"], []),
            },
        })

    def decorate(section: str, history_limit: int | None = None) -> list[dict]:
        out = []
        for row in config.get(section, []):
            quote = quotes.get(row["ticker"])
            if not quote:
                continue
            item = {**row, **quote}
            if history_limit:
                item["history"] = item["history"][-history_limit:]
            out.append(item)
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
        "macro": decorate("macro", history_limit=130),
    }


def main() -> int:
    import yfinance as yf

    config = load_config()
    tickers = collect_tickers(config)
    holding_tickers = [row["ticker"] for row in config.get("holdings", [])]

    frame = yf.download(
        tickers=tickers,
        period="2y",
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

    minute_history: dict[str, list[dict]] = {}
    if holding_tickers:
        try:
            minute_frame = yf.download(
                tickers=holding_tickers,
                period="5d",
                interval="15m",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            minute_history = extract_history(minute_frame, holding_tickers, "%Y-%m-%d %H:%M")
        except Exception as exc:  # 분봉은 부가 기능이라 실패해도 전체를 막지 않는다.
            print(f"분봉 수집 실패(무시하고 계속): {exc}", file=sys.stderr)

    payload = build_payload(config, quotes, minute_history)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    print(f"저장 완료: {len(quotes)}/{len(tickers)} 종목, {payload['generated_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
