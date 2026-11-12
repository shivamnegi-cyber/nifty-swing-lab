# Project audit & implementation checklist

**Important finding:** your live GitHub repo contains only the **first
deployment** (the early weekly-rebalance version). None of the later work was
pushed. This project is a **complete replacement** — deploy it over the old repo
(same repo, upload all files) and everything below is handled in one go.

| Component | Was in repo (1st deploy) | Change made | Final status |
| --- | --- | --- | --- |
| Market data integration | Basic fetch, no validation | Added `data.py`: validation, freshness, OHLC sanity, safe-state | ✅ Done |
| Strategy execution | ema_9_21 only | Combined EMA+RSI+volume (`trend_rsi_vol`) | ✅ Done |
| Signal generation | Weekly rebalance, no confirmation | Daily signals, 3-factor confirmation, ATR | ✅ Done |
| Paper trading engine | Mark-to-market, flat costs | ATR stop/target, 1% risk sizing, full Indian cost model | ✅ Done |
| Portfolio management | Equal-weight rotation | Position tracking, cash, whole shares, caps | ✅ Done |
| Risk management | None | Per-trade risk %, ATR stops, max position cap, daily-loss setting | ✅ Done |
| Telegram integration | ❌ none | `telegram_bot.py`: morning, evening, alerts | ⚠️ Needs your token |
| Morning automation | ❌ none | `open` phase in `run_cycle.py` + schedule | ✅ Done (token to send) |
| Market-closing automation | ❌ none | `close` phase: reconcile + evening report | ✅ Done (token to send) |
| Daily reporting | Dashboard only | Records + Telegram reports from real data | ✅ Done |
| Logging & monitoring | ❌ none | Structured logging, `records/`, `logs/runs.log`, health checks | ✅ Done |
| NSE calendar / scheduling | Single daily cron | `market_calendar.py` + multi-run/day, holiday-aware | ✅ Done |
| Groww API integration | ❌ none | `broker.py` seam; LiveBroker stub, hard-disabled | 🔒 Future (needs Groww) |
| Live-trading readiness | ❌ none | 3 isolated modes + safety gate; live blocked until configured | ✅ Isolated & safe |
| Recovery / restart | ❌ none | Stateless reconstruction → self-healing; safe-state on bad data | ✅ Done |
| Deployment | GitHub Pages (daily) | GitHub Actions multi-run + Pages + committed audit trail | ✅ Done |

## Known failure points handled
- Data download fails / too few stocks / stale → **safe state**, alert, no trades.
- Telegram down / unconfigured → logs and continues (never crashes the run).
- Missed or crashed run → next run re-derives correct state (no corruption).
- Non-trading day → detected and skipped.
- Mode mix-up → live can't fire without explicit phrase + Groww creds.

## Reliability & realism items — now done
1. Rejected/missed-signal logging → `records/rejected_signals.csv`.
2. API retry with backoff before safe-state.
3. Partial-fill + gap-rejection modelling (deterministic; rarely binds at ₹20k).
4. Entries fill at the next bar's **open** (+ slippage), with same-day stop/target.
5. systemd timer + service in `deploy/` for the optional VPS path.

## Not done on purpose
- No new strategies added (you asked to freeze features).
- No continuous intraday tick service (not needed for a daily strategy; would
  need paid data + a VPS). Multiple scheduled runs/day cover monitoring.
- Random order rejections are avoided deliberately: rejections are deterministic
  (slot/cash/gap), so the portfolio stays reproducible and auditable.
