"""
The one entrypoint the schedule calls several times each trading day.

Phases (passed with --phase, or inferred from the IST clock):
  open    (~market open)  -> place the day's decisions, send the MORNING report
  monitor (mid-session)   -> re-check the market, alert on any new trade
  close   (after close)   -> reconcile the day, send the EVENING report

Every run is independent and self-healing: it rebuilds the whole portfolio from
history, so a missed or crashed run simply corrects itself next time. It never
assumes a previous run succeeded — it re-derives the truth and verifies data
before acting. On bad/stale data it enters SAFE STATE: no signals, just an alert.
"""

import argparse
import datetime as dt
import logging
import sys

import config
import data as datafeed
import market_calendar as mc
import records
import run_dashboard
import telegram_bot as tg
from engine import run_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("cycle")


def infer_phase():
    hour = (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).hour
    if hour < 11:
        return "open"
    if hour >= 15:
        return "close"
    return "monitor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["open", "monitor", "close"], default=None)
    args = ap.parse_args()
    phase = args.phase or infer_phase()
    today = mc._today_ist()
    log.info("cycle start — phase=%s mode=%s date=%s", phase, config.MODE, today)

    # 1) trading-day gate
    if not mc.is_trading_day(today):
        why = mc.reason_not_trading(today)
        log.info("not a trading day (%s) — nothing to do", why)
        records.log_run(f"{phase}", True, f"skipped: {why}")
        return 0

    # 2) data + validation (safe state on failure)
    feed, health = datafeed.fetch_and_validate(period="5y")
    if feed is None:
        msg = "Data unavailable/invalid — entering SAFE STATE, no signals. Issues: " + "; ".join(health["issues"])
        log.error(msg)
        tg.alert(msg)
        records.log_run(phase, False, msg)
        return 0
    warnings = health["issues"]

    # 3) compute the portfolio (backtest + live) and persist
    results = run_all(
        paper_strategy=config.STRATEGY, universe=config.UNIVERSE,
        live_start=config.LIVE_START, backtest_years=config.BACKTEST_YEARS,
        top_k=config.TOP_K, capital=config.CAPITAL, risk_pct=config.RISK_PCT,
    )
    p = results["paper"]
    prev = records.read_state()
    records.write_live_records(p)
    run_dashboard.render(results)

    # 4) change detection vs the last run
    new_closed = p["n_closed"] - (prev["n_closed"] if prev else 0)
    asof = p["asof"]
    exits_today = [c for c in p["closed_trades"] if c["exit_date"] == asof]
    entries_today = [h for h in p["holdings"] if h.get("entry_date") == asof] + \
                    [c for c in p["closed_trades"] if c["entry_date"] == asof]
    missed_today = [r for r in p.get("rejected", []) if r["date"] == asof]
    day_pnl = p["daily"][-1]["pnl"] if p["daily"] and p["daily"][-1]["date"] == asof else 0.0

    system = "OK" + (f" ({len(warnings)} warning)" if warnings else "")
    data_str = f"OK — {health['loaded']} stocks, latest {health['latest']}"

    # 5) report by phase
    if phase == "open":
        ctx = {"date": str(today), "session": "Market open", "mode": config.MODE,
               "system": system, "data": data_str, "n_stocks": health["loaded"],
               "capital": config.CAPITAL, "value": p["value"],
               "yday_pnl": f"{'+' if day_pnl>=0 else '−'}₹{abs(day_pnl):,.0f}",
               "open_positions": p["holdings"], "strategy": config.STRATEGY,
               "risk_pct": p["risk_pct"], "atr_stop": p["atr_stop"], "atr_target": p["atr_target"],
               "warnings": warnings}
        tg.send(tg.morning_text(ctx))
    elif phase == "close":
        realised = sum(c["pnl_abs"] for c in exits_today)
        unreal = sum(h["unreal_abs"] for h in p["holdings"])
        ctx = {"date": str(today), "mode": config.MODE, "system": system,
               "trades_today": len(entries_today) + len(exits_today),
               "entries_today": len(entries_today), "exits_today": len(exits_today),
               "day_pnl": f"{'+' if day_pnl>=0 else '−'}₹{abs(day_pnl):,.0f}",
               "start": p["start"], "value": p["value"],
               "total_pnl_pct": f"{p['pnl_pct']:+.2f}%",
               "realised": f"{'+' if realised>=0 else '−'}₹{abs(realised):,.0f}",
               "unrealised": f"{'+' if unreal>=0 else '−'}₹{abs(unreal):,.0f}",
               "costs": f"₹{p['total_costs']:,.0f}", "n_closed": p["n_closed"],
               "win_rate": p["win_rate"], "maxdd": p["perf"]["maxdd"],
               "open_positions": p["holdings"], "benchmarks": results["benchmarks"],
               "bt_years": config.BACKTEST_YEARS, "errors": "none",
               "missed": len(missed_today)}
        tg.send(tg.evening_text(ctx))
    else:  # monitor
        if new_closed > 0 or entries_today:
            tg.alert(f"Intraday update {asof}: {len(entries_today)} new entr(y/ies), "
                     f"{len(exits_today)} exit(s) today. Value ₹{p['value']:,.0f} ({p['pnl_pct']:+.2f}%).")

    records.log_run(phase, True, f"value={p['value']} open={p['open_positions']} closed={p['n_closed']}")
    log.info("cycle done — phase=%s value=%.0f open=%d", phase, p["value"], p["open_positions"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
