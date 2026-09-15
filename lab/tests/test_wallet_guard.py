"""Wallet security guard.

The site's wallet integration is read-only by construction: it may ask a
wallet for a public address and for a *message* signature, and nothing else.
A site that can request a transaction signature can, if compromised, drain a
wallet. This test scans every shipped front-end source and fails if any
transaction-signing or fund-moving method name appears — so the guarantee on
the public page ("this site never requests a transaction signature") is
enforced by the build, not by a promise.

If you are reading this because the test failed: do not add the method to the
allow-list. Remove the call. Read-only is the product.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCAN_DIRS = ["site", os.path.join("genius-web", "src"), os.path.join("genius-web", "public")]
SCAN_EXT = (".js", ".ts", ".tsx", ".html", ".mjs")

# EVM + Solana method names that can move funds or grant spending permission.
# Allowed on purpose: eth_accounts / eth_requestAccounts (read the public address),
# personal_sign (a human-readable message, cannot authorise anything on chain),
# wallet_switchEthereumChain / wallet_addEthereumChain (a wallet setting).
FORBIDDEN = [
    r"eth_sendTransaction", r"eth_signTransaction", r"eth_sendRawTransaction", r"eth_sign\b",
    r"eth_signTypedData", r"signTypedData", r"wallet_requestPermissions", r"wallet_sendCalls",
    r"\.approve\(", r"setApprovalForAll", r"permit\(", r"increaseAllowance", r"0x095ea7b3",
    r"signTransaction", r"signAllTransactions", r"signAndSendTransaction",
    r"sendTransaction", r"signAndSendAllTransactions",
    r"solana:signTransaction", r"solana:signAndSendTransaction",
    r"SystemProgram\.transfer", r"createTransferInstruction", r"Transaction\(",
    r"VersionedTransaction",
]
# Things the site must never even mention as an input.
FORBIDDEN_INPUTS = [
    r"seed\s*phrase\s*:?\s*<input", r"private\s*key\s*:?\s*<input",
    r"mnemonic", r"secretKey", r"privateKey", r"fromSecretKey", r"Keypair\.",
]


def _sources():
    for d in SCAN_DIRS:
        base = os.path.join(ROOT, d)
        for dirpath, dirnames, files in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in ("node_modules", "dist")]
            for f in files:
                if f.endswith(SCAN_EXT) and f != "data.js":
                    yield os.path.join(dirpath, f)


class WalletIsReadOnly(unittest.TestCase):
    def test_sources_exist(self):
        files = list(_sources())
        self.assertTrue(any(f.endswith("wallet.js") for f in files), "site/wallet.js missing")

    def test_no_transaction_signing_anywhere(self):
        hits = []
        for path in _sources():
            text = open(path, encoding="utf-8", errors="replace").read()
            for pat in FORBIDDEN:
                for m in re.finditer(pat, text):
                    line = text.count("\n", 0, m.start()) + 1
                    hits.append(f"{os.path.relpath(path, ROOT)}:{line}: {m.group(0)}")
        self.assertEqual(hits, [], "transaction-capable code found:\n" + "\n".join(hits))

    def test_no_key_material_handling(self):
        hits = []
        for path in _sources():
            text = open(path, encoding="utf-8", errors="replace").read()
            for pat in FORBIDDEN_INPUTS:
                for m in re.finditer(pat, text, flags=re.I):
                    line = text.count("\n", 0, m.start()) + 1
                    hits.append(f"{os.path.relpath(path, ROOT)}:{line}: {m.group(0)}")
        self.assertEqual(hits, [], "key-material handling found:\n" + "\n".join(hits))

    def test_only_message_signing_is_used(self):
        """Positive check: the one signing call present is personal_sign (a
        readable message), the only account call is eth_requestAccounts, and
        every RPC read goes to the chain's public endpoint."""
        js = open(os.path.join(ROOT, "site", "wallet.js"), encoding="utf-8").read()
        self.assertIn("personal_sign", js)
        self.assertIn("eth_requestAccounts", js)
        self.assertIn("eip6963:announceProvider", js)
        wallet_methods = set(re.findall(r"request\(\{ method: '([a-zA-Z_]+)'", js))
        self.assertEqual(wallet_methods, {"eth_accounts", "eth_requestAccounts", "eth_chainId", "personal_sign",
                                          "wallet_switchEthereumChain", "wallet_addEthereumChain"},
                         f"unexpected wallet methods: {wallet_methods}")
        rpc_methods = set(re.findall(r"rpc\('([a-zA-Z_]+)'", js))
        self.assertEqual(rpc_methods, {"eth_getBalance", "eth_call"}, f"unexpected RPC reads: {rpc_methods}")

    def test_csp_only_reaches_the_chain_rpc(self):
        h = open(os.path.join(ROOT, "site", "_headers"), encoding="utf-8").read()
        m = re.search(r"connect-src ([^;]+);", h)
        self.assertEqual(m.group(1).split(), ["'self'", "https://rpc.mainnet.chain.robinhood.com"])

    def test_csp_forbids_inline_scripts(self):
        h = open(os.path.join(ROOT, "site", "_headers"), encoding="utf-8").read()
        m = re.search(r"script-src ([^;]+);", h)
        self.assertIsNotNone(m)
        self.assertNotIn("unsafe-inline", m.group(1))
        self.assertNotIn("unsafe-eval", m.group(1))
        self.assertIn("frame-ancestors 'none'", h)

    def test_no_inline_scripts_in_pages(self):
        for name in ("index.html", os.path.join("console", "index.html")):
            html = open(os.path.join(ROOT, "site", name), encoding="utf-8").read()
            self.assertFalse(re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html),
                             f"{name} has an inline <script> — the CSP would block it")
            self.assertFalse(re.search(r"\son\w+\s*=", html),
                             f"{name} has an inline event handler — the CSP would block it")


if __name__ == "__main__":
    unittest.main()
