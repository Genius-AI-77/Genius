#!/usr/bin/env python3
"""Publish the $GENIUS contract address to the site.

    python3 desk/set_ca.py <MINT_ADDRESS>          validate on chain, write, commit, push
    python3 desk/set_ca.py <MINT_ADDRESS> --dry    validate + write only, no git
    python3 desk/set_ca.py --clear                 blank it again

Validation: the address must decode as a 32-byte base58 key AND exist on
mainnet as an SPL token mint (owner = Token or Token-2022 program). A typo,
a wallet address or a mint that is not on chain is refused; nothing is written.
"""
import json, os, re, ssl, subprocess, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["site/ca.js", "genius-web/public/ca.js"]
RPC = os.environ.get("DESK_RPC_URL", "https://api.mainnet-beta.solana.com")
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnwqTfR3jsNPGA"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58_len(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return len(raw) + (len(s) - len(s.lstrip("1")))


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


def on_chain_mint(addr):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                       "params": [addr, {"encoding": "jsonParsed"}]}).encode()
    req = urllib.request.Request(RPC, body, {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()))
    v = (r.get("result") or {}).get("value")
    if not v:
        return None, "no account at that address on mainnet"
    if v["owner"] not in (TOKEN, TOKEN_2022):
        return None, f"account exists but is not an SPL token (owner {v['owner'][:8]}...)"
    parsed = v.get("data", {}).get("parsed", {})
    if parsed.get("type") != "mint":
        return None, f"token account but not a mint (type {parsed.get('type')})"
    return parsed.get("info", {}), None


def write(ca):
    for f in FILES:
        p = os.path.join(ROOT, f)
        s = open(p).read()
        s2 = re.sub(r'ca:\s*"[^"]*"', f'ca: "{ca}"', s, count=1)
        assert s2 != s or ca == "" or f'ca: "{ca}"' in s, f"pattern not found in {f}"
        open(p, "w").write(s2)


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if "--clear" in sys.argv:
        ca, msg = "", "site: clear contract address"
    else:
        if len(args) != 1:
            print(__doc__); return 2
        ca = args[0].strip()
        if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", ca) or b58_len(ca) != 32:
            print(f"REFUSED: '{ca}' is not a valid Solana address"); return 1
        info, err = on_chain_mint(ca)
        if err:
            print(f"REFUSED: {err}"); return 1
        print(f"mint OK  decimals={info.get('decimals')}  supply={info.get('supply')}  "
              f"mintAuthority={info.get('mintAuthority')}  freezeAuthority={info.get('freezeAuthority')}")
        msg = "site: publish $GENIUS contract address"
    write(ca)
    print("written:", ", ".join(FILES))
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
