/* GENIUS token contract. Empty until the token exists; the site hides every
   token element while `ca` is blank. Set once, at the drop, and push.
   feeWallet: 0x address on Robinhood Chain that receives the trade fees.
   deskWallet: Solana address the agents trade from (HERMES signs with it). */
window.GENIUS_TOKEN = {
  chain: "robinhood",
  chainName: "Robinhood Chain",
  chainId: 4663,
  explorer: "https://robinhoodchain.blockscout.com",
  ca: "",
  feeWallet: "",
  deskWallet: ""
};
