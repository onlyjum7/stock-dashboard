"""가짜 매매 기록으로 paperbot 요약 로직을 검증한다. (DB·네트워크 불필요)"""

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push_paperbot_summary import hold_minutes, read_trades, summarize, trade_cost, trade_pnl

PASS = 0
FAIL = 0
SEED = 10_000_000


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {label}: {got}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}: got={got} want={want}")


def trade(date, ticker, entry, exit_, qty, reason, t1="09:00", t2="09:10", mode="live-mock"):
    return {
        "date": date, "ticker": ticker, "name": ticker,
        "entry_time": t1, "exit_time": t2,
        "entry_price": entry, "exit_price": exit_, "qty": qty,
        "exit_reason": reason, "mode": mode,
    }


def main():
    # 익절 1건(+20% 가격) + 손절 1건(-20% 가격) → 가격만 보면 본전, 비용만 남는 케이스
    win = trade("2026-07-01", "111111", 10_000, 12_000, 100, "익절")
    loss = trade("2026-07-02", "222222", 10_000, 8_000, 100, "손절", "10:00", "10:03")

    print("[1] 매매 1건 비용·손익 계산")
    # 매수 1,000,000×0.35% = 3,500 / 매도 1,200,000×0.55% = 6,600
    check("익절건 비용(원)", trade_cost(win), 10_100)
    check("익절건 순손익(원)", trade_pnl(win), 189_900)
    check("손절건 비용(원)", trade_cost(loss), 7_900)
    check("손절건 순손익(원)", trade_pnl(loss), -207_900)
    check("청산 안 된 건은 None", trade_pnl(trade("2026-07-03", "333333", 100, None, 10, "")), None)

    print("[2] 보유 시간")
    check("09:00→09:10", hold_minutes(win), 10)
    check("10:00→10:03", hold_minutes(loss), 3)
    check("시간 형식 깨지면 None", hold_minutes(trade("d", "t", 1, 1, 1, "", "-", "-")), None)

    print("[3] 집계 - 가격은 본전인데 수수료로 마이너스")
    s = summarize([win, loss], SEED)
    check("매매 건수", s["trades"], 2)
    check("승률 %", s["win_rate"], 50.0)
    check("가격 기준 손익률 %", s["gross_return"], 0.0)
    check("비용 손익률 %", s["cost_return"], -0.18)
    check("시드 대비 누적 손익률 %", s["total_return"], -0.18)
    check("평균 익절률 %", s["avg_win"], 18.99)
    check("평균 손절률 %", s["avg_loss"], -20.79)
    check("최고 매매 %", s["best"], 18.99)
    check("최저 매매 %", s["worst"], -20.79)

    print("[4] 자산곡선 · MDD")
    check("일별 포인트 수", len(s["equity"]), 2)
    check("1일차 지수", s["equity"][0]["close"], 101.899)
    check("2일차 지수", s["equity"][1]["close"], 99.82)
    check("MDD % (고점 101.899 대비)", s["mdd"], -2.04)
    check("기간", (s["period"]["from"], s["period"]["to"], s["period"]["days"]),
          ("2026-07-01", "2026-07-02", 2))
    check("마지막 날 매매 수", s["today"]["trades"], 1)
    check("마지막 날 손익률 %", s["today"]["return"], -2.08)

    print("[5] 같은 날 여러 건은 하루로 합산")
    same_day = summarize([win, trade("2026-07-01", "444444", 10_000, 12_000, 100, "익절")], SEED)
    check("일별 포인트 수", len(same_day["equity"]), 1)
    check("합산 지수", same_day["equity"][0]["close"], 103.798)

    print("[6] 청산 사유별 집계 (손실 큰 순)")
    check("사유 수", len(s["by_reason"]), 2)
    check("최악 사유", s["by_reason"][0]["reason"], "손절")
    check("최악 사유 기여도 %", s["by_reason"][0]["contribution"], -2.08)
    check("익절 사유 승률 %", s["by_reason"][1]["win_rate"], 100.0)

    print("[7] 최근 매매 목록 - 최신순, 금액 필드 없음")
    check("최신 건이 앞", s["recent"][0]["date"], "2026-07-02")
    check("개별 손익률", s["recent"][0]["pnl_pct"], -20.79)
    check("금액·수량 미포함", [k for k in s["recent"][0] if k in ("qty", "pnl", "entry_price")], [])

    print("[8] 빈 입력 방어")
    e = summarize([], SEED)
    check("건수 0", e["trades"], 0)
    check("자산곡선 빈 배열", e["equity"], [])
    check("기간 None", e["period"], None)

    print("[9] mode 필터 (임시 DB)")
    tmp = Path(tempfile.gettempdir()) / "paperbot_test.db"
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.execute("CREATE TABLE trades (date TEXT, ticker TEXT, name TEXT, entry_time TEXT,"
                " exit_time TEXT, entry_price INT, exit_price INT, qty INT,"
                " exit_reason TEXT, mode TEXT)")
    for t in (win, loss, trade("2026-07-02", "999999", 10_000, 12_000, 100, "익절", mode="unknown")):
        con.execute("INSERT INTO trades VALUES (:date,:ticker,:name,:entry_time,:exit_time,"
                    ":entry_price,:exit_price,:qty,:exit_reason,:mode)", t)
    con.commit()
    con.close()

    check("live-mock 만 집계", len(read_trades(tmp, "trades", "live-mock")), 2)
    check("mode 빈 값이면 전체", len(read_trades(tmp, "trades", None)), 3)
    tmp.unlink(missing_ok=True)

    print(f"\n결과: {PASS} 통과 / {FAIL} 실패")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
