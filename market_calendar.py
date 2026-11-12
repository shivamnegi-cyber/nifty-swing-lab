"""
NSE trading-calendar awareness — so the system never runs on a weekend or a
market holiday, and never treats a holiday's stale data as fresh.

It prefers the `exchange_calendars` library (an official, maintained NSE
calendar). If that isn't installed, it falls back to weekend + a hardcoded NSE
holiday list that you update once a year.
"""

import datetime as dt

# Fallback NSE holiday list (update yearly). 2026 trading holidays (indicative;
# verify against the official NSE circular each January).
NSE_HOLIDAYS_FALLBACK = {
    "2026-01-26", "2026-02-16", "2026-03-04", "2026-03-20", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-06-17", "2026-08-15",
    "2026-09-14", "2026-10-02", "2026-10-21", "2026-11-09", "2026-12-25",
}

_cal = None
try:
    import exchange_calendars as xcals
    for code in ("XNSE", "XBOM"):
        try:
            _cal = xcals.get_calendar(code)
            break
        except Exception:
            continue
except Exception:
    _cal = None


def is_trading_day(date=None):
    """True if `date` (default today, IST) is an NSE trading day."""
    date = date or _today_ist()
    if _cal is not None:
        try:
            return _cal.is_session(date.strftime("%Y-%m-%d"))
        except Exception:
            pass
    if date.weekday() >= 5:               # Sat/Sun
        return False
    return date.strftime("%Y-%m-%d") not in NSE_HOLIDAYS_FALLBACK


def _today_ist():
    # IST = UTC + 5:30
    return (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).date()


def reason_not_trading(date=None):
    date = date or _today_ist()
    if date.weekday() >= 5:
        return "weekend"
    if not is_trading_day(date):
        return "NSE holiday"
    return ""
