"""Spot on Uniswap v3, Robinhood Chain, signed by the desk's own 0x wallet.

One wallet does two jobs: it receives the token's trade fees and HERMES trades
from it. Cash is USDG (Global Dollar, the chain's stablecoin), the asset is an
ERC-20 chosen in config (WETH by default; a Robinhood stock token such as NVDA
works the same way). Every swap is a normal transaction on Blockscout.

What this simplicity costs, stated plainly:

  * LONG ONLY. "long" = hold the asset, "flat" = hold USDG. The runner enforces
    this through `long_only`; short reads stand aside.
  * The wallet key signs swaps, so it could also move funds. This wallet holds
    fee income and nothing else. Never a main wallet.
  * Spot has no exchange-side stops. The desk watches stops itself
    (`check_stops`, called by the loop every minute) and swaps out.
  * Gas is paid in ETH. The wallet keeps a small ETH reserve that is never
    swapped; with no ETH at all, nothing can move (see `reconcile`).

Books are internal: each owns a slice of the wallet's USDG and asset. On chain
there is one wallet; the desk reconciles the sum against it every cycle. P&L
is exact, from the USDG actually spent and actually received.

Pure JSON-RPC plus eth_account for signing; no third-party trade API, no key.
"""

from __future__ import annotations

import json
import time
import urllib.request

from .venue import Closed, Fill, Position, Venue

CHAIN_ID = 4663
PUBLIC_RPC = "https://rpc.mainnet.chain.robinhood.com"
EXPLORER = "https://robinhoodchain.blockscout.com"

# Uniswap v3 on Robinhood Chain (developers.uniswap.org/deployments, verified on chain)
V3_FACTORY = "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA"
QUOTER_V2 = "0x33e885eD0Ec9bF04EcfB19341582aADCb4c8A9E7"
SWAP_ROUTER_02 = "0xCaf681a66D020601342297493863E78C959E5cb2"

TOKENS = {   # symbol -> (address, decimals). Only what the desk needs.
    "USDG": ("0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168", 6),
    "WETH": ("0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73", 18),
    "NVDA": ("0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC", 18),
}
ETH_GAS_RESERVE = 0.002          # ETH kept for gas, never swapped (Orbit gas is fractions of a cent)
MAX_UINT = 2 ** 256 - 1

# function selectors (keccak of the signature, first 4 bytes)
SEL = {
    "balanceOf": "0x70a08231", "allowance": "0xdd62ed3e", "approve": "0x095ea7b3",
    "getPool": "0x1698ee82", "slot0": "0x3850c7bd", "tokenPaused": "0x86c75e74", "paused": "0x5c975abb",
    "quoteExactInputSingle": "0xc6a5026a",   # QuoterV2 ((address,address,uint256,uint24,uint160))
    "exactInputSingle": "0x04e45aaf",        # SwapRouter02 ((address,address,uint24,address,uint256,uint256,uint160))
}


def _pad(x: int) -> str:
    return format(x, "064x")


def _addr(a: str) -> str:
    return _pad(int(a, 16))


