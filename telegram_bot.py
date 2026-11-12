"""
Telegram reporting — the primary monitoring channel.

Sends the morning status report, the evening summary, and immediate alerts on
critical failure. Every number comes from real recorded results; nothing is
fabricated. If Telegram isn't configured, it logs a warning and returns False
(it never crashes the run).

Setup: talk to @BotFather to create a bot and get TELEGRAM_BOT_TOKEN, then get
your TELEGRAM_CHAT_ID (see DEPLOYMENT.md). Set both as environment variables /
GitHub secrets.
"""

import logging

import config

log = logging.getLogger("telegram")
API = "https://api.telegram.org/bot{token}/sendMessage"


def send(text):
    if not config.telegram_configured():
        log.warning("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing) — skipping send.")
        return False
    try:
        import requests
        r = requests.post(
            API.format(token=config.TELEGRAM_BOT_TOKEN),
            data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=20,
        )
        if not r.ok:
            log.error("Telegram send failed: %s %s", r.status_code, r.text[:200])
        return r.ok
    except Exception as e:
        log.error("Telegram send error: %s", e)
        return False


def alert(message):
    return send(f"🚨 <b>ALERT</b>\n{message}")


def _rupees(x):
    return f"₹{x:,.0f}"


def morning_text(ctx):
    pos = ctx.get("open_positions", [])
    pos_lines = "\n".join(f"  • {h['ticker']}: {h['shares']} sh @ ₹{h['entry']}" for h in pos) or "  • none"
    warn = ctx.get("warnings") or []
    warn_lines = "\n".join(f"  ⚠️ {w}" for w in warn) or "  none"
    return (
        f"🌅 <b>Morning report — {ctx['date']}</b>\n"
        f"Session: <b>{ctx['session']}</b>  |  Mode: <b>{ctx['mode']}</b>\n"
        f"System: {ctx['system']}  |  Data: {ctx['data']}\n"
        f"Stocks monitored: {ctx['n_stocks']}\n"
        f"Paper capital: {_rupees(ctx['capital'])}  |  Value: {_rupees(ctx['value'])}\n"
        f"Yesterday P&L: {ctx['yday_pnl']}\n"
        f"Open positions ({len(pos)}):\n{pos_lines}\n"
        f"Strategy: {ctx['strategy']}  |  Risk/trade: {ctx['risk_pct']}%  "
        f"| Stop {ctx['atr_stop']}×ATR / Target {ctx['atr_target']}×ATR\n"
        f"Warnings:\n{warn_lines}"
    )


def evening_text(ctx):
    pos = ctx.get("open_positions", [])
    pos_lines = "\n".join(
        f"  • {h['ticker']}: {h['shares']} sh, unrl {('+' if h['unreal_abs']>=0 else '−')}₹{abs(h['unreal_abs']):,.0f}"
        for h in pos) or "  • none"
    bench_lines = "\n".join(f"  • {b['name']}: {b['cagr']}% CAGR, Sharpe {b['sharpe']}"
                            for b in ctx.get("benchmarks", [])) or "  • n/a"
    return (
        f"🌙 <b>Evening report — {ctx['date']}</b>\n"
        f"Mode: <b>{ctx['mode']}</b>  |  System: {ctx['system']}\n"
        f"— Today —\n"
        f"Trades: {ctx['trades_today']} (entries {ctx['entries_today']}, exits {ctx['exits_today']})\n"
        f"Day P&L: <b>{ctx['day_pnl']}</b>\n"
        f"— Portfolio (since {ctx['start']}) —\n"
        f"Value: <b>{_rupees(ctx['value'])}</b>  ({ctx['total_pnl_pct']})\n"
        f"Realised P&L: {ctx['realised']}  |  Unrealised: {ctx['unrealised']}\n"
        f"Est. costs to date: {ctx['costs']}\n"
        f"Closed trades: {ctx['n_closed']}  |  Win rate: {ctx['win_rate']}%  "
        f"| Max drawdown: {ctx['maxdd']}%\n"
        f"Missed/rejected signals today: {ctx.get('missed', 0)}\n"
        f"Open positions ({len(pos)}):\n{pos_lines}\n"
        f"— Benchmarks ({ctx.get('bt_years','3')}y backtest) —\n{bench_lines}\n"
        f"Errors: {ctx.get('errors','none')}"
    )
