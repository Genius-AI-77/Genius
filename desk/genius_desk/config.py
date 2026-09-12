"""Configuration and secrets.

Config is plain JSON (desk/config.json). Secrets are NEVER in config or the
repo: they are read from an env file the server operator writes by hand
(default /etc/genius-desk/secrets.env, mode 600), or from the environment.

    DESK_WALLET_KEY   base58 private key of the dedicated Solana desk wallet
                      (venue "solana"). Signs swaps. Pilot money only.
    DESK_RPC_URL      optional Solana RPC (a free Helius key is more reliable than public)
    DESK_AGENT_KEY    Hyperliquid agent key (venue "hyperliquid"): trade only, no withdraw
    DESK_ACCOUNT      Hyperliquid master wallet 0x address
    DESK_GIT_REMOTE   https://x-access-token:<token>@github.com/<user>/<repo>.git
                      (only if publish.git_push is true)
    DESK_TESTNET=1    use Hyperliquid testnet

Nothing that reads a secret ever prints it. `Secrets.__repr__` redacts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
DESK_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(DESK_DIR)
DEFAULT_SECRETS_FILE = "/etc/genius-desk/secrets.env"


@dataclass(frozen=True)
class BookConfig:
    name: str
    analyst: str          # fundamental | technical | orderflow
    sub_account: int


@dataclass(frozen=True)
class PublishConfig:
    targets: tuple = ("site/console/data.js", "genius-web/public/console/data.js")
    git_push: bool = False
    git_branch: str = "main"


@dataclass(frozen=True)
class DeskConfig:
    mode: str = "shadow"                      # shadow | live
    venue: str = "solana"                     # live venue: solana (spot, long only) | hyperliquid (perps)
    instrument: str = "SOL-USD"               # data instrument (Coinbase public)
    coin: str = "SOL"                         # asset the desk trades
    hl_books: dict = field(default_factory=dict)   # book name -> sub-account 0x address (public)
    bar_seconds: int = 3600
    warmup_bars: int = 60
    history_bars: int = 200
    max_holding_bars: int = 24
    order_step: float = 0.0001                # lot size (SOL spot: 4 decimals is plenty)
    min_order: float = 0.01                   # about $1 of SOL; Hyperliquid BTC would be 0.00014
    limits: str = "PILOT_100"                 # name in genius_lab.risk
    starting_cash_per_book: float = 33.33     # shadow mode starting equity per book
    books: tuple = (BookConfig("ATLAS", "fundamental", 0),
                    BookConfig("EUCLID", "technical", 1),
                    BookConfig("FLUX", "orderflow", 2))
    publish: PublishConfig = field(default_factory=PublishConfig)
    state_dir: str = os.path.join(DESK_DIR, "state")
    data_dir: str = os.path.join(DESK_DIR, "data")

    @staticmethod
    def load(path: str | None = None) -> "DeskConfig":
        path = path or os.path.join(DESK_DIR, "config.json")
        if not os.path.exists(path):
            return DeskConfig()
        raw = json.load(open(path))
        books = tuple(BookConfig(**b) for b in raw.pop("books", [])) or DeskConfig.books
        pub = PublishConfig(**{k: (tuple(v) if k == "targets" else v)
                               for k, v in raw.pop("publish", {}).items()})
        return DeskConfig(books=books, publish=pub, **raw)


@dataclass
class Secrets:
    wallet_key: str | None = None
    rpc_url: str | None = None
    agent_key: str | None = None
    account: str | None = None
    git_remote: str | None = None
    testnet: bool = False

    def __repr__(self) -> str:  # never leak
        return (f"Secrets(wallet_key={'set' if self.wallet_key else 'unset'}, "
                f"agent_key={'set' if self.agent_key else 'unset'}, "
                f"account={'set' if self.account else 'unset'}, "
                f"git_remote={'set' if self.git_remote else 'unset'}, testnet={self.testnet})")

    __str__ = __repr__

    @staticmethod
    def load(path: str | None = None) -> "Secrets":
        path = path or os.environ.get("DESK_SECRETS_FILE", DEFAULT_SECRETS_FILE)
        vals: dict = {}
        if os.path.exists(path):
            for line in open(path):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
        get = lambda k: os.environ.get(k) or vals.get(k)  # noqa: E731
        return Secrets(wallet_key=get("DESK_WALLET_KEY"), rpc_url=get("DESK_RPC_URL"),
                       agent_key=get("DESK_AGENT_KEY"), account=get("DESK_ACCOUNT"),
                       git_remote=get("DESK_GIT_REMOTE"),
                       testnet=str(get("DESK_TESTNET") or "").lower() in ("1", "true", "yes"))
