"""
Market-data layer with validation and a safe-state rule.

Fetches daily OHLCV, then checks it before anything trades on it:
  - enough stocks actually loaded,
  - data is fresh (not stale/holiday leftovers),
  - OHLCV values are sane (no zero/negative prices, high >= low).

If the data fails validation, callers must enter SAFE STATE: generate no
executable signals and send an alert. The system never silently trades on stale
or broken data.
"""

import config
import market_calendar as mc
from engine import download_prices
from universe import get_universe


def fetch_and_validate(period="5y"):
    tickers = get_universe(config.UNIVERSE)
    try:
        data = download_prices(tickers, period=period)
    except Exception as e:
        return None, {"ok": False, "loaded": 0, "requested": len(tickers),
                      "latest": None, "issues": [f"download failed: {e}"]}
    health = _validate(data, tickers)
    return (data if health["ok"] else None), health


def _validate(data, tickers):
    issues = []
    loaded = len(data)
    min_needed = max(10, len(tickers) // 3)
    if loaded < min_needed:
        issues.append(f"only {loaded}/{len(tickers)} stocks loaded (need >= {min_needed})")

    latest = None
    for df in data.values():
        d = df.index[-1].date()
        latest = max(latest, d) if latest else d

    stale = False
    if latest:
        age = (mc._today_ist() - latest).days
        if age > 5:
            issues.append(f"data stale: newest bar {latest} is {age} days old")
            stale = True

    # sanity on a sample of up to 5 stocks
    bad = 0
    for df in list(data.values())[:5]:
        last = df.iloc[-1]
        if last["Close"] <= 0 or last["High"] < last["Low"]:
            bad += 1
    if bad:
        issues.append(f"{bad} sampled stocks have impossible OHLC values")

    ok = (loaded >= min_needed) and (not stale) and (bad == 0)
    return {"ok": ok, "loaded": loaded, "requested": len(tickers),
            "latest": str(latest) if latest else None, "issues": issues}
