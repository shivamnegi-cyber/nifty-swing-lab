"""
A small library of swing-trading strategies you can test and compare.

Every strategy takes a daily price frame (needs columns: Close, High, Low) and
returns the same frame with a 'signal' column added:
    signal = 1  -> we want to be LONG today
    signal = 0  -> we want to be FLAT today

The backtester and the paper trader both import from here, so the exact rule you
test is the rule you trade. To invent your own, write a function with the same
shape and add it to the STRATEGIES registry at the bottom.

These are all LONG-ONLY daily swing strategies (holds of days to weeks) — the
sweet spot for free data and a part-time trader. None of them is "the answer";
the point is to compare them honestly on the backtest.
"""

import pandas as pd


# ---------- helpers ----------

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def _hysteresis(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    """Enter long when `entry` is True, stay long until `exit_` is True. Returns 0/1."""
    out = []
    pos = 0
    for e, x in zip(entry.fillna(False), exit_.fillna(False)):
        if pos == 0 and e:
            pos = 1
        elif pos == 1 and x:
            pos = 0
        out.append(pos)
    return pd.Series(out, index=entry.index)


# ---------- strategies ----------

def sma_cross(df, fast=20, slow=50):
    """Baseline trend follower: long while fast SMA > slow SMA. Slow, few trades."""
    df = df.copy()
    f = df["Close"].rolling(fast).mean()
    s = df["Close"].rolling(slow).mean()
    df["signal"] = (f > s).astype(int)
    return df


def ema_cross(df, fast=9, slow=21):
    """Faster trend swing: long while 9-EMA > 21-EMA. More trades than 20/50."""
    df = df.copy()
    f = df["Close"].ewm(span=fast, adjust=False).mean()
    s = df["Close"].ewm(span=slow, adjust=False).mean()
    df["signal"] = (f > s).astype(int)
    return df


def rsi_reversion(df, period=14, low=35, high=55):
    """Mean reversion: buy when RSI dips below `low` (oversold), exit when it
    recovers above `high`. Aggressive, trades often, good in choppy markets."""
    df = df.copy()
    rsi = _rsi(df["Close"], period)
    df["signal"] = _hysteresis(rsi < low, rsi > high)
    return df


def donchian_breakout(df, entry_n=20, exit_n=10):
    """Momentum breakout: buy when Close breaks above the highest high of the
    last `entry_n` days, exit when it breaks below the lowest low of `exit_n`."""
    df = df.copy()
    upper = df["High"].rolling(entry_n).max().shift(1)
    lower = df["Low"].rolling(exit_n).min().shift(1)
    df["signal"] = _hysteresis(df["Close"] > upper, df["Close"] < lower)
    return df


def bollinger_reversion(df, period=20, k=2.0):
    """Mean reversion: buy when Close falls below the lower Bollinger band,
    exit when it climbs back above the middle (the moving average)."""
    df = df.copy()
    mid = df["Close"].rolling(period).mean()
    sd = df["Close"].rolling(period).std()
    lower_band = mid - k * sd
    df["signal"] = _hysteresis(df["Close"] < lower_band, df["Close"] > mid)
    return df


def atr(df, period=14):
    """Average True Range — how much a stock typically moves in a day. Used to
    place stops at a distance that fits each stock's own volatility."""
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def trend_rsi_vol(df, fast=20, slow=50, rsi_p=14, vol_p=20):
    """The combined strategy — three independent confirmations must agree:
      - TREND:  20-EMA above 50-EMA (we only trade with the trend)
      - MOMENTUM: RSI(14) above 50 (momentum is genuinely positive, not oversold)
      - VOLUME: today's volume above its 20-day average (real participation)
    It adds two columns the engine uses:
      - trend    : 1 while the trend holds (we keep a position while this is 1)
      - entry_ok : 1 only when all three confirmations agree (we open here)
    'signal' mirrors trend so the basket comparison still works.
    """
    out = df.copy()
    ef = out["Close"].ewm(span=fast, adjust=False).mean()
    es = out["Close"].ewm(span=slow, adjust=False).mean()
    out["trend"] = (ef > es).astype(int)
    rsi = _rsi(out["Close"], rsi_p)
    if "Volume" in out:
        vol_ok = out["Volume"] > out["Volume"].rolling(vol_p).mean()
    else:
        vol_ok = True
    out["entry_ok"] = ((out["trend"] == 1) & (rsi > 50) & vol_ok).astype(int)
    out["signal"] = out["trend"]
    return out


# ---------- registry ----------
# name -> (function, kwargs, one-line description)
STRATEGIES = {
    "trend_rsi_vol": (trend_rsi_vol,    {}, "EMA20/50 trend + RSI>50 + volume confirmation (combined)"),
    "sma_20_50":   (sma_cross,          {"fast": 20, "slow": 50}, "Slow trend: 20/50 SMA crossover (baseline)"),
    "ema_9_21":    (ema_cross,          {"fast": 9, "slow": 21},  "Faster trend swing: 9/21 EMA crossover"),
    "rsi_reversion": (rsi_reversion,    {"low": 35, "high": 55},  "Buy oversold RSI<35, exit RSI>55"),
    "donchian":    (donchian_breakout,  {"entry_n": 20, "exit_n": 10}, "20-day high breakout, 10-day low exit"),
    "bollinger":   (bollinger_reversion,{"period": 20, "k": 2.0}, "Buy below lower band, exit at the mean"),
}


def apply_strategy(name, df):
    if name not in STRATEGIES:
        raise SystemExit(f"Unknown strategy '{name}'. Choices: {', '.join(STRATEGIES)}")
    func, kwargs, _ = STRATEGIES[name]
    out = func(df, **kwargs)
    out["cross"] = out["signal"].diff().fillna(0)   # +1 = fresh entry, -1 = fresh exit
    return out
