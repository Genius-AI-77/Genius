/* GENIUS token contract. Empty until the token exists; the site hides every
   token element while `ca` is blank. Set once, at the drop, and push.
   feeWallet: the agents' 0x wallet on Robinhood Chain. It receives the trade
   fees and the desk trades from it (HERMES signs with it). */
window.GENIUS_TOKEN = {
  chain: "robinhood",
  chainName: "Robinhood Chain",
  chainId: 4663,
  explorer: "https://robinhoodchain.blockscout.com",
  ca: "",
  feeWallet: ""
};
