"""
The trading universe — a basket of liquid, large-cap NSE stocks (the NIFTY 50
names). The system scans ALL of these automatically every day and picks what to
trade from them, rather than you hand-choosing a few.

All tickers use Yahoo Finance's '.NS' suffix. If any ticker ever stops
returning data, the engine simply skips it that run.

Swap NIFTY50 for NIFTY100 (or your own list) to widen the net.
"""

NIFTY50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "NESTLEIND.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "M&M.NS",
    "TATAMOTORS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "COALINDIA.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS", "BRITANNIA.NS",
    "GRASIM.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
    "BAJAJ-AUTO.NS", "INDUSINDBK.NS", "TECHM.NS", "APOLLOHOSP.NS", "TATACONSUM.NS",
    "BPCL.NS", "HINDALCO.NS", "LTIM.NS", "SHRIRAMFIN.NS", "TRENT.NS",
]


# A wider net — the Nifty-100-ish large & mid caps. Any name that fits the
# strategy can be picked; the engine skips any ticker that fails to load.
NIFTY_NEXT = [
    "DMART.NS", "PIDILITIND.NS", "GODREJCP.NS", "SIEMENS.NS", "ABB.NS", "HAVELLS.NS",
    "DABUR.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IOC.NS", "GAIL.NS", "VEDL.NS",
    "AMBUJACEM.NS", "ACC.NS", "SHREECEM.NS", "TORNTPHARM.NS", "LUPIN.NS", "AUROPHARMA.NS",
    "BIOCON.NS", "ZYDUSLIFE.NS", "MANKIND.NS", "DLF.NS", "GODREJPROP.NS", "MOTHERSON.NS",
    "BOSCHLTD.NS", "TVSMOTOR.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "ICICIPRULI.NS",
    "ICICIGI.NS", "HDFCAMC.NS", "SBICARD.NS", "NAUKRI.NS", "ETERNAL.NS", "POLICYBZR.NS",
    "IRCTC.NS", "IRFC.NS", "PFC.NS", "RECLTD.NS", "INDIGO.NS", "JUBLFOOD.NS", "COLPAL.NS",
    "MARICO.NS", "UNITDSPR.NS", "BERGEPAINT.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS",
    "OBEROIRLTY.NS",
]

NIFTY100 = NIFTY50 + NIFTY_NEXT


def get_universe(name: str = "nifty100"):
    name = name.lower()
    if name in ("nifty50", "nifty_50", "n50"):
        return list(NIFTY50)
    if name in ("nifty100", "nifty_100", "n100"):
        return list(NIFTY100)
    raise SystemExit(f"Unknown universe '{name}'. Available: nifty50, nifty100")