class UniswapVenue(Venue):
    mode = "live"
    long_only = True

    def __init__(self, books: list[str], wallet_key: str, rpc_url: str | None = None,
                 asset: str = "WETH", pool_fee: int = 500, fee_bps: float = 5.0,
                 slippage_bps: int = 50, fee_token: str | None = None):
        from eth_account import Account
        self.acct = Account.from_key(wallet_key)
        self.address = self.acct.address
        self.rpc = rpc_url or PUBLIC_RPC
        self.asset_sym = asset
        self.asset, self.asset_dec = TOKENS[asset]
        self.cash, self.cash_dec = TOKENS["USDG"]
        self.fee_token = fee_token            # optional: token the fees arrive in, sold to USDG by init_cash
        self.pool_fee = pool_fee              # 500 = 0.05 %
        self.fee_bps = fee_bps                # accounting estimate only; real P&L uses real amounts
        self.slippage_bps = slippage_bps
        self.book_names = list(books)
        self.b: dict[str, dict] = {n: {"usdc": 0.0, "sol": 0.0, "entry": 0.0, "stop": None,
                                       "since_ts": 0, "entry_usdc": 0.0} for n in books}
        # field names kept identical to the Solana venue so state, publish and tests
        # read the same shape: "usdc" = cash (USDG), "sol" = asset units.
        self.fills: list[Fill] = []
        self.closed: list[Closed] = []
        self._mark = 0.0
        self._pool: str | None = None

    # -- chain reads ------------------------------------------------------------
    def _rpc(self, method: str, params: list):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.rpc, data=body, headers={
            "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 genius-desk/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read())
        if "error" in out:
            raise RuntimeError(f"rpc {method}: {out['error']}")
        return out["result"]

    def _call(self, to: str, data: str) -> str:
        return self._rpc("eth_call", [{"to": to, "data": data}, "latest"])

    def _uint(self, hexres: str, word: int = 0) -> int:
        h = hexres[2:]
        return int(h[word * 64:(word + 1) * 64], 16) if len(h) >= (word + 1) * 64 else 0

    def eth_balance(self) -> float:
        return int(self._rpc("eth_getBalance", [self.address, "latest"]), 16) / 1e18

    def _erc20_balance(self, token: str, dec: int) -> float:
        return self._uint(self._call(token, SEL["balanceOf"] + _addr(self.address))) / 10 ** dec

    def usdc_balance(self) -> float:            # name kept for shape parity with SolanaVenue
        return self._erc20_balance(self.cash, self.cash_dec)

    def sol_balance(self) -> float:             # asset units
        return self._erc20_balance(self.asset, self.asset_dec)

    def pool(self) -> str:
        if not self._pool:
            res = self._call(V3_FACTORY, SEL["getPool"] + _addr(self.asset) + _addr(self.cash) + _pad(self.pool_fee))
            p = "0x" + res[-40:]
            if int(p, 16) == 0:
                raise RuntimeError(f"no Uniswap v3 {self.asset_sym}/USDG pool at fee {self.pool_fee}")
            self._pool = p
        return self._pool

    def mark_price(self) -> float:
        """USDG per asset unit from the pool's current sqrt price."""
        try:
            sqrt = self._uint(self._call(self.pool(), SEL["slot0"]), 0)
            price01 = (sqrt / 2 ** 96) ** 2              # token1 per token0, raw units
            if int(self.asset, 16) < int(self.cash, 16):  # asset is token0
                self._mark = price01 * 10 ** (self.asset_dec - self.cash_dec)
            else:                                        # cash is token0
                self._mark = (1 / price01) * 10 ** (self.asset_dec - self.cash_dec)
        except Exception:
            pass
        return self._mark

    def asset_paused(self) -> bool:
        """Robinhood stock tokens can be paused by the issuer; WETH cannot."""
        for sel in ("tokenPaused", "paused"):
            try:
                res = self._call(self.asset, SEL[sel])
                if res and res != "0x":
                    return bool(self._uint(res))
            except Exception:
                continue
        return False

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

    # -- transactions ------------------------------------------------------------
    def _send(self, to: str, data: str, value: int = 0) -> str:
        """Estimate, sign locally, send, wait for the receipt. Returns the tx hash.
        Raises if the chain reverts; nothing is retried blindly."""
        nonce = int(self._rpc("eth_getTransactionCount", [self.address, "pending"]), 16)
        gas_price = int(self._rpc("eth_gasPrice", []), 16)
        tx = {"chainId": CHAIN_ID, "from": self.address, "to": to, "data": data, "value": value,
              "nonce": nonce, "maxFeePerGas": gas_price * 2, "maxPriorityFeePerGas": 0}
        est = int(self._rpc("eth_estimateGas", [{"from": self.address, "to": to, "data": data,
                                                  "value": hex(value)}]), 16)
        tx["gas"] = int(est * 1.3) + 10_000
        tx.pop("from")
        signed = self.acct.sign_transaction(tx)
        raw = signed.raw_transaction if hasattr(signed, "raw_transaction") else signed.rawTransaction
        h = self._rpc("eth_sendRawTransaction", ["0x" + bytes(raw).hex()])
        for _ in range(60):
            rec = self._rpc("eth_getTransactionReceipt", [h])
            if rec:
                if int(rec.get("status", "0x0"), 16) != 1:
                    raise RuntimeError(f"transaction reverted on-chain: {EXPLORER}/tx/{h}")
                return h
            time.sleep(1.0)
        raise RuntimeError(f"transaction not mined in time; check {EXPLORER}/tx/{h} before retrying")

    def _ensure_allowance(self, token: str, amount_raw: int) -> None:
        cur = self._uint(self._call(token, SEL["allowance"] + _addr(self.address) + _addr(SWAP_ROUTER_02)))
        if cur < amount_raw:
            self._send(token, SEL["approve"] + _addr(SWAP_ROUTER_02) + _pad(MAX_UINT))

    def quote(self, token_in: str, token_out: str, amount_raw: int, fee: int | None = None) -> int:
        fee = fee or self.pool_fee
        data = (SEL["quoteExactInputSingle"] + _addr(token_in) + _addr(token_out)
                + _pad(amount_raw) + _pad(fee) + _pad(0))
        return self._uint(self._call(QUOTER_V2, data), 0)

    def _swap(self, token_in: str, token_out: str, amount_raw: int,
              fee: int | None = None) -> tuple[str, float, float]:
        """Quote, approve if needed, swap through SwapRouter02, wait. Returns
        (tx_hash, asset_delta, cash_delta) from real balance changes."""
        fee = fee or self.pool_fee
        out = self.quote(token_in, token_out, amount_raw, fee)
        if out <= 0:
            raise RuntimeError("quoter returned zero; pool empty or token paused")
        min_out = out * (10_000 - self.slippage_bps) // 10_000
        self._ensure_allowance(token_in, amount_raw)
        data = (SEL["exactInputSingle"] + _addr(token_in) + _addr(token_out) + _pad(fee)
                + _addr(self.address) + _pad(amount_raw) + _pad(min_out) + _pad(0))
        a0, c0 = self.sol_balance(), self.usdc_balance()
        h = self._send(SWAP_ROUTER_02, data)
        a1, c1 = self.sol_balance(), self.usdc_balance()
        return h, a1 - a0, c1 - c0

    # -- HERMES' verbs -----------------------------------------------------------
    def open(self, book, side, qty, mark, stop, atr) -> Fill:
        assert side == "long", "spot desk is long only"
        bk = self.b[book]
        assert bk["sol"] <= 0, f"{book}: one position at a time"
        if self.asset_paused():
            raise RuntimeError(f"{self.asset_sym} transfers are paused by the issuer; standing aside")
        cash_in = min(bk["usdc"], qty * mark)
        if cash_in < 1.0:
            raise RuntimeError(f"{book}: not enough USDG for the order (${cash_in:.2f})")
        h, d_asset, d_cash = self._swap(self.cash, self.asset, int(round(cash_in * 10 ** self.cash_dec)))
        got, spent = max(d_asset, 0.0), max(-d_cash, 0.0)
        if got <= 0:
            raise RuntimeError(f"swap mined but no {self.asset_sym} received; check {EXPLORER}/tx/{h}")
        px = spent / got
        bk.update({"usdc": bk["usdc"] - spent, "sol": got, "entry": px, "stop": stop,
                   "since_ts": int(time.time()), "entry_usdc": spent})
        f = Fill(ts=int(time.time()), book=book, side="buy", qty=got, price=round(px, 4),
                 fee=0.0, tx=h, note="uniswap v3 swap")
        self.fills.append(f)
        return f

    def close(self, book, mark, atr, reason) -> Closed:
        bk = self.b[book]
        assert bk["sol"] > 0, f"{book}: nothing to close"
        h, d_asset, d_cash = self._swap(self.asset, self.cash, int(round(bk["sol"] * 10 ** self.asset_dec)))
        received = max(d_cash, 0.0)
        pnl = received - bk["entry_usdc"]
        c = Closed(book=book, open_ts=bk["since_ts"], close_ts=int(time.time()), side="long",
                   qty=bk["sol"], entry=bk["entry"], exit=round(received / bk["sol"], 4),
                   pnl=round(pnl, 4), costs=0.0, reason=reason, tx=h)
        self.fills.append(Fill(ts=c.close_ts, book=book, side="sell", qty=bk["sol"], price=c.exit,
                               fee=0.0, tx=h, note="uniswap v3 swap"))
        self.closed.append(c)
        bk.update({"usdc": bk["usdc"] + received, "sol": 0.0, "entry": 0.0, "stop": None,
                   "since_ts": 0, "entry_usdc": 0.0})
        return c

    def flatten_all(self, mark, atr, reason) -> list[Closed]:
        return [self.close(n, mark, atr, reason) for n in self.book_names if self.b[n]["sol"] > 0]

    # -- setup + safety ----------------------------------------------------------
    def init_cash(self) -> dict:
        """After fees have landed: sell whatever the fees arrived in (the fee token,
        or the asset) for USDG, keep the ETH gas reserve, split USDG equally
        across the books. Run it again whenever new fees arrive."""
        txs = []
        if self.fee_token and self.fee_token in TOKENS and self.fee_token not in ("USDG", self.asset_sym):
            addr, dec = TOKENS[self.fee_token]
            bal = self._erc20_balance(addr, dec)
            if bal > 0:
                for fee in (self.pool_fee, 3000, 10000, 100):
                    try:
                        h, _, _ = self._swap(addr, self.cash, int(bal * 10 ** dec), fee)
                        txs.append(h); break
                    except Exception:
                        continue
        held = sum(b["sol"] for b in self.b.values())
        spare_asset = self.sol_balance() - held
        if spare_asset * (self._mark or self.mark_price() or 0) > 1.0:
            h, _, _ = self._swap(self.asset, self.cash, int(spare_asset * 10 ** self.asset_dec))
            txs.append(h)
        cash = self.usdc_balance()
        in_positions = sum(b["entry_usdc"] for b in self.b.values())
        share = (cash) / len(self.book_names)
        for n in self.book_names:
            self.b[n]["usdc"] = share
        return {"eth_for_gas": round(self.eth_balance(), 5), "usdg": round(cash, 2),
                "per_book": round(share, 2), "in_positions": round(in_positions, 2), "txs": txs}

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
        """Sum of the books vs the chain, with tolerance for dust. New fee income
        makes the chain richer than the books; that is reported, not a halt,
        because init_cash is the deliberate step that adopts it."""
        try:
            eth, asset, cash = self.eth_balance(), self.sol_balance(), self.usdc_balance()
        except Exception as e:
            return f"rpc unavailable: {e}"
        basset = sum(b["sol"] for b in self.b.values())
        bcash = sum(b["usdc"] for b in self.b.values())
        problems = []
        if asset + 1e-9 < basset - max(1e-6, 0.02 * basset):
            problems.append(f"{self.asset_sym} on-chain {asset:.6f} below books {basset:.6f}")
        if cash + 1e-6 < bcash - max(0.5, 0.02 * bcash):
            problems.append(f"USDG on-chain {cash:.2f} below books {bcash:.2f}")
        if eth < ETH_GAS_RESERVE / 4 and (basset > 0 or bcash > 0):
            problems.append(f"ETH for gas {eth:.5f}: too low to trade or exit; send a little ETH")
        return "; ".join(problems)

    def unadopted(self) -> dict:
        """Balances on chain that no book owns yet (fees that arrived)."""
        return {"usdg": round(self.usdc_balance() - sum(b["usdc"] for b in self.b.values()), 2),
                self.asset_sym: round(self.sol_balance() - sum(b["sol"] for b in self.b.values()), 6)}

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
