"""Spot SOL/USDC on Solana through Jupiter, signed by a dedicated desk wallet.

The simplest possible real venue: one Phantom wallet, SOL and USDC, every swap
visible on Solscan. What that simplicity costs, stated plainly:

  * LONG ONLY. "long" = hold SOL, "flat" = hold USDC. A short signal means the
    book stands aside. The runner enforces this through `long_only`.
  * The wallet key signs swaps, so it could also move funds. This venue is for
    a dedicated pilot wallet holding only the pilot money. Never a main wallet.
  * Spot has no exchange-side stops. The desk watches stops itself
    (`check_stops`, called by the loop every minute) and swaps out.

Books are internal: each book owns a slice of the wallet's USDC and SOL. On
chain there is one wallet; the desk reconciles the sum against it every cycle.
P&L is exact, from the USDC actually spent and actually received.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request

from .venue import Closed, Fill, Position, Venue

SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUP = "https://lite-api.jup.ag"
PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
SOL_FEE_RESERVE = 0.03          # SOL kept back for transaction fees, never swapped


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "genius-desk/0.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _post(url: str, body: dict):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "genius-desk/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


class SolanaVenue(Venue):
    mode = "live"
    long_only = True

    def __init__(self, books: list[str], wallet_key: str, rpc_url: str | None = None,
                 fee_bps: float = 10.0, slippage_bps: int = 50):
        from solders.keypair import Keypair
        self.kp = Keypair.from_base58_string(wallet_key)
        self.pubkey = str(self.kp.pubkey())
        self.rpc = rpc_url or PUBLIC_RPC
        self.fee_bps = fee_bps          # accounting estimate only; real P&L uses real amounts
        self.slippage_bps = slippage_bps
        self.book_names = list(books)
        self.b: dict[str, dict] = {n: {"usdc": 0.0, "sol": 0.0, "entry": 0.0, "stop": None,
                                       "since_ts": 0, "entry_usdc": 0.0} for n in books}
        self.fills: list[Fill] = []
        self.closed: list[Closed] = []
        self._mark = 0.0

    # -- chain reads ------------------------------------------------------------
    def _rpc(self, method: str, params: list):
        out = _post(self.rpc, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        if "error" in out:
            raise RuntimeError(f"rpc {method}: {out['error']}")
        return out["result"]

    def sol_balance(self) -> float:
        return self._rpc("getBalance", [self.pubkey])["value"] / 1e9

    def usdc_balance(self) -> float:
        res = self._rpc("getTokenAccountsByOwner",
                        [self.pubkey, {"mint": USDC_MINT}, {"encoding": "jsonParsed"}])
        total = 0.0
        for acc in res.get("value", []):
            total += float(acc["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
        return total

    def mark_price(self) -> float:
        try:
            j = _get(f"{JUP}/price/v3?ids={SOL_MINT}")
            self._mark = float(j[SOL_MINT]["usdPrice"])
        except Exception:
            pass
        return self._mark

    # -- book views ------------------------------------------------------------
    def equity(self, book: str) -> float:
        bk = self.b[book]
        return bk["usdc"] + bk["sol"] * (self._mark or self.mark_price())

    def position(self, book: str) -> Position | None:
        bk = self.b[book]
        if bk["sol"] <= 0:
            return None
        mark = self._mark or self.mark_price()
        return Position(side="long", qty=bk["sol"], entry=bk["entry"], mark=mark,
                        unrealized=(mark - bk["entry"]) * bk["sol"], stop=bk["stop"],
                        since_ts=bk["since_ts"])

    # -- the swap --------------------------------------------------------------
    def _swap(self, in_mint: str, out_mint: str, amount_raw: int) -> tuple[str, float, float]:
        """Quote, build, sign, send, confirm. Returns (signature, sol_delta, usdc_delta)
        measured from real balance changes, so fills are exact."""
        from solders.transaction import VersionedTransaction
        q = _get(f"{JUP}/swap/v1/quote?inputMint={in_mint}&outputMint={out_mint}"
                 f"&amount={amount_raw}&slippageBps={self.slippage_bps}")
        built = _post(f"{JUP}/swap/v1/swap", {
            "quoteResponse": q, "userPublicKey": self.pubkey, "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True, "prioritizationFeeLamports": "auto"})
        raw = VersionedTransaction.from_bytes(base64.b64decode(built["swapTransaction"]))
        signed = VersionedTransaction(raw.message, [self.kp])
        sol0, usdc0 = self.sol_balance(), self.usdc_balance()
        sig = self._rpc("sendTransaction", [base64.b64encode(bytes(signed)).decode(),
                                            {"encoding": "base64", "skipPreflight": False, "maxRetries": 3}])
        for _ in range(40):                      # up to ~60s for confirmation
            st = self._rpc("getSignatureStatuses", [[sig]])["value"][0]
            if st and st.get("confirmationStatus") in ("confirmed", "finalized"):
                if st.get("err"):
                    raise RuntimeError(f"swap failed on-chain: {st['err']}")
                break
            time.sleep(1.5)
        else:
            raise RuntimeError("swap not confirmed in time; check the signature on Solscan before retrying")
        sol1, usdc1 = self.sol_balance(), self.usdc_balance()
        return sig, sol1 - sol0, usdc1 - usdc0

    # -- HERMES' verbs -----------------------------------------------------------
    def open(self, book, side, qty, mark, stop, atr) -> Fill:
        assert side == "long", "spot desk is long only"
        bk = self.b[book]
        assert bk["sol"] <= 0, f"{book}: one position at a time"
        usdc_in = min(bk["usdc"], qty * mark)
        if usdc_in < 1.0:
            raise RuntimeError(f"{book}: not enough USDC for the order (${usdc_in:.2f})")
        sig, d_sol, d_usdc = self._swap(USDC_MINT, SOL_MINT, int(round(usdc_in * 1e6)))
        got_sol, spent = max(d_sol, 0.0), max(-d_usdc, 0.0)
        if got_sol <= 0:
            raise RuntimeError("swap confirmed but no SOL received; check on Solscan")
        px = spent / got_sol
        bk.update({"usdc": bk["usdc"] - spent, "sol": got_sol, "entry": px, "stop": stop,
                   "since_ts": int(time.time()), "entry_usdc": spent})
        f = Fill(ts=int(time.time()), book=book, side="buy", qty=got_sol, price=round(px, 4),
                 fee=0.0, tx=sig, note="jupiter swap")
        self.fills.append(f)
        return f

    def close(self, book, mark, atr, reason) -> Closed:
        bk = self.b[book]
        assert bk["sol"] > 0, f"{book}: nothing to close"
        sig, d_sol, d_usdc = self._swap(SOL_MINT, USDC_MINT, int(round(bk["sol"] * 1e9)))
        received = max(d_usdc, 0.0)
        pnl = received - bk["entry_usdc"]
        c = Closed(book=book, open_ts=bk["since_ts"], close_ts=int(time.time()), side="long",
                   qty=bk["sol"], entry=bk["entry"], exit=round(received / bk["sol"], 4),
                   pnl=round(pnl, 4), costs=0.0, reason=reason, tx=sig)
        self.fills.append(Fill(ts=c.close_ts, book=book, side="sell", qty=bk["sol"], price=c.exit,
                               fee=0.0, tx=sig, note="jupiter swap"))
        self.closed.append(c)
        bk.update({"usdc": bk["usdc"] + received, "sol": 0.0, "entry": 0.0, "stop": None,
                   "since_ts": 0, "entry_usdc": 0.0})
        return c

    def flatten_all(self, mark, atr, reason) -> list[Closed]:
        return [self.close(n, mark, atr, reason) for n in self.book_names if self.b[n]["sol"] > 0]

    # -- setup + safety ----------------------------------------------------------
    def init_cash(self) -> dict:
        """One time, after funding: convert wallet SOL above the fee reserve to USDC
        and split all USDC equally across the books."""
        sol = self.sol_balance()
        spare = sol - SOL_FEE_RESERVE
        sig = None
        if spare > 0.01:
            sig, _, _ = self._swap(SOL_MINT, USDC_MINT, int(round(spare * 1e9)))
        usdc = self.usdc_balance()
        share = usdc / len(self.book_names)
        for n in self.book_names:
            self.b[n].update({"usdc": share, "sol": 0.0, "entry": 0.0, "stop": None,
                              "since_ts": 0, "entry_usdc": 0.0})
        return {"sol_left": round(self.sol_balance(), 4), "usdc": round(usdc, 2),
                "per_book": round(share, 2), "tx": sig}

    def check_stops(self) -> list[Closed]:
        """Spot has no exchange-side stops; the loop calls this every minute."""
        mark = self.mark_price()
        out = []
        for n in self.book_names:
            bk = self.b[n]
            if bk["sol"] > 0 and bk["stop"] and mark and mark <= bk["stop"]:
                out.append(self.close(n, mark, 0.0, "stop (invalidation) hit"))
        return out

    def reconcile(self) -> str:
        """Sum of the books vs the chain, with tolerance for fees and dust."""
        try:
            sol, usdc = self.sol_balance(), self.usdc_balance()
        except Exception as e:
            return f"rpc unavailable: {e}"
        bsol = sum(b["sol"] for b in self.b.values())
        busdc = sum(b["usdc"] for b in self.b.values())
        problems = []
        if abs((sol - SOL_FEE_RESERVE) - bsol) > max(0.005, 0.02 * max(bsol, 0.01)):
            problems.append(f"SOL on-chain {sol:.4f} (reserve {SOL_FEE_RESERVE}) vs books {bsol:.4f}")
        if abs(usdc - busdc) > max(0.5, 0.02 * max(busdc, 1)):
            problems.append(f"USDC on-chain {usdc:.2f} vs books {busdc:.2f}")
        return "; ".join(problems)

    def snapshot(self) -> dict:
        return {"books": self.b, "mark": self._mark,
                "closed": [c.to_dict() for c in self.closed][-500:],
                "fills": [f.to_dict() for f in self.fills][-500:]}

    def restore(self, snap: dict) -> None:
        for n, v in snap.get("books", {}).items():
            if n in self.b:
                self.b[n].update(v)
        self._mark = snap.get("mark", 0.0)
        self.closed = [Closed(**c) for c in snap.get("closed", [])]
        self.fills = [Fill(**f) for f in snap.get("fills", [])]
