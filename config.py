"""
Central configuration and the three execution modes.

Modes (set with the MODE environment variable):
  - backtest : historical only, no reporting side-effects
  - paper    : simulated trading on real data (the default, and what you run now)
  - live     : REAL orders via the Groww API — HARD-DISABLED until you explicitly
               turn it on with credentials (see is_live_allowed()).

Nothing here ever places a real order. Live mode cannot even be *reached*
without (a) MODE=live, (b) a confirmation phrase, and (c) Groww credentials.
Everything is read from environment variables, so no secret is ever committed.
"""

import os

# ---- mode ----
MODE = os.getenv("MODE", "paper").lower()            # backtest | paper | live

# ---- strategy / portfolio (change via env if you want) ----
STRATEGY = os.getenv("STRATEGY", "trend_rsi_vol")
UNIVERSE = os.getenv("UNIVERSE", "nifty100")
CAPITAL = float(os.getenv("CAPITAL", "20000"))
TOP_K = int(os.getenv("TOP_K", "5"))
RISK_PCT = float(os.getenv("RISK_PCT", "0.01"))      # risk 1% of equity per trade
LIVE_START = os.getenv("LIVE_START", "2026-11-13")   # first trading day — starts from zero here
BACKTEST_YEARS = int(os.getenv("BACKTEST_YEARS", "3"))

# ---- Telegram (from BotFather; set as secrets, never hard-code) ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---- storage ----
RECORDS_DIR = os.getenv("RECORDS_DIR", "records")
LOG_DIR = os.getenv("LOG_DIR", "logs")

# ---- live-trading safety gate ----
# Live orders require ALL of these, so a mode mix-up can never fire a real trade.
LIVE_CONFIRM_PHRASE = "I_UNDERSTAND_LIVE_TRADING_RISK"
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.03"))     # halt at -3% day
MAX_CAPITAL_DEPLOYED = float(os.getenv("MAX_CAPITAL_DEPLOYED", "1.0"))


def is_live_allowed():
    """True only when live trading is deliberately and fully configured."""
    return (
        MODE == "live"
        and os.getenv("GROWW_LIVE_CONFIRM", "") == LIVE_CONFIRM_PHRASE
        and bool(os.getenv("GROWW_API_KEY", ""))
        and bool(os.getenv("GROWW_API_SECRET", ""))
    )


def telegram_configured():
    return bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


def summary():
    return {
        "mode": MODE, "strategy": STRATEGY, "universe": UNIVERSE,
        "capital": CAPITAL, "top_k": TOP_K, "risk_pct": RISK_PCT,
        "live_start": LIVE_START, "live_allowed": is_live_allowed(),
        "telegram": telegram_configured(),
    }
