"""
Permanent, auditable records. The evening run writes the portfolio's full state
to these files; the GitHub workflow commits them, so git history is a tamper-
evident audit trail of every trading decision.

Because the engine reconstructs the portfolio deterministically from history,
these files are always the correct current truth — a missed or crashed run
self-heals on the next run (no corrupted half-state).
"""

import json
import logging
import os
from datetime import datetime

import pandas as pd

import config

log = logging.getLogger("records")


def ensure_dirs():
    os.makedirs(config.RECORDS_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)


def _path(name):
    return os.path.join(config.RECORDS_DIR, name)


def write_live_records(paper):
    """paper = the engine's live portfolio result dict."""
    ensure_dirs()
    pd.DataFrame(paper["closed_trades"]).to_csv(_path("trades.csv"), index=False)
    pd.DataFrame(paper["daily"]).to_csv(_path("daily.csv"), index=False)
    pd.DataFrame(paper["holdings"]).to_csv(_path("holdings.csv"), index=False)
    pd.DataFrame(paper.get("rejected", [])).to_csv(_path("rejected_signals.csv"), index=False)
    state = {
        "updated": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "mode": config.MODE, "start": paper["start"], "asof": paper["asof"],
        "value": paper["value"], "cash": paper["cash"],
        "pnl_abs": paper["pnl_abs"], "pnl_pct": paper["pnl_pct"],
        "open_positions": paper["open_positions"], "n_closed": paper["n_closed"],
        "win_rate": paper["win_rate"], "maxdd_pct": paper["perf"]["maxdd"],
    }
    with open(_path("state.json"), "w") as f:
        json.dump(state, f, indent=2, default=float)   # tolerate numpy numbers
    log.info("records written: %s", state)
    return state


def read_state():
    try:
        with open(_path("state.json")) as f:
            return json.load(f)
    except Exception:
        return None


def log_run(kind, ok, info=""):
    ensure_dirs()
    line = f"{datetime.utcnow().isoformat(timespec='seconds')}Z\t{kind}\t{'OK' if ok else 'FAIL'}\t{info}\n"
    with open(os.path.join(config.LOG_DIR, "runs.log"), "a") as f:
        f.write(line)
