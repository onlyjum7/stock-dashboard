"""노트북에서 실행. paperbot 매매 DB를 요약해 data/paperbot.json 으로 올린다.

주의: 이 스크립트는 DB를 읽기 전용으로만 연다. 매매 로직이나 주문에는 일절 손대지 않는다.
사용법:  python scripts/push_paperbot_summary.py --db "C:/경로/trades.db"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "paperbot.json"
KST = timezone(timedelta(hours=9))


def summarize(rows: list[dict]) -> dict:
    """청산된 매매 목록에서 승률·누적수익률·MDD를 계산한다."""
    closed = [r for r in rows if r.get("pnl_pct") is not None]
    if not closed:
        return {"trades": 0, "win_rate": 0.0, "total_return": 0.0, "mdd": 0.0}

    wins = sum(1 for r in closed if r["pnl_pct"] > 0)

    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in closed:
        equity *= (1 + r["pnl_pct"] / 100)
        peak = max(peak, equity)
        mdd = min(mdd, (equity - peak) / peak * 100)

    return {
        "trades": len(closed),
        "win_rate": round(wins / len(closed) * 100, 2),
        "total_return": round((equity - 1) * 100, 2),
        "mdd": round(mdd, 2),
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
    ap.add_argument("--db", required=True, help="trades.db 경로")
    ap.add_argument("--table", default="trades")
    ap.add_argument("--mode", default="live-mock", help="이 mode 값만 집계 (빈 값이면 전체)")
    ap.add_argument("--push", action="store_true", help="git commit + push 까지 실행")
    args = ap.parse_args()

    rows = read_trades(Path(args.db), args.table, args.mode or None)
    payload = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "mode": args.mode or "all",
        **summarize(rows),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.push:
        subprocess.run(["git", "add", str(OUTPUT_PATH)], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", "paperbot 요약 갱신"], cwd=ROOT, check=False)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
