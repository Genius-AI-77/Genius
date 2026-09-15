/**
 * Wallet connect for Robinhood Chain — READ-ONLY BY CONSTRUCTION.
 *
 * Can: discover browser wallets (EIP-6963 + window.ethereum fallback), read
 * the public address (eth_requestAccounts), offer a network switch (a wallet
 * setting), request a *message* signature the user sees in full (ownership
 * proof — costs nothing, moves nothing), read ETH and GENIUS balances from
 * the chain's public RPC.
 *
 * Cannot, and no edit may add: request a transaction signature of any kind,
 * or a typed-data signature (permits). The site therefore has no way to move
 * funds or approve transfers. A test in the parent repo
 * (lab/tests/test_wallet_guard.py) fails the build if such method names
 * appear in this folder.
 *
 * No backend. Only the last-used wallet *name* is persisted, for silent
 * reconnect. Private keys never exist anywhere in this code path.
 */

export const CHAIN_ID = 4663;
const CHAIN_HEX = "0x1237";
export const RPC = "https://rpc.mainnet.chain.robinhood.com";
export const EXPLORER = "https://robinhoodchain.blockscout.com";
const LS_KEY = "genius.wallet.name";

type Provider = {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: string, cb: (...a: any[]) => void): void;
  isMetaMask?: boolean; isRabby?: boolean; isRobinhood?: boolean;
};

export type Connected = { address: string; chainId: number | null };

export type Adapter = {
  name: string;
  icon: string;
  connect(silent: boolean): Promise<Connected>;
  signMessage(address: string, text: string): Promise<string>;
  switchChain(): Promise<number | null>;
  disconnect(): Promise<void>;
  onChange(cb: (accounts?: string[]) => void): void;
};

const registry = new Map<string, Adapter>();
const listeners = new Set<() => void>();
function notify() { listeners.forEach((l) => l()); }

export function onWalletsChange(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
export function wallets(): Adapter[] { return [...registry.values()]; }

const toHex = (s: string) => "0x" + Array.from(new TextEncoder().encode(s), (b) => b.toString(16).padStart(2, "0")).join("");

function adapt(name: string, icon: string, p: Provider): Adapter {
  return {
    name, icon,
    async connect(silent) {
      const accounts = (await p.request({ method: silent ? "eth_accounts" : "eth_requestAccounts" })) as string[];
      if (!accounts?.length) throw new Error(silent ? "not connected" : "No account returned");
      let chainId: number | null = null;
      try { chainId = parseInt((await p.request({ method: "eth_chainId" })) as string, 16); } catch { /* optional */ }
      return { address: accounts[0], chainId };
    },
    async signMessage(address, text) {
      return (await p.request({ method: "personal_sign", params: [toHex(text), address] })) as string;
    },
    async switchChain() {
      try {
        await p.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_HEX }] });
      } catch (e: any) {
        if (e?.code === 4902 || /unrecognized|not added|4902/i.test(e?.message ?? "")) {
          await p.request({ method: "wallet_addEthereumChain", params: [{
            chainId: CHAIN_HEX, chainName: "Robinhood Chain", rpcUrls: [RPC],
            nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 }, blockExplorerUrls: [EXPLORER] }] });
        } else throw e;
      }
      try { return parseInt((await p.request({ method: "eth_chainId" })) as string, 16); } catch { return null; }
    },
    async disconnect() { /* EVM wallets have no disconnect call; we just forget the session */ },
    onChange(cb) {
      try {
        p.on?.("accountsChanged", (a: string[]) => cb(a));
        p.on?.("chainChanged", () => cb());
        p.on?.("disconnect", () => cb([]));
      } catch { /* provider without events */ }
    },
  };
}

let listening = false;
export function discover() {
  if (typeof window === "undefined") return;
  if (!listening) {
    listening = true;
    window.addEventListener("eip6963:announceProvider", (ev: Event) => {
      const d = (ev as CustomEvent).detail ?? {};
      if (!d.provider || !d.info?.name) return;
      registry.set(d.info.name, adapt(d.info.name, d.info.icon ?? "", d.provider));
      notify();
    });
  }
  try { window.dispatchEvent(new Event("eip6963:requestProvider")); } catch { /* ignore */ }
  const eth = (window as any).ethereum as Provider | undefined;
  if (eth && registry.size === 0) {
    const name = eth.isRabby ? "Rabby" : eth.isRobinhood ? "Robinhood Wallet" : eth.isMetaMask ? "MetaMask" : "Browser wallet";
    registry.set(name, adapt(name, "", eth));
    notify();
  }
}

export const short = (a: string) => (a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "");

function nonce() {
  const b = new Uint8Array(16); crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

export function ownershipMessage(address: string) {
  return `GENIUS wants you to prove you control this address on Robinhood Chain:\n${address}\n\n` +
    "This signature proves ownership only. It costs nothing, moves nothing, and grants this site no permissions.\n\n" +
    `Domain: ${location.host}\nNonce: ${nonce()}\nIssued At: ${new Date().toISOString()}`;
}

/** A well-formed secp256k1 signature came back from the wallet, which only signs
 * for keys it holds. Browsers have no native secp256k1 recovery, so this is a
 * shape check, honestly labelled "Signed" in the UI rather than "Verified". */
export const looksSigned = (sig: string) => /^0x[0-9a-fA-F]{130}$/.test(sig);

async function rpc(method: string, params: unknown[]): Promise<any> {
  const r = await fetch(RPC, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message ?? "rpc error");
  return j.result;
}

export async function fetchBalance(address: string): Promise<number | null> {
  try { return parseInt(await rpc("eth_getBalance", [address, "latest"]), 16) / 1e18; } catch { return null; }
}

const pad = (x: string) => x.replace(/^0x/, "").toLowerCase().padStart(64, "0");

export async function fetchTokenBalance(address: string, ca: string): Promise<number | null> {
  try {
    const [bal, dec] = await Promise.all([
      rpc("eth_call", [{ to: ca, data: "0x70a08231" + pad(address) }, "latest"]),
      rpc("eth_call", [{ to: ca, data: "0x313ce567" }, "latest"]),
    ]);
    const d = parseInt(dec, 16) || 18;
    return Number((BigInt(bal) * 1000000n) / 10n ** BigInt(d)) / 1e6;
  } catch { return null; }
}

export const prefs = {
  get: () => { try { return localStorage.getItem(LS_KEY); } catch { return null; } },
  set: (n: string) => { try { localStorage.setItem(LS_KEY, n); } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(LS_KEY); } catch { /* ignore */ } },
};
