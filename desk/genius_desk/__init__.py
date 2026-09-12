"""GENIUS Desk: the always-on runner that takes the lab's agents to a real venue.

Three analyst books (ATLAS, EUCLID, FLUX), one signer (HERMES), one gate (VETO),
one auditor (LEDGER). Runs one cycle per hourly bar in one of three modes:

  shadow  computes every order and fills it on paper against the live market
          with the venue's real fee model. Sends nothing. Default.
  live    places real orders on Hyperliquid perps, one sub-account per book,
          with exchange-side stop orders mirroring our own. The desk holds an
          agent key that can trade but cannot withdraw.
  halted  the kill switch has been pulled: flatten everything, trade nothing.

Reuses the lab's agents, risk engine and data layer unchanged. The only new
code paths are the venue adapters, persistence, and publishing.
"""

__version__ = "0.1.0"
