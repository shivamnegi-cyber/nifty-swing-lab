# NIFTY Swing Lab — automated paper-trading system

A reliable, fully automated daily paper-trading system for NSE equities, built to
transition to Groww API live trading later **without a rewrite**. Free to run.

- Starts from **zero capital** on the first trading day and builds a real,
  auditable track record.
- Runs itself several times each **NSE trading day** (skips weekends/holidays).
- Combined strategy (EMA 20/50 trend + RSI + volume), **ATR stop-loss & target**,
  **1%-risk position sizing**, realistic Indian costs (brokerage, STT, exchange &
  SEBI charges, stamp duty, GST, slippage). Dividends & splits handled.
- **Telegram** morning + evening reports and instant failure alerts.
- Three isolated **modes** — backtest / paper / live — with live hard-disabled.
- A live web **dashboard** (GitHub Pages) with risk-adjusted metrics and
  benchmark comparison (Nifty 50 / 500 TRI proxies).

> New here? Read **DEPLOYMENT.md** — a beginner, click-by-click guide.

## How it runs

The schedule (`.github/workflows/cycle.yml`) calls `run_cycle.py` several times a
trading day. The script infers the phase from the IST clock:

| Phase | ~IST time | What it does |
| --- | --- | --- |
| open | 09:30 | applies the day's decisions, sends the **morning report** |
| monitor | 12:00, 14:00 | re-checks the market, alerts on any new trade |
| close | 15:50 | reconciles the day, sends the **evening report** |

Every run is independent and rebuilds the whole portfolio from history, so a
missed or crashed run self-heals. Bad/stale data → **safe state**: no signals,
just an alert.

## Files

| File | Purpose |
| --- | --- |
| `config.py` | Settings + the 3 modes + the live-trading safety gate |
| `market_calendar.py` | NSE trading-day / holiday awareness |
| `data.py` | Data fetch + validation + safe-state rule |
| `strategies.py` | The combined strategy (+ ATR) and others |
| `engine.py` | Portfolio sim: ATR stops, risk sizing, costs, metrics, benchmarks |
| `broker.py` | Execution seam: PaperBroker now, LiveBroker (disabled) later |
| `telegram_bot.py` | Morning / evening reports and alerts |
| `records.py` | Permanent auditable records (`records/`) |
| `run_cycle.py` | The entrypoint the schedule calls |
| `run_dashboard.py` | Builds the dashboard HTML |
| `dashboard_body.html` | Dashboard template |
| `.github/workflows/cycle.yml` | The daily automation |

## Run it yourself once (local, optional)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_cycle.py --phase close      # paper mode; no Telegram needed to test
```

Then open `dashboard.html`.

---
*Educational tool, not investment advice. Paper trading only — no real orders are
placed by this build.*
