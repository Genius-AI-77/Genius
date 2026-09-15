import { useCallback, useEffect, useRef, useState } from "react";
import {
  CHAIN_ID, EXPLORER, discover, fetchBalance, fetchTokenBalance, looksSigned, onWalletsChange,
  ownershipMessage, prefs, short, wallets, type Adapter, type Connected,
} from "../lib/wallet";

type Verified = null | "yes" | "no";
const tokenCA = () => (window as unknown as { GENIUS_TOKEN?: { ca?: string; chain?: string } }).GENIUS_TOKEN;

/** Connect button for the nav + the dropdown panel. Read-only by construction. */
export function WalletButton() {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState<Adapter[]>([]);
  const [adapter, setAdapter] = useState<Adapter | null>(null);
  const [conn, setConn] = useState<Connected | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [token, setToken] = useState<number | null | undefined>(undefined);
  const [verified, setVerified] = useState<Verified>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    discover();
    setList(wallets());
    const off = onWalletsChange(() => setList(wallets()));
    const last = prefs.get();
    if (last) {
      const a = wallets().find((w) => w.name === last);
      if (a) void connect(a, true);
    }
    return () => { off(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (panel.current && !panel.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const disconnect = useCallback((keepPref = false) => {
    adapter?.disconnect().catch(() => undefined);
    setAdapter(null); setConn(null); setBalance(null); setToken(undefined); setVerified(null); setError(null);
    if (!keepPref) prefs.clear();
  }, [adapter]);

  const connect = useCallback(async (a: Adapter, silent: boolean) => {
    setBusy(true); setError(null);
    try {
      const c = await a.connect(silent);
      setAdapter(a); setConn(c); setVerified(null); setBalance(null); setToken(undefined);
      prefs.set(a.name);
      a.onChange((accounts) => { if (accounts && accounts.length === 0) disconnect(true); else void connect(a, true); });
      const T = tokenCA();
      if (T?.ca && T.chain === "robinhood") void fetchTokenBalance(c.address, T.ca).then(setToken);
      setBalance(await fetchBalance(c.address));
    } catch (e) {
      if (!silent) setError((e as Error)?.message ?? "Connection rejected");
    } finally {
      setBusy(false);
    }
  }, [disconnect]);

  const prove = useCallback(async () => {
    if (!adapter || !conn) return;
    setBusy(true); setError(null);
    try {
      const sig = await adapter.signMessage(conn.address, ownershipMessage(conn.address));
      setVerified(looksSigned(sig) ? "yes" : "no");
    } catch (e) {
      setError((e as Error)?.message ?? "Signature rejected");
    } finally {
      setBusy(false);
    }
  }, [adapter, conn]);

  const switchChain = useCallback(async () => {
    if (!adapter || !conn) return;
    setBusy(true); setError(null);
    try { setConn({ ...conn, chainId: await adapter.switchChain() }); }
    catch (e) { setError((e as Error)?.message ?? "Switch rejected"); }
    finally { setBusy(false); }
  }, [adapter, conn]);

  const btnBase =
    "ml-[18px] flex-none rounded border px-3.5 py-[9px] font-mono text-[10.5px] font-semibold " +
    "uppercase tracking-[0.13em] transition-all hover:border-volt hover:text-volt hover:shadow-volt-soft " +
    "max-[520px]:ml-auto";

  return (
    <div className="relative" ref={panel}>
      <button
        type="button"
        id="wallet-btn"
        onClick={() => setOpen((o) => !o)}
        className={`${btnBase} ${conn ? "border-volt normal-case tracking-[0.04em] text-volt" : "border-line-2 text-ink"}`}
      >
        {conn ? short(conn.address) : "Connect wallet"}
      </button>

      {open && (
        <div
          className="absolute right-0 top-[52px] z-[70] w-[min(400px,calc(100vw-40px))] rounded-lg border
            border-line-2 p-[18px] text-[13px] leading-[1.6] text-ink-2 shadow-[0_30px_60px_-20px_rgba(0,0,0,.9)]"
          style={{ background: "linear-gradient(160deg,#141a1c,#0f1315 55%,#0a0d0f)" }}
        >
          <div className="mb-3.5 flex items-center gap-2.5 border-b border-line pb-3 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
            <span>Wallet</span>
            <span className="ml-auto font-medium normal-case tracking-[0.08em] text-ink-3">Robinhood Chain · read-only</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close"
              className="pl-1.5 text-[20px] leading-none text-ink-3 hover:text-volt">×</button>
          </div>

          {conn ? (
            <>
              <Row k="Address">
                <code className="cursor-copy text-volt" title={conn.address}
                  onClick={() => navigator.clipboard?.writeText(conn.address)}>{short(conn.address)}</code>
              </Row>
              {conn.chainId !== null && conn.chainId !== CHAIN_ID && (
                <Row k="Network">
                  <b className="font-medium text-ink"><span className="text-danger">not Robinhood Chain</span>{" "}
                    <button type="button" disabled={busy} onClick={switchChain}
                      className="ml-2 rounded-[3px] border border-volt px-2 py-[3px] font-mono text-[9.5px] font-semibold uppercase tracking-[0.1em] text-volt hover:bg-volt hover:text-[#07130a]">Switch</button></b>
                </Row>
              )}
              <Row k="ETH balance"><b className="font-medium text-ink">{balance === null ? "…" : `${balance.toFixed(5)} ETH`}</b></Row>
              {tokenCA()?.ca && tokenCA()?.chain === "robinhood" && (
                <Row k="GENIUS"><b className="font-medium text-ink">{token === undefined ? "…" : token === null ? <span className="text-ink-3">unavailable</span> : token.toLocaleString("en-US", { maximumFractionDigits: 2 })}</b></Row>
              )}
              <Row k="Ownership">
                <b className="font-medium text-ink">
                  {verified === "yes" ? <span className="text-volt">Signed ✓</span>
                    : verified === "no" ? <span className="text-danger">Signature did not verify</span>
                    : <span className="text-ink-3">not proven</span>}
                </b>
              </Row>
              <div className="mb-1 mt-3.5 flex flex-wrap gap-2">
                <button type="button" className="btn btn-solid !px-4 !py-2.5 !text-[10.5px]" disabled={busy} onClick={prove}>Prove ownership</button>
                <a className="btn btn-ghost !px-4 !py-2.5 !text-[10.5px]" href={`${EXPLORER}/address/${conn.address}`} target="_blank" rel="noopener noreferrer">Explorer</a>
                <button type="button" className="btn btn-ghost !px-4 !py-2.5 !text-[10.5px]" onClick={() => disconnect(false)}>Disconnect</button>
              </div>
            </>
          ) : list.length ? (
            <div className="mb-1.5 grid gap-1.5">
              {list.map((w) => (
                <button key={w.name} type="button" disabled={busy} onClick={() => connect(w, false)}
                  className="flex w-full items-center gap-2.5 rounded-[5px] border border-line-2 bg-[#0b0f11] px-3 py-[11px]
                    text-left font-display text-[12.5px] font-semibold text-ink transition-all hover:border-volt hover:shadow-volt-soft">
                  {w.icon && <img src={w.icon} alt="" className="h-5 w-5 rounded" />}
                  {w.name}
                </button>
              ))}
            </div>
          ) : (
            <p className="font-mono text-[12.5px] leading-[1.7] text-ink-2">
              No browser wallet detected.<br />Install{" "}
              <a className="text-volt" href="https://metamask.io" target="_blank" rel="noopener noreferrer">MetaMask</a>,{" "}
              <a className="text-volt" href="https://rabby.io" target="_blank" rel="noopener noreferrer">Rabby</a> or the{" "}
              <a className="text-volt" href="https://robinhood.com/web3-wallet" target="_blank" rel="noopener noreferrer">Robinhood Wallet</a>, then reload.
            </p>
          )}

          {error && <p className="mt-2.5 font-mono text-[12px] text-danger">{error}</p>}

          <ul className="mt-3.5 list-disc border-t border-dashed border-line pl-4 pt-3 font-mono text-[11.5px] leading-[1.6] text-ink-3">
            <li className="mb-1.5">We never ask for a seed phrase or private key. Nobody legitimate does.</li>
            <li className="mb-1.5">This site never requests a transaction signature, so it cannot move funds or approve transfers. That rule is enforced by a test in the codebase.</li>
            <li className="mb-1.5">Only your public address is read. There is no server; nothing is stored anywhere but your browser.</li>
            <li>This site will never ask you to claim, buy or mint anything. If a page that looks like this one does, it is not us.</li>
          </ul>
        </div>
      )}
    </div>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-b border-line py-2 font-mono text-[12.5px]">
      <span className="text-ink-3">{k}</span>
      {children}
    </div>
  );
}

/** The in-page "Connect a wallet" card for the Connect section. */
export function WalletCard() {
  return (
    <div className="mod mt-9 p-[26px]">
      <h5 className="mb-3.5 font-display text-[19px] font-bold text-ink">
        What connecting does{" "}
        <span className="inline-block rounded-[3px] border border-volt/40 bg-volt/10 px-2 py-[3px] align-[1px] font-mono text-[9.5px] font-semibold uppercase tracking-[0.14em] text-volt">Read-only</span>
      </h5>
      <p className="max-w-[74ch] text-[15.5px] leading-[1.68] text-ink-2">
        Three things, and only three: it shows your public address, shows your ETH balance on Robinhood
        Chain, and, if you choose, asks your wallet to sign a message you can read in full, proving you
        control the address. That is all it can ever do. It works with MetaMask, Rabby, the Robinhood
        Wallet and any wallet that speaks the standard.
      </p>
      <ul className="mt-[18px] list-disc pl-[18px] text-[14.5px] leading-[1.62] text-ink-2 marker:text-ink-3">
        <li className="mb-2.5">This site <strong className="font-semibold text-ink">never requests a transaction signature</strong>. It cannot move funds or approve transfers, which is the mechanism behind every wallet-drainer scam. A test in the codebase fails the build if that code ever appears.</li>
        <li className="mb-2.5">Your private key and seed phrase never leave your wallet. There is no code path here that could see them, and no one legitimate will ever ask for them.</li>
        <li>This site will never ask you to claim, buy or mint anything. If a page that looks like this one does, it is not us.</li>
      </ul>
      <p className="mt-4">
        <button type="button" className="btn btn-solid" onClick={() => document.getElementById("wallet-btn")?.click()}>
          Connect wallet
        </button>
      </p>
    </div>
  );
}
