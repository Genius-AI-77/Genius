#!/usr/bin/env python3
"""Publish the GENIUS contract address to the site.

    python3 desk/set_ca.py <CONTRACT_ADDRESS>     validate on chain, write, commit, push
    python3 desk/set_ca.py <CONTRACT_ADDRESS> --dry   validate + write only, no git
    python3 desk/set_ca.py --clear                 blank it again
    python3 desk/set_ca.py --fee-wallet 0x...      publish the wallet that receives the fees
    python3 desk/set_ca.py --desk-wallet <sol>     publish the Solana wallet the desk trades from

Validation: the address must be a 0x address AND be a deployed contract on
Robinhood Chain (chain id 4663) that answers symbol(), decimals() and
totalSupply() like an ERC-20. A typo, a wallet address, a contract on another
chain, or a non-token contract is refused; nothing is written.
"""
import json, os, re, ssl, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["site/ca.js", "genius-web/public/ca.js"]
RPC = os.environ.get("GENIUS_CHAIN_RPC", "https://rpc.mainnet.chain.robinhood.com")
CHAIN_ID = 4663
SELECTORS = {"symbol": "0x95d89b41", "decimals": "0x313ce567", "totalSupply": "0x18160ddd", "name": "0x06fdde03"}


def _ssl_ctx():
    """python.org builds on macOS ship without a CA bundle wired up; use certifi
    if present, else the system bundle."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        for p in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
            if os.path.exists(p):
                return ssl.create_default_context(cafile=p)
        return ssl.create_default_context()


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, body, {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()))
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["result"]


def _abi_string(hexdata):
    raw = bytes.fromhex(hexdata[2:])
    if len(raw) >= 64:                      # dynamic string: offset, length, bytes
        n = int.from_bytes(raw[32:64], "big")
        return raw[64:64 + n].decode("utf-8", "replace")
    return raw.rstrip(b"\0").decode("utf-8", "replace")   # bytes32 style


def on_chain_token(addr):
    if int(rpc("eth_chainId", []), 16) != CHAIN_ID:
        return None, f"RPC is not Robinhood Chain (expected chain id {CHAIN_ID})"
    code = rpc("eth_getCode", [addr, "latest"])
    if code in ("0x", "0x0", None):
        return None, "no contract at that address on Robinhood Chain (a wallet, a typo, or another chain)"
    info = {}
    for name, sel in SELECTORS.items():
        try:
            out = rpc("eth_call", [{"to": addr, "data": sel}, "latest"])
        except Exception as e:
            return None, f"contract does not answer {name}(): {e}"
        if out in ("0x", None):
            return None, f"contract does not answer {name}(), so it is not an ERC-20 token"
        info[name] = _abi_string(out) if name in ("symbol", "name") else int(out, 16)
    return info, None


def write(ca, key="ca"):
    for f in FILES:
        p = os.path.join(ROOT, f)
        s = open(p).read()
        s2, n = re.subn(rf'{key}:\s*"[^"]*"', f'{key}: "{ca}"', s, count=1)
        assert n == 1, f"{key} field not found in {f}"
        open(p, "w").write(s2)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    key = "ca"
    if "--fee-wallet" in sys.argv:
        key, ca = "feeWallet", (args[0].strip() if args else "")
        if ca and not re.fullmatch(r"0x[0-9a-fA-F]{40}", ca):
            print(f"REFUSED: '{ca}' is not a 0x address"); return 1
        msg = "site: publish fee wallet"
    elif "--desk-wallet" in sys.argv:
        key, ca = "deskWallet", (args[0].strip() if args else "")
        if ca and not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", ca):
            print(f"REFUSED: '{ca}' is not a Solana address"); return 1
        msg = "site: publish desk wallet"
    elif "--clear" in sys.argv:
        ca, msg = "", "site: clear contract address"
    else:
        if len(args) != 1:
            print(__doc__); return 2
        ca = args[0].strip()
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", ca):
            print(f"REFUSED: '{ca}' is not a 0x contract address"); return 1
        info, err = on_chain_token(ca)
        if err:
            print(f"REFUSED: {err}"); return 1
        supply = info["totalSupply"] / 10 ** info["decimals"]
        print(f"token OK  name={info['name']!r}  symbol={info['symbol']!r}  decimals={info['decimals']}  supply={supply:,.0f}")
        print(f"explorer: https://robinhoodchain.blockscout.com/token/{ca}")
        msg = "site: publish GENIUS contract address"
    write(ca, key)
    print(f"written {key}:", ", ".join(FILES))
    if dry:
        return 0
    remote = ""
    for p in (os.environ.get("DESK_SECRETS_FILE", os.path.expanduser("~/.genius-desk/secrets.env")),):
        if os.path.exists(p):
            for line in open(p):
                if line.startswith("DESK_GIT_REMOTE="):
                    remote = line.split("=", 1)[1].strip()
    if not remote:
        print("no DESK_GIT_REMOTE in secrets file; files written but not pushed"); return 1
    env = dict(os.environ, GIT_AUTHOR_NAME="genius-desk[bot]", GIT_COMMITTER_NAME="genius-desk[bot]",
               GIT_AUTHOR_EMAIL="genius-desk[bot]@users.noreply.github.com",
               GIT_COMMITTER_EMAIL="genius-desk[bot]@users.noreply.github.com")
    subprocess.run(["git", "add", *FILES], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=ROOT, check=True, env=env)
    subprocess.run(["git", "fetch", "-q", remote, "main"], cwd=ROOT, check=True, capture_output=True)
    subprocess.run(["git", "rebase", "-q", "FETCH_HEAD"], cwd=ROOT, check=True, env=env, capture_output=True)
    r = subprocess.run(["git", "push", "-q", remote, "HEAD:main"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        print("push failed:", re.sub(r"x-access-token:[^@]*@", "***@", r.stderr)); return 1
    print("pushed. Netlify redeploys in about a minute: https://geniusai77.xyz/#top")
    return 0


if __name__ == "__main__":
    sys.exit(main())
