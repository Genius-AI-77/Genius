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

# Solana + EVM method names that can move funds or grant spending permission.
FORBIDDEN = [
    r"signTransaction", r"signAllTransactions", r"signAndSendTransaction",
    r"sendTransaction", r"signAndSendAllTransactions",
    r"solana:signTransaction", r"solana:signAndSendTransaction",
    r"eth_sendTransaction", r"eth_signTransaction", r"eth_sign\b",
    r"personal_sign", r"wallet_requestPermissions", r"eth_requestAccounts",
    r"\.approve\(", r"setApprovalForAll", r"permit\(", r"increaseAllowance",
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
        """Positive check: the one signing call present is message signing."""
        js = open(os.path.join(ROOT, "site", "wallet.js"), encoding="utf-8").read()
        self.assertIn("solana:signMessage", js)
        self.assertIn("standard:connect", js)

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
