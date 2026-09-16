"""GENIUS Desk: the always-on runner that takes the lab's agents to a real venue.

Three analyst books (ATLAS, EUCLID, FLUX), one signer (HERMES), one gate (VETO),
one auditor (LEDGER). Runs one cycle per hourly bar in one of three modes:

  shadow  computes every order and fills it on paper against the live market
          with the venue's real fee model. Sends nothing. Default.
  live    real swaps on Uniswap v3, Robinhood Chain, from the desk wallet
          that also receives the token's trade fees. Long only, spot, stops
          watched by the loop every minute.
  halted  the kill switch has been pulled: flatten everything, trade nothing.

Reuses the lab's agents, risk engine and data layer unchanged. The only new
code paths are the venue adapters, persistence, and publishing.
"""

__version__ = "0.1.0"


def _install_ca_bundle() -> None:
    """python.org builds of Python on macOS ship without a CA bundle wired into
    ssl, so every HTTPS call fails until one is pointed at. Prefer certifi (in
    the venv), else the system bundle. Harmless where the default already works."""
    import ssl
    import urllib.request
    try:
        ssl.create_default_context().load_default_certs()
        import socket
        ctx = ssl.create_default_context()
        if ctx.cert_store_stats().get("x509", 0) > 0:
            return
    except Exception:
        pass
    cafile = None
    try:
        import certifi
        cafile = certifi.where()
    except ImportError:
        import os
        for c in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
            if os.path.exists(c):
                cafile = c
                break
    if cafile:
        ctx = ssl.create_default_context(cafile=cafile)
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)))


_install_ca_bundle()
