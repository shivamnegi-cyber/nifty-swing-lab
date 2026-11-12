# Verification report

Tests actually executed in a clean environment on 2026-11-12. Honest status:
**done** = ran and passed here; **needs creds** = code verified but needs your
keys to exercise end-to-end; **on deploy** = happens on GitHub/live session.

| Check | Status | Evidence |
| --- | --- | --- |
| Install dependencies | ✅ done | `pip install -r requirements.txt` succeeded |
| All modules import | ✅ done | `import config, data, broker, records, telegram_bot, engine, …` OK |
| NSE calendar correct | ✅ done | Thu 2026-11-12 → trading; Sat 2026-11-14 → not trading |
| Mode isolation / live gate | ✅ done | `is_live_allowed()` = False; `get_broker()` = PaperBroker |
| Market-data integration + validation | ✅ done | 97 stocks loaded & validated; safe-state path exercised on failure |
| Strategy execution | ✅ done | combined strategy ran across 97 stocks |
| Paper order execution | ✅ done | portfolio built 5 positions with ATR stop/target & risk sizing |
| Records / persistence | ✅ done | `records/state.json, trades.csv, daily.csv, holdings.csv` written |
| Dashboard build | ✅ done | `dashboard.html` generated (≈150 KB) |
| Full trading cycle (close phase) | ✅ done | `run_cycle.py --phase close` ran clean, wrote records, rendered |
| Telegram reports | ⚠️ needs creds | module + morning/evening formatters verified; sending needs your bot token |
| Scheduler firing | 🕒 on deploy | workflow YAML valid; real schedule runs once on GitHub |
| Restart / recovery | ✅ by design | every run re-derives state from history — a missed/crashed run self-heals |
| Market-close reporting | ✅ done | close-phase path + evening report built from real data |
| Groww live trading | ⛔ blocked by design | requires Groww subscription + credentials; cannot and must not run now |

## Reliability & realism upgrades (added and tested)

| Item | Status | Evidence |
| --- | --- | --- |
| Rejected / missed-signal logging | ✅ done | `records/rejected_signals.csv` written (date, ticker, reason); reasons: no_open_slot, insufficient_cash, gap_too_large |
| API retry with backoff | ✅ done | `_yf_download_retry` (3 tries, 2/4/6s backoff) before safe-state |
| Partial-fill / rejected-order modelling | ✅ done | volume-cap partial fills + gap-too-large rejection (deterministic); rarely binds at ₹20k capital — honest |
| Entry fill realism | ✅ done | entries now fill at the **next bar's open** (+ slippage in cost model), with a same-day stop/target check |
| systemd timer + service (VPS) | ✅ provided | `deploy/nifty-swing.timer` + `deploy/nifty-swing.service` |

## What still needs *you* (external resources)

1. **Telegram bot token + chat id** — free, 5 minutes (DEPLOYMENT.md Step 2).
   Until set, the system runs fine but sends no messages (it logs and skips).
2. **GitHub Pages + Secrets** — free, one-time (DEPLOYMENT.md Steps 3–4).
3. **Groww API** (only for the future live phase) — a paid subscription plus
   API key/secret. Not needed for paper trading. Live stays disabled until you
   wire `broker.LiveBroker` and set the three Groww env vars.

## Honest limitations (free data)

- Market data is Yahoo Finance (free): occasional rate-limits/gaps; the validator
  tolerates small gaps and enters safe-state on serious ones.
- "TRI" benchmarks are dividend-adjusted ETF proxies, not official index TRI.
- Intraday runs use end-of-day/forming-bar data; true tick-level intraday needs
  the Groww API (live phase).
- This is paper trading. Past/backtest results do not predict future returns.
