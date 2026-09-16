# Wallet Connect: Security Model

The site lets a visitor connect a wallet on Robinhood Chain. This document states exactly
what that can and cannot do, and how the "cannot" part is enforced rather than promised.

## The one idea that matters

**A wallet connection never involves private keys.** Ever. Not on this site, not on any
correctly built site. The private key lives inside the wallet (MetaMask, Rabby, the Robinhood
Wallet, a hardware wallet behind them). A website can only *ask the wallet* for two things:

1. **"What is your public address?"** Public by definition; it is what people send funds *to*.
2. **"Please sign this."** And here is the entire security question of web3 in one line:
   *sign what?*

A **message** signature proves you hold the key. It moves nothing, costs nothing, and grants
nothing. A **transaction** signature moves funds. A **typed-data** signature can grant a
spending allowance (a "permit"). Every wallet-drainer scam is a site that shows a friendly
button and asks for one of those two underneath it.

**GENIUS only ever asks for a plain message signature.** There is no code that can request a
transaction or a typed-data signature, and a build test makes sure it stays that way.

## What the site can do

| Action | How | What the user sees |
|---|---|---|
| Discover installed wallets | EIP-6963 provider announcements, `window.ethereum` fallback | A list of wallet names |
| Connect | `eth_requestAccounts`, then `eth_chainId` | The wallet's own connect prompt |
| Silent reconnect | `eth_accounts` for the wallet used last time | Nothing; it never prompts |
| Offer a network switch | `wallet_switchEthereumChain`, falling back to `wallet_addEthereumChain` with the public RPC and explorer | The wallet's own network prompt; a setting changes, nothing moves |
| Read balances | `eth_getBalance` and an ERC-20 `balanceOf` through `eth_call`, sent to the chain's public RPC, not through the wallet | ETH and GENIUS balances in the panel |
| Prove ownership | `personal_sign` on a human-readable, domain-bound, single-use message | The wallet displays the full text before signing |

The ownership message:

```
GENIUS wants you to prove you control this address on Robinhood Chain:
0x...

This signature proves ownership only. It costs nothing, moves nothing, and grants this site no permissions.

Domain: geniusai77.xyz
Nonce: <16 random bytes>
Issued At: <timestamp>
```

The domain and nonce make the signature useless anywhere else or at another time. It is the
Sign-In-With-Ethereum shape, kept plain so a person can read it.

## What the site cannot do, and how that is enforced

`lab/tests/test_wallet_guard.py` scans every `.js`, `.ts`, `.tsx`, `.html` and `.mjs` file
under `site/`, `genius-web/src/` and `genius-web/public/` and fails if any of these appear:

- EVM: `eth_sendTransaction`, `eth_signTransaction`, `eth_sendRawTransaction`, `eth_sign`,
  `eth_signTypedData` in any version, `wallet_requestPermissions`, `wallet_sendCalls`,
  `.approve(`, `setApprovalForAll`, `permit(`, `increaseAllowance`, the `approve` selector
- Solana (kept so the rule survives a chain change): `signTransaction`,
  `signAllTransactions`, `signAndSendTransaction`, `sendTransaction`,
  `SystemProgram.transfer`, `Transaction(`, `VersionedTransaction`
- Key material of any kind: `privateKey`, `secretKey`, `mnemonic`, `Keypair.`, or an input
  field labelled seed phrase or private key

It also asserts the positive case: the wallet calls present in `site/wallet.js` are exactly
`eth_accounts`, `eth_requestAccounts`, `eth_chainId`, `personal_sign`,
`wallet_switchEthereumChain` and `wallet_addEthereumChain`, and the RPC reads are exactly
`eth_getBalance` and `eth_call`. Anything added to that list fails the build.

## Browser hardening

`site/_headers` (served by Netlify; mirrored in `netlify.toml` and `vercel.json`):

| Header | Value | Effect |
|---|---|---|
| `Content-Security-Policy` | `script-src 'self'` | Only this site's own script files run; no inline scripts, no third-party scripts |
| | `connect-src 'self' https://rpc.mainnet.chain.robinhood.com` | The page can only talk to itself and the chain's RPC |
| | `frame-ancestors 'none'` | Cannot be embedded in another site (clickjacking) |
| | `form-action 'self'`, `base-uri 'self'`, `object-src 'none'` | No form exfiltration, no base-tag hijack, no plugins |
| `X-Frame-Options` | `DENY` | Same as above for older browsers |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Outbound links do not leak the page URL |
| `Permissions-Policy` | camera, microphone, geolocation, payment all off | |

Because there are no inline scripts, a copy of the page with an injected `<script>` will not
run it in a compliant browser.

## What is stored

| Where | What | Why |
|---|---|---|
| `localStorage` | The **name** of the last-used wallet (e.g. `"MetaMask"`) | Silent reconnect on the next visit |
| Anywhere else | **Nothing** | There is no backend. Addresses, balances and signatures are displayed and discarded. |

## Honest limitations

- **Signature verification.** Browsers have no native secp256k1 recovery, so the panel does not
  recompute the signer. A wallet only signs for keys it holds, and it shows the text first, so
  the panel says **Signed**, not Verified. A server-side check would add nothing the wallet has
  not already proven to the person holding it.
- **The public RPC is rate-limited.** If a balance read fails the panel shows "…" rather than a
  wrong number. Swap `RPC` in `wallet.js` / `lib/wallet.ts` for a dedicated endpoint when there
  is traffic.
- **Exercised against a simulated provider, and against the real chain for reads.** The flow
  was driven end to end in a browser with a fake EIP-6963 wallet on the wrong network: connect,
  network warning, switch, balance from the real RPC, sign. The remaining test is a real
  extension, which behaves the same by specification; if one misbehaves the panel shows the
  wallet's own error text.
- **A wallet connection is not identity.** Proving control of an address proves control of an
  address. It says nothing about who the person is, and this site does not pretend otherwise.

## The user-facing promise, verbatim from the panel

> We never ask for a seed phrase or private key. Nobody legitimate does.
> This site never requests a transaction signature, so it cannot move funds or approve
> transfers. That rule is enforced by a test in the codebase.
> Only your public address is read. There is no server; nothing is stored anywhere but
> your browser.
> This site will never ask you to claim, buy or mint anything. If a page that looks like
> this one does, it is not us.
