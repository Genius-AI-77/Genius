/**
 * Solana wallet connect — READ-ONLY BY CONSTRUCTION.
 *
 * Can: discover wallets (Wallet Standard + legacy fallback), read the public
 * address, request a *message* signature the user sees in full (ownership
 * proof — costs nothing, moves nothing), read SOL balance from a public RPC.
 *
 * Cannot, and no edit may add: request a transaction signature of any kind.
 * The site therefore has no way to move funds or approve transfers. A test in
 * the parent repo (lab/tests/test_wallet_guard.py) fails the build if
 * transaction-signing method names appear in this folder.
 *
 * No backend. Only the last-used wallet *name* is persisted, for silent
 * reconnect. Private keys never exist anywhere in this code path.
 */

export const RPC = "https://api.mainnet-beta.solana.com";
const LS_KEY = "genius.wallet.name";
const CHAIN = "solana:mainnet";

export type Connected = { account: unknown; address: string; pubkey: Uint8Array };

export type Adapter = {
  name: string;
  icon: string;
  connect(silent: boolean): Promise<Connected>;
  signMessage(account: unknown, bytes: Uint8Array): Promise<Uint8Array>;
  disconnect(): Promise<void>;
  onChange(cb: () => void): void;
};

type StdAccount = { address: string; publicKey: Uint8Array; chains?: string[] };
type StdWallet = {
  name: string;
  icon?: string;
  chains: string[];
  features: Record<string, any>;
};

const registry = new Map<string, Adapter>();
const listeners = new Set<() => void>();
function notify() { listeners.forEach((l) => l()); }

export function onWalletsChange(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
export function wallets(): Adapter[] { return [...registry.values()]; }

function adaptStandard(w: StdWallet): Adapter | null {
  if (!w?.chains?.some((c) => String(c).startsWith("solana:"))) return null;
  if (!w.features?.["standard:connect"]) return null;
  return {
    name: w.name,
    icon: w.icon ?? "",
    async connect(silent) {
      const r = await w.features["standard:connect"].connect(silent ? { silent: true } : undefined);
      const accs: StdAccount[] = r.accounts ?? [];
      const acc = accs.find((a) => !a.chains || a.chains.includes(CHAIN)) ?? accs[0];
      if (!acc) throw new Error("No Solana account returned");
      return { account: acc, address: acc.address, pubkey: new Uint8Array(acc.publicKey) };
    },
    async signMessage(account, bytes) {
      const f = w.features["solana:signMessage"];
      if (!f) throw new Error("Wallet cannot sign messages");
      const out = await f.signMessage({ account, message: bytes });
      const o = Array.isArray(out) ? out[0] : out;
      return new Uint8Array(o.signature);
    },
    async disconnect() {
      const f = w.features["standard:disconnect"];
      if (f) await f.disconnect();
    },
    onChange(cb) { w.features["standard:events"]?.on("change", cb); },
  };
}

function register(...ws: StdWallet[]) {
  for (const w of ws) {
    try {
      const a = adaptStandard(w);
      if (a) registry.set(a.name, a);
    } catch { /* a broken wallet must not break the page */ }
  }
  notify();
}

let discovered = false;
export function discover() {
  if (discovered || typeof window === "undefined") return;
  discovered = true;
  window.addEventListener("wallet-standard:register-wallet", (ev: Event) => {
    try { (ev as CustomEvent).detail({ register }); } catch { /* ignore */ }
  });
  try {
    window.dispatchEvent(new CustomEvent("wallet-standard:app-ready", { detail: { register } }));
  } catch { /* ignore */ }
  registerLegacy();
}

function registerLegacy() {
  if (registry.size) return;
  const w = window as any;
  const p = w.phantom?.solana ?? w.solana;
  if (!p || typeof p.connect !== "function") return;
  registry.set("Phantom", {
    name: "Phantom",
    icon: "",
    async connect(silent) {
      const r = await p.connect(silent ? { onlyIfTrusted: true } : undefined);
      const pk = r?.publicKey ?? p.publicKey;
      return { account: null, address: pk.toString(), pubkey: new Uint8Array(pk.toBytes()) };
    },
    async signMessage(_a, bytes) {
      const r = await p.signMessage(bytes, "utf8");
      return new Uint8Array(r.signature);
    },
    async disconnect() { await p.disconnect(); },
    onChange(cb) { try { p.on("accountChanged", cb); p.on("disconnect", cb); } catch { /* ignore */ } },
  });
  notify();
}

/* ------------------------------------------------------------- helpers */

export const short = (a: string) => (a ? `${a.slice(0, 4)}…${a.slice(-4)}` : "");

function nonce() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

/** Shown to the user in full by the wallet. Domain-bound and single-use. */
export function ownershipMessage(address: string) {
  return (
    `GENIUS wants you to prove you control this Solana address:\n${address}\n\n` +
    `This signature proves ownership only. It costs nothing, moves nothing, and grants this site no permissions.\n\n` +
    `Domain: ${location.host}\nNonce: ${nonce()}\nIssued At: ${new Date().toISOString()}`
  );
}

/** Ed25519 verify via WebCrypto. true/false, or null if the browser lacks support. */
export async function verify(pubkey: Uint8Array, msg: Uint8Array, sig: Uint8Array): Promise<boolean | null> {
  try {
    // copy into plain ArrayBuffers: TS's BufferSource type rejects Uint8Array<ArrayBufferLike>
    const buf = (u: Uint8Array) => u.slice().buffer as ArrayBuffer;
    const key = await crypto.subtle.importKey("raw", buf(pubkey), { name: "Ed25519" } as any, false, ["verify"]);
    return await crypto.subtle.verify({ name: "Ed25519" } as any, key, buf(sig), buf(msg));
  } catch {
    return null;
  }
}

export async function fetchBalance(address: string): Promise<number | null> {
  try {
    const r = await fetch(RPC, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "getBalance", params: [address] }),
    });
    const j = await r.json();
    return j.result ? j.result.value / 1e9 : null;
  } catch {
    return null;
  }
}

export const prefs = {
  get: () => { try { return localStorage.getItem(LS_KEY); } catch { return null; } },
  set: (n: string) => { try { localStorage.setItem(LS_KEY, n); } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(LS_KEY); } catch { /* ignore */ } },
};
