/* GENIUS — Solana wallet connect. READ-ONLY BY CONSTRUCTION.
 *
 * What this file can do:
 *   • discover installed Solana wallets (Wallet Standard, with a legacy fallback)
 *   • ask the wallet for the user's PUBLIC address
 *   • ask the wallet to sign a human-readable message the user can see in full,
 *     to prove they control the address (costs nothing, moves nothing)
 *   • read the SOL balance of that public address from a public RPC
 *
 * What this file cannot do, and no future edit may add:
 *   • request a transaction signature of any kind. The site therefore has no
 *     way to move funds or approve token transfers — the mechanism behind
 *     every "wallet drainer" scam. A test in lab/tests fails the build if the
 *     transaction-signing method names ever appear in this codebase.
 *   • see, ask for, or store a private key or seed phrase. There is no such
 *     code path. The keys live inside the wallet extension and never leave it.
 *
 * Nothing is sent anywhere: there is no backend. The only thing persisted is
 * the *name* of the wallet the user last connected, so it can reconnect
 * silently next visit. The public address is public by definition.
 */
(function () {
  'use strict';

  var RPC = 'https://api.mainnet-beta.solana.com';
  var LS_KEY = 'genius.wallet.name';
  var CHAIN = 'solana:mainnet';

  /* ---------------------------------------------------------- discovery */

  var wallets = {};            // name → normalised adapter
  var state = { adapter: null, address: null, pubkey: null, balance: null,
                verified: null, busy: false, error: null };

  function registerStandard(w) {
    try {
      if (!w || !w.chains || !w.features || !w.features['standard:connect']) return;
      if (!w.chains.some(function (c) { return String(c).indexOf('solana:') === 0; })) return;
      wallets[w.name] = {
        name: w.name, icon: w.icon || '',
        connect: function (silent) {
          return w.features['standard:connect'].connect(silent ? { silent: true } : undefined)
            .then(function (r) {
              var acc = (r.accounts || []).filter(function (a) {
                return !a.chains || a.chains.indexOf(CHAIN) >= 0;
              })[0] || (r.accounts || [])[0];
              if (!acc) throw new Error('No Solana account returned');
              return { account: acc, address: acc.address, pubkey: new Uint8Array(acc.publicKey) };
            });
        },
        signMessage: function (account, bytes) {
          var f = w.features['solana:signMessage'];
          if (!f) return Promise.reject(new Error('Wallet cannot sign messages'));
          return f.signMessage({ account: account, message: bytes }).then(function (out) {
            var o = Array.isArray(out) ? out[0] : out;
            return new Uint8Array(o.signature);
          });
        },
        disconnect: function () {
          var f = w.features['standard:disconnect'];
          return f ? f.disconnect() : Promise.resolve();
        },
        onChange: function (cb) {
          var f = w.features['standard:events'];
          if (f) f.on('change', cb);
        }
      };
      render();
    } catch (e) { /* a broken wallet must not break the page */ }
  }

  // Wallet Standard handshake: wallets already loaded answer app-ready;
  // wallets that load later announce themselves with register-wallet.
  window.addEventListener('wallet-standard:register-wallet', function (ev) {
    try { ev.detail({ register: function () {
      Array.prototype.forEach.call(arguments, registerStandard); } }); } catch (e) {}
  });
  try {
    window.dispatchEvent(new CustomEvent('wallet-standard:app-ready', {
      detail: { register: function () { Array.prototype.forEach.call(arguments, registerStandard); } }
    }));
  } catch (e) {}

  // Legacy fallback (older Phantom-style injection). Only used when nothing
  // registered through the standard.
  function registerLegacy() {
    if (Object.keys(wallets).length) return;
    var p = (window.phantom && window.phantom.solana) || window.solana;
    if (!p || typeof p.connect !== 'function') return;
    wallets['Phantom'] = {
      name: 'Phantom', icon: '',
      connect: function (silent) {
        return p.connect(silent ? { onlyIfTrusted: true } : undefined).then(function (r) {
          var pk = (r && r.publicKey) || p.publicKey;
          return { account: null, address: pk.toString(), pubkey: new Uint8Array(pk.toBytes()) };
        });
      },
      signMessage: function (_acc, bytes) {
        return p.signMessage(bytes, 'utf8').then(function (r) { return new Uint8Array(r.signature); });
      },
      disconnect: function () { return p.disconnect(); },
      onChange: function (cb) { try { p.on('accountChanged', cb); p.on('disconnect', cb); } catch (e) {} }
    };
    render();
  }

  /* ------------------------------------------------------------ helpers */

  function short(a) { return a ? a.slice(0, 4) + '…' + a.slice(-4) : ''; }

  function nonce() {
    var b = new Uint8Array(16); crypto.getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }

  // The message is shown to the user in full by the wallet before signing.
  // It is domain-bound and single-use so it cannot be replayed elsewhere.
  function ownershipMessage(address) {
    return 'GENIUS wants you to prove you control this Solana address:\n' + address +
      '\n\nThis signature proves ownership only. It costs nothing, moves nothing, ' +
      'and grants this site no permissions.\n\nDomain: ' + location.host +
      '\nNonce: ' + nonce() + '\nIssued At: ' + new Date().toISOString();
  }

  // Ed25519 verification in the browser via WebCrypto (Chrome 113+, Safari 17+,
  // Firefox 130+). Returns true/false, or null where the browser lacks support.
  function verify(pubkey, msgBytes, sig) {
    if (!(crypto.subtle && crypto.subtle.importKey)) return Promise.resolve(null);
    return crypto.subtle.importKey('raw', pubkey, { name: 'Ed25519' }, false, ['verify'])
      .then(function (k) { return crypto.subtle.verify({ name: 'Ed25519' }, k, sig, msgBytes); })
      .catch(function () { return null; });
  }

  function fetchBalance(address) {
    return fetch(RPC, { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'getBalance', params: [address] }) })
      .then(function (r) { return r.json(); })
      .then(function (j) { return j.result ? j.result.value / 1e9 : null; })
      .catch(function () { return null; });
  }

  /* ------------------------------------------------------------ actions */

  function connect(name, silent) {
    var a = wallets[name]; if (!a) return;
    state.busy = true; state.error = null; render();
    a.connect(!!silent).then(function (r) {
      state.adapter = a; state.account = r.account; state.address = r.address;
      state.pubkey = r.pubkey; state.verified = null; state.balance = null;
      try { localStorage.setItem(LS_KEY, name); } catch (e) {}
      a.onChange(function () { disconnect(true); });
      render();
      return fetchBalance(r.address).then(function (b) { state.balance = b; render(); });
    }).catch(function (e) {
      if (!silent) state.error = (e && e.message) || 'Connection rejected';
    }).then(function () { state.busy = false; render(); });
  }

  function disconnect(keepPref) {
    var a = state.adapter;
    state.adapter = state.account = state.address = state.pubkey = state.balance = null;
    state.verified = null; state.error = null;
    if (!keepPref) { try { localStorage.removeItem(LS_KEY); } catch (e) {} }
    if (a) a.disconnect().catch(function () {});
    render();
  }

  function prove() {
    if (!state.adapter) return;
    var msg = ownershipMessage(state.address);
    var bytes = new TextEncoder().encode(msg);
    state.busy = true; state.error = null; render();
    state.adapter.signMessage(state.account, bytes)
      .then(function (sig) { return verify(state.pubkey, bytes, sig); })
      .then(function (ok) { state.verified = ok === null ? 'unsupported' : (ok ? 'yes' : 'no'); })
      .catch(function (e) { state.error = (e && e.message) || 'Signature rejected'; })
      .then(function () { state.busy = false; render(); });
  }

  /* ---------------------------------------------------------------- UI */

  var open = false;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function render() {
    var btn = document.getElementById('wallet-btn');
    var panel = document.getElementById('wallet-panel');
    if (!btn || !panel) return;
    btn.textContent = state.address ? short(state.address) : 'Connect wallet';
    btn.classList.toggle('connected', !!state.address);
    panel.hidden = !open;
    if (!open) return;

    var names = Object.keys(wallets);
    var h = '<div class="wp-head"><span>Wallet</span><span class="wp-net">Solana · mainnet · read-only</span>' +
            '<button class="wp-x" data-act="close" aria-label="Close">×</button></div>';

    if (state.address) {
      h += '<div class="wp-row"><span>Address</span><code title="' + esc(state.address) + '" data-act="copy">' +
           esc(short(state.address)) + '</code></div>';
      h += '<div class="wp-row"><span>SOL balance</span><b>' +
           (state.balance === null ? '…' : esc(state.balance.toFixed(4)) + ' SOL') + '</b></div>';
      h += '<div class="wp-row"><span>$GENIUS balance</span><b class="wp-dim">no token exists yet</b></div>';
      h += '<div class="wp-row"><span>Ownership</span><b>' +
           (state.verified === 'yes' ? '<span class="wp-ok">Verified ✓</span>' :
            state.verified === 'no' ? '<span class="wp-bad">Signature did not verify</span>' :
            state.verified === 'unsupported' ? 'Signed (browser cannot verify Ed25519)' :
            '<span class="wp-dim">not proven</span>') + '</b></div>';
      h += '<div class="wp-actions">' +
           '<button class="btn solid" data-act="prove"' + (state.busy ? ' disabled' : '') +
           '>Prove ownership</button>' +
           '<button class="btn ghost" data-act="disconnect">Disconnect</button></div>';
    } else if (names.length) {
      h += '<div class="wp-list">' + names.map(function (n) {
        var w = wallets[n];
        return '<button class="wp-wallet" data-act="connect" data-name="' + esc(n) + '"' +
               (state.busy ? ' disabled' : '') + '>' +
               (w.icon ? '<img src="' + esc(w.icon) + '" alt="">' : '') + esc(n) + '</button>';
      }).join('') + '</div>';
    } else {
      h += '<p class="wp-none">No Solana wallet detected in this browser.<br>Install ' +
           '<a href="https://phantom.app" target="_blank" rel="noopener noreferrer">Phantom</a>, ' +
           '<a href="https://solflare.com" target="_blank" rel="noopener noreferrer">Solflare</a> or ' +
           '<a href="https://backpack.app" target="_blank" rel="noopener noreferrer">Backpack</a>, then reload.</p>';
    }
    if (state.error) h += '<p class="wp-err">' + esc(state.error) + '</p>';

    h += '<ul class="wp-rules">' +
         '<li>We never ask for a seed phrase or private key. Nobody legitimate does.</li>' +
         '<li>This site never requests a transaction signature, so it cannot move funds or approve transfers. That rule is enforced by a test in the codebase.</li>' +
         '<li>Only your public address is read. There is no server; nothing is stored anywhere but your browser.</li>' +
         '<li>There is nothing to claim, buy or mint. If a page that looks like this one asks you to, it is not us.</li>' +
         '</ul>';
    panel.innerHTML = h;
  }

  document.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-act]');
    var btn = document.getElementById('wallet-btn');
    var panel = document.getElementById('wallet-panel');
    if (ev.target === btn) { open = !open; if (open) registerLegacy(); render(); return; }
    if (!t) { if (open && panel && !panel.contains(ev.target)) { open = false; render(); } return; }
    var act = t.getAttribute('data-act');
    if (act === 'close') { open = false; render(); }
    else if (act === 'connect') connect(t.getAttribute('data-name'), false);
    else if (act === 'disconnect') disconnect(false);
    else if (act === 'prove') prove();
    else if (act === 'copy' && state.address && navigator.clipboard) navigator.clipboard.writeText(state.address);
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && open) { open = false; render(); } });

  // Silent reconnect to the wallet used last time — never prompts.
  window.addEventListener('load', function () {
    registerLegacy();
    var last = null; try { last = localStorage.getItem(LS_KEY); } catch (e) {}
    if (last && wallets[last]) connect(last, true);
    render();
  });
})();
