# Wallet Connect — Security Model

The site lets a visitor connect a Solana wallet. This document states exactly what that
can and cannot do, and how the "cannot" part is enforced rather than promised.

## The one idea that matters

**A wallet connection never involves private keys.** Ever. Not on this site, not on any
correctly built site. The private key lives inside the wallet extension (Phantom,
Solflare, Backpack). A website can only *ask the wallet* for two things:

1. **"What is your public address?"** — public by definition; it is what people send
   funds *to*.
2. **"Please sign this."** — and here is the entire security question of web3 in one
   line: *sign what?*

A **message** signature proves you hold the key. It moves nothing, costs nothing, and grants
nothing. A **transaction** signature moves funds or grants spending permission. Every
"wallet drainer" scam is a site that shows a friendly button and asks for a transaction
signature underneath it.

**GENIUS only ever asks for message signatures.** There is no code that can request a
transaction signature, and a build test makes sure it stays that way.

## What the site can do

| Action | How | What the user sees |
|---|---|---|
| Discover installed wallets | Wallet Standard handshake (`wallet-standard:app-ready` / `register-wallet`), legacy `window.solana` fallback | A list of wallet names |
| Connect | `standard:connect` → public address | The wallet's own connect prompt |
| Show SOL balance | JSON-RPC `getBalance` to a public mainnet endpoint | A number |
| Prove ownership | `solana:signMessage` on a human-readable, domain-bound, single-use message | The wallet displays the **full message text** before signing |
| Verify the signature | Ed25519 via WebCrypto, in the browser | "Verified ✓" (or "browser cannot verify" on old browsers) |
| Silent reconnect | `connect({silent:true})` for the last-used wallet | Nothing — never prompts |
| Disconnect | `standard:disconnect` | — |

The ownership message reads, in full:

```
GENIUS wants you to prove you control this Solana address:
<address>

This signature proves ownership only. It costs nothing, moves nothing,
and grants this site no permissions.

Domain: <the site's host>
Nonce: <random, single use>
Issued At: <timestamp>
```

Domain-binding and the nonce mean a captured signature cannot be replayed on another site
or at another time. It is the Sign-In-With-Solana shape, kept plain so a person can read it.

## What the site cannot do — and how that is enforced

`lab/tests/test_wallet_guard.py` scans every shipped front-end source
(`site/`, `genius-web/src`, `genius-web/public`) and **fails the build** if any of these
appear:

- Solana: `signTransaction`, `signAllTransactions`, `signAndSendTransaction`,
  `sendTransaction`, `solana:signTransaction`, `SystemProgram.transfer`,
  `createTransferInstruction`, `Transaction(`, `VersionedTransaction`
- EVM (in case anyone ever adds it): `eth_sendTransaction`, `eth_signTransaction`,
  `eth_sign`, `personal_sign`, `eth_requestAccounts`, `.approve(`, `setApprovalForAll`,
  `permit(`, `increaseAllowance`
- Key material: `privateKey`, `secretKey`, `mnemonic`, `Keypair.`, `fromSecretKey`,
  any seed-phrase or private-key input field

It also asserts the positive case (the one signing feature used is `solana:signMessage`),
that the CSP forbids inline scripts, and that the pages contain none.

The test runs in the daily GitHub Action before the live run. A pull request that adds
transaction capability cannot go green.

**If that test ever fails, the fix is to remove the code, not to edit the test.**

## Browser hardening

`site/_headers` (honoured by Netlify and Cloudflare Pages; `serve.py` sends the same
headers locally so violations surface before deploy):

| Header | Value | Why |
|---|---|---|
| `Content-Security-Policy` | `script-src 'self'` — **no inline scripts, no eval, no third-party script hosts** | An injected script is the usual way a drainer gets onto a legitimate site. With this policy the browser refuses to run one. |
| | `connect-src 'self' https://api.mainnet-beta.solana.com` | The page can only talk to itself and the RPC |
| | `frame-ancestors 'none'` + `X-Frame-Options: DENY` | Cannot be embedded in another site (clickjacking) |
| | `object-src 'none'`, `base-uri 'self'`, `form-action 'self'` | Closes the remaining injection vectors |
| `X-Content-Type-Options` | `nosniff` | |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | |
| `Permissions-Policy` | camera, mic, geolocation, payment off | |

All page behaviour lives in external files (`app.js`, `wallet.js`, `console/app.js`) so the
strict script policy holds. Google Fonts is the only third-party origin, and it is allowed
for stylesheets and fonts only — not scripts.

## What is stored

| Where | What | Why |
|---|---|---|
| `localStorage` | The **name** of the last-used wallet (e.g. `"Phantom"`) | Silent reconnect on the next visit |
| Anywhere else | **Nothing** | There is no backend. Addresses, balances and signatures are displayed and discarded. |

## Honest limitations

- **Not yet exercised against a real wallet extension in this environment.** The flow is
  written to the Wallet Standard specification and the legacy Phantom API, and its
  structure is tested, but the automated browser here has no wallet installed. The first
  real test is: deploy, open with Phantom installed, connect, prove ownership. If a wallet
  misbehaves the panel shows the wallet's own error text.
- **The public RPC is rate-limited.** If `getBalance` fails the panel shows "…" rather than
  a wrong number. Swap `RPC` in `wallet.js` / `lib/wallet.ts` for a dedicated endpoint
  when there is traffic.
- **Ed25519 in WebCrypto** needs Chrome 113+, Safari 17+, Firefox 130+. Older browsers
  still sign; they just cannot verify locally, and the panel says so.
- **Solana only.** EVM support is not built. If added, the guard test's EVM list already
  covers the dangerous methods.
- **A wallet connection is not identity.** Proving control of an address proves control
  of an address. It says nothing about who the person is, and this site does not pretend
  otherwise.

## The user-facing promise, verbatim from the panel

> We never ask for a seed phrase or private key. Nobody legitimate does.
> This site never requests a transaction signature, so it cannot move funds or approve
> transfers. That rule is enforced by a test in the codebase.
> Only your public address is read. There is no server; nothing is stored anywhere but
> your browser.
> There is nothing to claim, buy or mint. If a page that looks like this one asks you to,
> it is not us.

That last line is the one that will matter most. The moment $GENIUS exists, clones of
this page will appear with a "claim" button. The defence is that the real page has said,
from day one, that it will never have one.
