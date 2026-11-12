"""
The execution seam — the ONE place a real order would ever be placed.

This is what makes the paper -> live transition a configuration change, not a
rewrite. Today everything runs through PaperBroker (pure simulation). When you
later subscribe to Groww and are ready, LiveBroker is wired here — and it still
refuses to act unless config.is_live_allowed() passes every safety check.

In THIS build, LiveBroker intentionally raises: no real order can be placed,
by construction, during development and paper trading.
"""

import config


class PaperBroker:
    """Simulates orders. Never touches a real account."""
    mode = "paper"

    def place_order(self, symbol, side, qty, price):
        # The portfolio engine does the full cost-accurate simulation; this is
        # the interface the live transition will mirror.
        return {"status": "SIMULATED", "symbol": symbol, "side": side,
                "qty": qty, "price": price}

    def positions(self):
        return {}


class LiveBroker:
    """Groww live orders — deliberately not implemented in this phase."""
    mode = "live"

    def place_order(self, symbol, side, qty, price):
        if not config.is_live_allowed():
            raise PermissionError(
                "Live trading is not authorised. It needs MODE=live, the "
                "confirmation phrase, and Groww API credentials — see config.py."
            )
        raise NotImplementedError(
            "Groww live execution is a future step: it requires the Groww API "
            "SDK, your credentials, order validation and reconciliation to be "
            "wired here. No real order is placed by this build."
        )


def get_broker():
    """Paper unless live is fully authorised. Live still cannot execute here."""
    if config.is_live_allowed():
        return LiveBroker()
    return PaperBroker()
