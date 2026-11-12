"""
Builds the dashboard HTML from a results dict.

  render(results)  -> writes dashboard.html (+ dashboard_artifact.html) from an
                      already-computed results dict (used by run_cycle).
  build(args)      -> computes results via run_all, then renders (standalone use).
"""

import argparse
import json

from engine import run_all

TEMPLATE = "dashboard_body.html"


def render(results):
    with open(TEMPLATE) as fh:
        body = fh.read().replace("/*__DATA__*/{}", json.dumps(results))
    standalone = ('<!doctype html><meta charset="utf-8">'
                  '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                  + body)
    with open("dashboard.html", "w") as fh:
        fh.write(standalone)
    with open("dashboard_artifact.html", "w") as fh:
        fh.write(body)
    with open("results.json", "w") as fh:
        json.dump(results, fh, indent=2)


def build(args):
    results = run_all(
        paper_strategy=args.strategy, universe=args.universe, period=args.period,
        live_start=args.live_start, backtest_years=args.backtest_years,
        top_k=args.top, capital=args.capital, risk_pct=args.risk,
    )
    render(results)
    b, p = results["backtest"], results["paper"]
    print(f"Rebuilt — {results['universe_loaded']} stocks | backtest Sharpe {b['perf']['sharpe']} "
          f"| live value Rs.{p['value']:.0f} ({p['pnl_pct']:+.2f}%), {p['open_positions']} open")


if __name__ == "__main__":
    import config
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default=config.STRATEGY)
    ap.add_argument("--universe", default=config.UNIVERSE)
    ap.add_argument("--live-start", default=config.LIVE_START)
    ap.add_argument("--backtest-years", type=int, default=config.BACKTEST_YEARS)
    ap.add_argument("--top", type=int, default=config.TOP_K)
    ap.add_argument("--capital", type=float, default=config.CAPITAL)
    ap.add_argument("--risk", type=float, default=config.RISK_PCT)
    ap.add_argument("--period", default="5y")
    build(ap.parse_args())
