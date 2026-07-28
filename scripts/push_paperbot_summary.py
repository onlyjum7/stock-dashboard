"""노트북에서 실행. paperbot 매매 DB를 요약해 data/paperbot.json 으로 올린다.

주의: 이 스크립트는 DB를 읽기 전용으로만 연다. 매매 로직이나 주문에는 일절 손대지 않는다.
사용법:  python scripts/push_paperbot_summary.py            # 기본 DB 경로 사용
         python scripts/push_paperbot_summary.py --push     # 커밋+푸시까지

공개 저장소이므로 금액(원)은 일절 내보내지 않는다. 시드 대비 % 와 건수만 기록한다.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "paperbot.json"
KST = timezone(timedelta(hours=9))

DEFAULT_DB = Path(
    r"c:/Users/onlyj/projects/자동매매 프로젝트(단타)/자동매매 프로그램(단타)/trades.db"
)

# 거래비용 — 자동매매 프로젝트 config.py 의 실측 상수와 동일하게 맞춘 값.
# (2026-07-16 영웅문 당일매매 실측: 일반주 왕복 0.90%)
COST_BUY_PCT = 0.35   # 매수 수수료
COST_SELL_PCT = 0.35  # 매도 수수료
COST_TAX_PCT = 0.20   # 증권거래세 (매도 시에만)

# 모의 계좌 시드 (자동매매 config.SEED_KRW, 2026-07-08 기준).
# 손익률의 분모로만 쓰고 출력 JSON 에는 넣지 않는다 — 공개 저장소이므로 금액 비노출.
DEFAULT_SEED_KRW = 49_249_723


def trade_cost(row: dict) -> int:
    """매매 1건의 왕복 수수료 + 증권거래세(원). 자동매매 daily_report._calc_cost 와 동일 식."""
    entry = float(row["entry_price"]) * float(row["qty"])
    exit_ = float(row["exit_price"]) * float(row["qty"])
    return int(entry * COST_BUY_PCT / 100 + exit_ * (COST_SELL_PCT + COST_TAX_PCT) / 100)


def trade_pnl(row: dict) -> int | None:
    """매매 1건의 순손익(원). 청산 안 된 건은 None."""
    if row.get("exit_price") in (None, "") or row.get("entry_price") in (None, ""):
        return None
    gross = (float(row["exit_price"]) - float(row["entry_price"])) * float(row["qty"])
    return int(gross - trade_cost(row))


def hold_minutes(row: dict) -> int | None:
    """진입~청산 보유 시간(분). HH:MM 형식이 아니면 None."""
    try:
        h1, m1 = (int(x) for x in str(row["entry_time"]).split(":")[:2])
        h2, m2 = (int(x) for x in str(row["exit_time"]).split(":")[:2])
    except (ValueError, KeyError, AttributeError):
        return None
    return (h2 * 60 + m2) - (h1 * 60 + m1)


def summarize(rows: list[dict], seed: float, recent_n: int = 12) -> dict:
    """청산된 매매 목록에서 승률·시드대비 손익률·MDD·일별 자산곡선을 계산한다."""
    closed = []
    for r in rows:
        pnl = trade_pnl(r)
        if pnl is None:
            continue
        cost_basis = float(r["entry_price"]) * float(r["qty"])
        closed.append({
            "date": str(r.get("date", "")),
            "ticker": str(r.get("ticker", "")),
            "name": str(r.get("name") or r.get("ticker", "")),
            "exit_reason": str(r.get("exit_reason", "")),
            "hold_min": hold_minutes(r),
            "pnl": pnl,
            "cost": trade_cost(r),
            "gross": pnl + trade_cost(r),
            # 개별 매매 손익률은 그 매매에 투입한 금액 기준 (시드 기준 아님)
            "pnl_pct": round(pnl / cost_basis * 100, 2) if cost_basis else 0.0,
        })

    empty = {
        "trades": 0, "win_rate": 0.0, "total_return": 0.0, "gross_return": 0.0,
        "cost_return": 0.0, "mdd": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "best": 0.0, "worst": 0.0, "period": None, "today": None,
        "equity": [], "recent": [], "by_reason": [],
    }
    if not closed:
        return empty

    closed.sort(key=lambda t: t["date"])
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]

    pct = lambda won: round(won / seed * 100, 2)  # noqa: E731 — 시드 대비 %

    # 일별 자산곡선 (시드를 100 으로 잡은 지수)
    by_day: dict[str, float] = defaultdict(float)
    for t in closed:
        by_day[t["date"]] += t["pnl"]
    equity, cum = [], 0.0
    for day in sorted(by_day):
        cum += by_day[day]
        equity.append({"date": day, "close": round((seed + cum) / seed * 100, 3)})

    # MDD — 일별 종가 기준 고점 대비 최대 하락률
    peak, mdd = 100.0, 0.0
    for point in equity:
        peak = max(peak, point["close"])
        mdd = min(mdd, (point["close"] - peak) / peak * 100)

    # 청산 사유별 성적 — 어떤 청산 로직이 돈을 벌고 잃는지가 이 봇의 핵심 지표
    reasons: dict[str, list[dict]] = defaultdict(list)
    for t in closed:
        reasons[t["exit_reason"] or "미상"].append(t)
    by_reason = sorted(
        (
            {
                "reason": name,
                "n": len(ts),
                "win_rate": round(sum(1 for t in ts if t["pnl"] > 0) / len(ts) * 100, 1),
                "contribution": pct(sum(t["pnl"] for t in ts)),
            }
            for name, ts in reasons.items()
        ),
        key=lambda x: x["contribution"],
    )

    last_day = equity[-1]["date"]
    today_trades = [t for t in closed if t["date"] == last_day]

    return {
        "trades": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 2),
        "total_return": pct(sum(t["pnl"] for t in closed)),
        "gross_return": pct(sum(t["gross"] for t in closed)),
        "cost_return": -pct(sum(t["cost"] for t in closed)),
        "mdd": round(mdd, 2),
        "avg_win": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0.0,
        "best": max(t["pnl_pct"] for t in closed),
        "worst": min(t["pnl_pct"] for t in closed),
        "period": {"from": equity[0]["date"], "to": last_day, "days": len(equity)},
        "today": {
            "date": last_day,
            "trades": len(today_trades),
            "return": pct(sum(t["pnl"] for t in today_trades)),
        },
        "equity": equity,
        "recent": [
            {k: t[k] for k in ("date", "ticker", "name", "exit_reason", "hold_min", "pnl_pct")}
            for t in list(reversed(closed))[:recent_n]
        ],
        "by_reason": by_reason,
    }


def read_trades(db_path: Path, table: str, mode: str | None) -> list[dict]:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        sql = f"SELECT * FROM {table} ORDER BY rowid"
        rows = [dict(r) for r in con.execute(sql)]
    finally:
        con.close()
    if mode:
        rows = [r for r in rows if str(r.get("mode", "")) == mode]
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB), help="trades.db 경로")
    ap.add_argument("--table", default="trades")
    ap.add_argument("--mode", default="live-mock", help="이 mode 값만 집계 (빈 값이면 전체)")
    ap.add_argument("--seed", type=float, default=DEFAULT_SEED_KRW, help="손익률 분모로 쓸 시드(원)")
    ap.add_argument("--push", action="store_true", help="git commit + push 까지 실행")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[에러] DB를 못 찾았다: {db_path}")
        return 1

    rows = read_trades(db_path, args.table, args.mode or None)
    payload = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "mode": args.mode or "all",
        **summarize(rows, args.seed),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    p = payload
    print(f"{p['mode']} · {p['trades']}건 · 승률 {p['win_rate']}% · "
          f"누적 {p['total_return']}% (비용 {p['cost_return']}%) · MDD {p['mdd']}%")
    print(f"→ {OUTPUT_PATH}")

    if args.push:
        subprocess.run(["git", "add", str(OUTPUT_PATH)], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", "paperbot 요약 갱신"], cwd=ROOT, check=False)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
