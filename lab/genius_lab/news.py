"""Fundamental news layer for ATLAS.

IMPLEMENTED: live headlines from public RSS feeds (no key, no account), scored
             with a small keyword lexicon into a directional bias in [-1, 1].
PLANNED:     an LLM reads the same headlines and writes the rationale. The
             lexicon is deliberately crude and deliberately transparent — every
             score can be traced to the exact words that produced it.

Time discipline: `NewsBias.bias_at(ts)` only sees items published *before* ts.
When the backtest replays history, ATLAS cannot read tomorrow's news. This is
enforced here, not left to the caller, and covered by a test.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime

FEEDS = [
    # (name, url) — general crypto + macro. All public RSS/Atom, no auth.
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
]

# Each term: weight in [-1, 1]. Matched case-insensitively on title + summary.
LEXICON = {
    # bullish
    "etf inflow": 0.6, "inflows": 0.4, "approval": 0.4, "approves": 0.4,
    "rate cut": 0.6, "cuts rates": 0.6, "dovish": 0.5, "adoption": 0.3,
    "record high": 0.5, "all-time high": 0.5, "accumulat": 0.3,
    "treasury reserve": 0.4, "buys bitcoin": 0.5, "adds bitcoin": 0.4,
    "institutional": 0.2, "rally": 0.3, "surge": 0.3, "bullish": 0.4,
    # bearish
    "outflow": -0.5, "outflows": -0.5, "hack": -0.6, "exploit": -0.6,
    "lawsuit": -0.4, "sues": -0.4, "ban": -0.5, "crackdown": -0.6,
    "rate hike": -0.6, "hikes rates": -0.6, "hawkish": -0.5,
    "inflation hotter": -0.5, "cpi hotter": -0.5, "liquidation": -0.4,
    "sell-off": -0.5, "selloff": -0.5, "plunge": -0.5, "crash": -0.6,
    "bankrupt": -0.7, "insolven": -0.7, "bearish": -0.4, "delist": -0.4,
    "sec charges": -0.6, "investigation": -0.3,
}

# Headlines that mention none of these are ignored — they carry no directional read.
_ASSET_TERMS = ("bitcoin", "btc", "crypto", "fed", "federal reserve", "rates",
                "inflation", "cpi", "etf", "sec", "treasury")


@dataclass
class NewsItem:
    ts: float
    title: str
    source: str
    link: str
    bias: float
    matched: list[str]

    def to_event(self) -> dict:
        return {"headline": self.title, "source": self.source, "link": self.link,
                "date": time.strftime("%Y-%m-%d %H:%M", time.gmtime(self.ts)),
                "bias": round(self.bias, 2), "matched": self.matched}


def score(text: str) -> tuple[float, list[str]]:
    """Lexicon score in [-1, 1] and the terms that produced it."""
    t = text.lower()
    if not any(a in t for a in _ASSET_TERMS):
        return 0.0, []
    hits = [(term, w) for term, w in LEXICON.items() if term in t]
    if not hits:
        return 0.0, []
    total = sum(w for _, w in hits)
    return max(-1.0, min(1.0, total)), [term for term, _ in hits]


def _text(el, *names) -> str:
    for n in names:
        found = el.find(n)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _parse_time(s: str) -> float | None:
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).timestamp()          # RFC 2822 (RSS)
    except Exception:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()  # ISO (Atom)
    except Exception:
        return None


def parse_feed(xml_bytes: bytes, source: str) -> list[NewsItem]:
    """RSS 2.0 or Atom → NewsItems (unscored items with bias 0 are dropped)."""
    root = ET.fromstring(xml_bytes)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = []
    entries = root.findall(".//item") or root.findall(".//a:entry", ns)
    for e in entries:
        title = _text(e, "title", "a:title") or _text(e, "{http://www.w3.org/2005/Atom}title")
        summary = (_text(e, "description", "a:summary") or
                   _text(e, "{http://www.w3.org/2005/Atom}summary"))
        link = _text(e, "link") or ""
        if not link:
            l = e.find("{http://www.w3.org/2005/Atom}link")
            link = l.get("href", "") if l is not None else ""
        ts = _parse_time(_text(e, "pubDate", "published", "updated") or
                         _text(e, "{http://www.w3.org/2005/Atom}published") or
                         _text(e, "{http://www.w3.org/2005/Atom}updated"))
        if not title or ts is None:
            continue
        bias, matched = score(title + " " + summary[:300])
        if not matched:
            continue
        items.append(NewsItem(ts=ts, title=title, source=source, link=link,
                              bias=bias, matched=matched))
    return items


def fetch_feed(name: str, url: str, timeout: float = 10.0) -> list[NewsItem]:
    req = urllib.request.Request(url, headers={"User-Agent": "genius-lab/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_feed(resp.read(), name)


def live_news(max_age_days: float = 40.0, cache_dir: str | None = None) -> "NewsBias | None":
    """Fetch every feed, keep items within max_age_days, cache to disk.

    Returns None only if *every* feed failed. Partial success is normal and the
    result records which feeds answered.
    """
    items: list[NewsItem] = []
    ok, failed = [], []
    cutoff = time.time() - max_age_days * 86400
    for name, url in FEEDS:
        try:
            got = [i for i in fetch_feed(name, url) if i.ts >= cutoff]
            items.extend(got)
            ok.append(f"{name} ({len(got)})")
        except Exception:
            failed.append(name)
    if not items and not ok:
        return None
    # dedupe on title
    seen, unique = set(), []
    for i in sorted(items, key=lambda i: i.ts):
        k = i.title.lower()
        if k not in seen:
            seen.add(k)
            unique.append(i)
    bias = NewsBias(unique, sources_ok=ok, sources_failed=failed)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"news-{time.strftime('%Y-%m-%d', time.gmtime())}.json")
        with open(path, "w") as f:
            json.dump([asdict(i) for i in unique], f)
    return bias


class NewsBias:
    """Time-aware bias: only items published before the queried bar count."""

    def __init__(self, items: list[NewsItem], sources_ok=None, sources_failed=None,
                 lookback_hours: float = 72.0):
        self.items = sorted(items, key=lambda i: i.ts)
        self.sources_ok = sources_ok or []
        self.sources_failed = sources_failed or []
        self.lookback = lookback_hours * 3600

    def bias_at(self, ts: float) -> tuple[float, list[dict]]:
        """Recency-weighted mean bias of items in (ts - lookback, ts]."""
        window = [i for i in self.items if ts - self.lookback < i.ts <= ts]
        if not window:
            return 0.0, []
        weights = [max(0.1, 1 - (ts - i.ts) / self.lookback) for i in window]
        bias = sum(i.bias * w for i, w in zip(window, weights)) / sum(weights)
        strongest = sorted(window, key=lambda i: -abs(i.bias))[:3]
        return max(-1.0, min(1.0, bias)), [i.to_event() for i in strongest]

    def summary(self) -> dict:
        return {"items": len(self.items), "sources_ok": self.sources_ok,
                "sources_failed": self.sources_failed,
                "span_days": round((self.items[-1].ts - self.items[0].ts) / 86400, 1)
                if len(self.items) > 1 else 0}
