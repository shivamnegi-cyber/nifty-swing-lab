"""
The engine — built to judge a strategy the way a quant would: risk-adjusted,
after realistic costs, against proper benchmarks.

Core = portfolio_sim(): the combined strategy (EMA trend + RSI + volume) run as a
real portfolio with
  - ATR-based stop-loss and target (stops fit each stock's own volatility),
  - risk-based position sizing (each trade risks a fixed % of equity),
  - a realistic Indian cost model (brokerage, STT, exchange + SEBI charges,
    stamp duty, GST, slippage) on every order,
  - dividends & splits already handled by Yahoo's adjusted prices.

run_all() runs it twice: a multi-year BACKTEST (for risk-adjusted metrics and
benchmark comparison) and a LIVE paper run from a chosen start date, and pulls
benchmark series (Nifty 50 / Nifty 500 TRI proxies) to compare after costs.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from strategies import STRATEGIES, apply_strategy, atr
from universe import get_universe

MOM_LOOKBACK = 20
CAPITAL = 20_000.0
RISK_PCT = 0.01        # risk 1% of equity per trade (the stop distance)
ATR_STOP = 2.0         # stop = entry - 2*ATR
ATR_TARGET = 4.0       # target = entry + 4*ATR  (2:1 reward-to-risk)
MAX_POS_PCT = 0.35     # never put more than 35% of equity in one name
TOP_K = 5
SLIPPAGE = 0.0005      # 5 bps per side (inside the cost model)
PARTICIPATION_CAP = 0.01   # can't buy more than 1% of a day's volume (partial fills)
MAX_ENTRY_GAP = 0.06       # reject an entry if the open gaps >6% above prior close
MAX_RETRIES = 3            # data-download retries before giving up

# Nifty 50 / Nifty 500 TRI proxies: dividend-adjusted ETFs (free TRI equivalent)
BENCH_N50 = "NIFTYBEES.NS"
BENCH_N500_CANDIDATES = ["MON500.NS", "^CRSLDX", "NIFTY500.NS"]


# ---------- realistic Indian delivery cost ----------

def order_cost(turnover, side, slippage=SLIPPAGE):
    """Total cost of one order in rupees (Indian delivery equity, approx)."""
    brokerage = min(20.0, 0.001 * turnover)          # Groww-style: Rs20 or 0.1%, lower
    stt = 0.001 * turnover                            # 0.1% both sides (delivery)
    exch = 0.0000297 * turnover                       # NSE transaction charge
    sebi = 0.000001 * turnover
    stamp = 0.00015 * turnover if side == "buy" else 0.0
    gst = 0.18 * (brokerage + exch)
    slip = slippage * turnover
    return brokerage + stt + exch + sebi + stamp + gst + slip


# ---------- performance metrics ----------

def perf_metrics(values, capital):
    s = pd.Series([v for v in values if v is not None], dtype=float)
    rets = s.pct_change().dropna()
    n = len(s)
    years = max(n / 252, 1e-6)
    end = s.iloc[-1]
    cagr = (end / capital) ** (1 / years) - 1 if end > 0 else -1
    ann = rets.mean() * 252
    vol = rets.std() * np.sqrt(252)
    sharpe = ann / vol if vol > 0 else 0.0
    downside = rets[rets < 0].std() * np.sqrt(252)
    sortino = ann / downside if downside > 0 else 0.0
    maxdd = float((s / s.cummax() - 1).min()) if n else 0.0
    calmar = cagr / abs(maxdd) if maxdd < 0 else 0.0
    return {"cagr": round(cagr * 100, 1), "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2), "maxdd": round(maxdd * 100, 1),
            "calmar": round(calmar, 2), "vol": round(vol * 100, 1)}


def trade_metrics(closed):
    if not closed:
        return {"n": 0, "win_rate": 0, "profit_factor": 0, "expectancy": 0,
                "avg_win": 0, "avg_loss": 0}
    pnls = [c["pnl_abs"] for c in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "n": len(closed),
        "win_rate": round(100 * len(wins) / len(pnls), 0),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else round(gross_win, 2),
        "expectancy": round(np.mean(pnls), 0),
        "avg_win": round(np.mean(wins), 0) if wins else 0,
        "avg_loss": round(np.mean(losses), 0) if losses else 0,
    }


# ---------- data ----------

def _yf_download_retry(tickers, period):
    """Download with sensible retries + backoff before giving up (item 2)."""
    import time
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = yf.download(tickers, period=period, auto_adjust=True,
                              progress=False, group_by="ticker", threads=True)
            if raw is not None and len(raw) > 0:
                return raw
        except Exception as e:
            last_err = e
        time.sleep(2 * (attempt + 1))        # 2s, 4s, 6s backoff
    if last_err:
        raise last_err
    return raw


def download_prices(tickers, period="5y"):
    raw = _yf_download_retry(tickers, period)
    data = {}
    for t in tickers:
        try:
            sub = raw[t][["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(sub) > 250:
                data[t] = sub
        except Exception:
            pass
    return data


# ---------- the portfolio simulation ----------

def portfolio_sim(strategy, data, start, capital=CAPITAL, top_k=TOP_K,
                  risk_pct=RISK_PCT, atr_stop=ATR_STOP, atr_target=ATR_TARGET):
    closes = pd.DataFrame({t: df["Close"] for t, df in data.items()}).sort_index()
    opens = pd.DataFrame({t: df["Open"] for t, df in data.items()}).reindex(closes.index)
    highs = pd.DataFrame({t: df["High"] for t, df in data.items()}).reindex(closes.index)
    lows = pd.DataFrame({t: df["Low"] for t, df in data.items()}).reindex(closes.index)
    vols = pd.DataFrame({t: df["Volume"] for t, df in data.items()}).reindex(closes.index)
    mom = closes.pct_change(MOM_LOOKBACK)

    sig = {t: apply_strategy(strategy, data[t]) for t in data}
    trend = pd.DataFrame({t: sig[t].get("trend", sig[t]["signal"]) for t in data}).reindex(closes.index)
    entry_ok = pd.DataFrame({t: sig[t].get("entry_ok", sig[t]["signal"]) for t in data}).reindex(closes.index)
    atr_df = pd.DataFrame({t: atr(data[t]) for t in data}).reindex(closes.index)

    all_dates = closes.index
    dates = all_dates[all_dates >= pd.Timestamp(start)]
    if len(dates) == 0:
        dates = all_dates[-1:]

    cash = capital
    positions = {}
    closed, daily, curve_dates, curve_val, rejected = [], [], [], [], []
    prev_value = capital
    total_cost = 0.0

    def _close_position(t, ex, reason, dt, entered_same_day=False):
        nonlocal cash, total_cost
        pos = positions[t]
        sell_cost = order_cost(pos["shares"] * ex, "sell")
        total_cost += sell_cost
        cash += pos["shares"] * ex - sell_cost
        pnl = pos["shares"] * (ex - pos["entry_price"]) - pos["buy_cost"] - sell_cost
        closed.append({
            "ticker": t.replace(".NS", ""), "shares": pos["shares"],
            "entry_date": str(pos["entry_date"].date()), "entry_price": round(pos["entry_price"], 1),
            "stop_price": round(pos["stop_price"], 1), "target_price": round(pos["target_price"], 1),
            "exit_date": str(dt.date()), "exit_price": round(float(ex), 1), "reason": reason,
            "pnl_abs": round(pnl, 0), "pnl_pct": round(pnl / (pos["shares"] * pos["entry_price"]) * 100, 2),
            "days": (dt - pos["entry_date"]).days, "partial": pos.get("partial", False),
        })
        del positions[t]

    for dt in dates:
        price, high, low = closes.loc[dt], highs.loc[dt], lows.loc[dt]
        i = all_dates.get_loc(dt)
        prev = all_dates[i - 1] if i > 0 else dt
        tr_prev, eok_prev, m_prev, atr_prev = trend.loc[prev], entry_ok.loc[prev], mom.loc[prev], atr_df.loc[prev]
        trades_today = 0

        # 1) exits for positions held from earlier days (stop -> target -> trend)
        for t in list(positions):
            pos = positions[t]
            pl, ph, pc = low.get(t), high.get(t), price.get(t)
            ex, reason = None, None
            if pd.notna(pl) and pl <= pos["stop_price"]:
                ex, reason = pos["stop_price"], "STOP"
            elif pd.notna(ph) and ph >= pos["target_price"]:
                ex, reason = pos["target_price"], "TARGET"
            elif tr_prev.get(t, 1) == 0 and pd.notna(pc):
                ex, reason = float(pc), "TREND"
            if ex is not None:
                _close_position(t, ex, reason, dt)
                trades_today += 1

        # 2) entries at TODAY'S OPEN from yesterday's confirmed signal (item 4)
        value_now = cash + sum(positions[t]["shares"] * price[t] for t in positions if pd.notna(price.get(t)))
        open_slots = top_k - len(positions)
        eligible = [t for t in closes.columns
                    if eok_prev.get(t, 0) == 1 and t not in positions
                    and pd.notna(m_prev.get(t)) and pd.notna(opens.loc[dt].get(t)) and atr_prev.get(t, 0) > 0]
        eligible = sorted(eligible, key=lambda t: m_prev[t], reverse=True)
        cand, overflow = eligible[:max(0, open_slots)], eligible[max(0, open_slots):]
        for t in overflow:                                    # wanted, but no slot free (item 1)
            rejected.append({"date": str(dt.date()), "ticker": t.replace(".NS", ""), "reason": "no_open_slot"})
        for t in cand:
            o = float(opens.loc[dt][t]); a = float(atr_prev[t]); pcp = float(closes.loc[prev].get(t, o))
            stop_dist = atr_stop * a
            if stop_dist <= 0:
                continue
            if pcp > 0 and (o / pcp - 1) > MAX_ENTRY_GAP:      # gapped up too far — don't chase (item 3)
                rejected.append({"date": str(dt.date()), "ticker": t.replace(".NS", ""), "reason": "gap_too_large"})
                continue
            desired = min(int((risk_pct * value_now) // stop_dist),
                          int((MAX_POS_PCT * value_now) // o),
                          int(cash // (o * 1.003)))
            v = vols.loc[dt].get(t)
            qty_vol = int(PARTICIPATION_CAP * float(v)) if pd.notna(v) and v > 0 else desired
            qty = max(0, min(desired, qty_vol))               # volume-capped partial fill (item 3)
            if qty <= 0:
                reason = "insufficient_cash" if int(cash // (o * 1.003)) <= 0 else "size_zero"
                rejected.append({"date": str(dt.date()), "ticker": t.replace(".NS", ""), "reason": reason})
                continue
            partial = qty < desired
            bc = order_cost(qty * o, "buy")
            total_cost += bc
            cash -= qty * o + bc
            positions[t] = {"shares": qty, "entry_price": o, "entry_date": dt, "buy_cost": bc,
                            "stop_price": o - stop_dist, "target_price": o + atr_target * a, "partial": partial}
            trades_today += 1
            # same-day stop/target: a move after entry can exit the same day
            pl2, ph2 = low.get(t), high.get(t)
            if pd.notna(pl2) and pl2 <= positions[t]["stop_price"]:
                _close_position(t, positions[t]["stop_price"], "STOP", dt); trades_today += 1
            elif pd.notna(ph2) and ph2 >= positions[t]["target_price"]:
                _close_position(t, positions[t]["target_price"], "TARGET", dt); trades_today += 1

        value = cash + sum(positions[t]["shares"] * price[t] for t in positions if pd.notna(price.get(t)))
        pnl = value - prev_value
        daily.append({"date": str(dt.date()), "value": round(value, 0), "pnl": round(pnl, 1),
                      "pnl_pct": round((pnl / prev_value * 100) if prev_value else 0, 2), "trades": trades_today})
        prev_value = value
        curve_dates.append(str(dt.date())); curve_val.append(round(value, 1))

    last_price = closes.loc[dates[-1]]
    holdings = []
    for t, pos in positions.items():
        cur = float(last_price[t])
        unreal = pos["shares"] * (cur - pos["entry_price"]) - pos["buy_cost"]
        holdings.append({"ticker": t.replace(".NS", ""), "shares": pos["shares"],
                         "entry_date": str(pos["entry_date"].date()),
                         "entry": round(pos["entry_price"], 1), "stop": round(pos["stop_price"], 1),
                         "target": round(pos["target_price"], 1), "price": round(cur, 1),
                         "value": round(pos["shares"] * cur, 0), "unreal_abs": round(unreal, 0),
                         "unreal_pct": round(unreal / (pos["shares"] * pos["entry_price"]) * 100, 2),
                         "partial": pos.get("partial", False)})
    holdings.sort(key=lambda h: h["value"], reverse=True)

    perf = perf_metrics(curve_val, capital)
    tstats = trade_metrics(closed)
    pnls = [d["pnl"] for d in daily]
    value_now = curve_val[-1]
    return {
        "strategy": strategy, "top_k": top_k, "capital": capital,
        "risk_pct": round(risk_pct * 100, 1), "atr_stop": atr_stop, "atr_target": atr_target,
        "start": str(dates[0].date()), "asof": str(dates[-1].date()), "days": len(dates),
        "value": round(value_now, 0), "cash": round(cash, 0),
        "pnl_abs": round(value_now - capital, 0), "pnl_pct": round((value_now / capital - 1) * 100, 2),
        "total_costs": round(total_cost, 0),
        "rejected": rejected[-300:], "n_rejected": len(rejected),
        "perf": perf, "trades_stats": tstats,
        "win_days": sum(1 for x in pnls if x > 0), "total_days": len(daily),
        "best_day": round(max(pnls), 1) if pnls else 0, "worst_day": round(min(pnls), 1) if pnls else 0,
        "closed_trades": closed, "n_closed": len(closed),
        "win_rate": tstats["win_rate"], "open_positions": len(positions),
        "curve": {"dates": curve_dates, "value": curve_val},
        "daily": daily, "holdings": holdings,
    }


# ---------- benchmarks ----------

def benchmark_metrics(ticker, start, capital, period="5y"):
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        c = df["Close"]
        c = c[c.index >= pd.Timestamp(start)]
        if len(c) < 20:
            return None
        values = (capital * c / c.iloc[0]).tolist()
        m = perf_metrics(values, capital)
        m["ticker"] = ticker
        return m
    except Exception:
        return None


def equal_weight_benchmark(data, start, capital):
    closes = pd.DataFrame({t: df["Close"] for t, df in data.items()}).sort_index()
    rets = closes.pct_change()
    rets = rets[rets.index >= pd.Timestamp(start)]
    values = (capital * (1 + rets.mean(axis=1).fillna(0)).cumprod()).tolist()
    return perf_metrics(values, capital)


# ---------- orchestration ----------

def run_all(paper_strategy="trend_rsi_vol", universe="nifty100", period="5y",
            live_start="2026-11-12", backtest_years=3, top_k=TOP_K,
            capital=CAPITAL, risk_pct=RISK_PCT):
    tickers = get_universe(universe)
    data = download_prices(tickers, period=period)
    asof = pd.Timestamp.now().normalize()
    bt_start = str((asof - pd.DateOffset(years=backtest_years)).date())

    backtest = portfolio_sim(paper_strategy, data, bt_start, capital=capital, top_k=top_k, risk_pct=risk_pct)
    live = portfolio_sim(paper_strategy, data, live_start, capital=capital, top_k=top_k, risk_pct=risk_pct)

    benches = []
    n50 = benchmark_metrics(BENCH_N50, bt_start, capital, period)
    if n50:
        n50["name"] = "Nifty 50 TRI (proxy)"; benches.append(n50)
    for tk in BENCH_N500_CANDIDATES:
        n500 = benchmark_metrics(tk, bt_start, capital, period)
        if n500:
            n500["name"] = "Nifty 500 TRI (proxy)"; benches.append(n500); break
    ew = equal_weight_benchmark(data, bt_start, capital)
    ew["name"] = "Stocks buy & hold (equal wt)"; benches.append(ew)

    return {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "universe": universe, "universe_loaded": len(data),
        "backtest_start": bt_start, "backtest_years": backtest_years,
        "backtest": backtest, "paper": live, "benchmarks": benches,
    }


if __name__ == "__main__":
    res = run_all(backtest_years=3)
    b = res["backtest"]
    print(f"BACKTEST ({res['backtest_start']} ->, {res['universe_loaded']} stocks, after costs)")
    print(f"  CAGR {b['perf']['cagr']}%  Sharpe {b['perf']['sharpe']}  Sortino {b['perf']['sortino']}  "
          f"maxDD {b['perf']['maxdd']}%  Calmar {b['perf']['calmar']}")
    print(f"  trades {b['n_closed']}  win {b['win_rate']}%  PF {b['trades_stats']['profit_factor']}  "
          f"expectancy Rs.{b['trades_stats']['expectancy']}")
    print("  BENCHMARKS:")
    for bm in res["benchmarks"]:
        print(f"    {bm['name']:<30} CAGR {bm['cagr']}%  Sharpe {bm['sharpe']}  maxDD {bm['maxdd']}%")
