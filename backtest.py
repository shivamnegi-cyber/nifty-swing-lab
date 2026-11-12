"""
Backtest any strategy from strategies.py on FREE daily data (Yahoo Finance),
or compare them all side by side.

Honest by design:
  - Signal is decided on a day's CLOSE; the position is held from the NEXT day
    (position = signal.shift(1)). No trading on tomorrow's information.
  - Brokerage + taxes + slippage charged on every buy and sell.
  - Always compared against buy & hold — the benchmark to beat.

Run:
    python backtest.py --all                      # compare every strategy
    python backtest.py --strategy ema_9_21 --chart
    python backtest.py --strategy rsi_reversion --ticker NIFTYBEES.NS
"""

import argparse
import pandas as pd
import yfinance as yf

from strategies import STRATEGIES, apply_strategy


def max_drawdown(equity: pd.Series) -> float:
    return (equity / equity.cummax() - 1.0).min()


def get_data(ticker, start):
    data = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if data.empty:
        raise SystemExit(f"No data for {ticker}. Check the ticker or your connection.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data


def evaluate(name, data, cost):
    df = apply_strategy(name, data)
    df["ret"] = df["Close"].pct_change()
    df["position"] = df["signal"].shift(1).fillna(0)
    df["turnover"] = df["position"].diff().abs().fillna(0)
    df["strat_ret"] = df["position"] * df["ret"] - df["turnover"] * cost
    df = df.dropna(subset=["ret"])
    df["strat_equity"] = (1 + df["strat_ret"]).cumprod()
    df["bh_equity"] = (1 + df["ret"]).cumprod()

    # per-trade win rate
    trades, entry = [], None
    for _, r in df.iterrows():
        if r["cross"] == 1 and entry is None:
            entry = r["Close"]
        elif r["cross"] == -1 and entry is not None:
            trades.append(r["Close"] / entry - 1 - 2 * cost)
            entry = None
    n = len(trades)
    win_rate = (sum(t > 0 for t in trades) / n) if n else 0.0

    years = len(df) / 252
    return {
        "name": name,
        "cagr": df["strat_equity"].iloc[-1] ** (1 / years) - 1,
        "total": df["strat_equity"].iloc[-1] - 1,
        "maxdd": max_drawdown(df["strat_equity"]),
        "trades": n,
        "win_rate": win_rate,
        "df": df,
        "bh_cagr": df["bh_equity"].iloc[-1] ** (1 / years) - 1,
        "bh_maxdd": max_drawdown(df["bh_equity"]),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", default="ema_9_21", choices=list(STRATEGIES))
    p.add_argument("--all", action="store_true", help="compare every strategy")
    p.add_argument("--ticker", default="^NSEI")
    p.add_argument("--start", default="2010-01-01")
    p.add_argument("--cost", type=float, default=0.0015)
    p.add_argument("--chart", action="store_true")
    args = p.parse_args()

    data = get_data(args.ticker, args.start)
    names = list(STRATEGIES) if args.all else [args.strategy]
    results = [evaluate(n, data, args.cost) for n in names]
    ref = results[0]

    print("=" * 74)
    print(f"  SWING STRATEGY BACKTEST  —  {args.ticker}  "
          f"({ref['df'].index[0].date()} to {ref['df'].index[-1].date()}, "
          f"{len(ref['df'])/252:.1f}y, cost {args.cost*100:.2f}%/side)")
    print("=" * 74)
    print(f"  {'strategy':<16}{'CAGR':>8}{'total':>9}{'maxDD':>9}{'trades':>8}{'win%':>7}")
    print("  " + "-" * 70)
    for r in results:
        print(f"  {r['name']:<16}{r['cagr']*100:>7.1f}%{r['total']*100:>8.0f}%"
              f"{r['maxdd']*100:>8.1f}%{r['trades']:>8d}{r['win_rate']*100:>6.0f}%")
    print("  " + "-" * 70)
    print(f"  {'buy & hold':<16}{ref['bh_cagr']*100:>7.1f}%{'':>9}{ref['bh_maxdd']*100:>8.1f}%")
    print("=" * 74)
    print("  Read it honestly: higher CAGR is better, a smaller (less negative)")
    print("  maxDD means a gentler worst-case fall. Beating buy & hold on BOTH is rare.")
    print("=" * 74)

    if args.chart:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 5))
        for r in results:
            ax.plot(r["df"].index, r["df"]["strat_equity"], linewidth=1.4, label=r["name"])
        ax.plot(ref["df"].index, ref["df"]["bh_equity"], "k--", linewidth=1.1, label="buy & hold")
        ax.set_title(f"Strategy equity curves — {args.ticker}")
        ax.set_ylabel("growth of 1 unit")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig("equity_curve.png", dpi=130)
        print("Saved equity_curve.png")


if __name__ == "__main__":
    main()
