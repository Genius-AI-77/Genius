/* GENIUS, wallet connect for Robinhood Chain. READ-ONLY BY CONSTRUCTION.
 *
 * What this file can do:
 *   • discover installed browser wallets (EIP-6963 announcements, with the
 *     legacy window.ethereum fallback): MetaMask, Rabby, Robinhood Wallet, ...
 *   • ask the wallet for the user's PUBLIC address (eth_requestAccounts)
 *   • offer to switch the wallet to Robinhood Chain (a wallet prompt the user
 *     approves; it changes a setting, it moves nothing)
 *   • ask the wallet to sign a human-readable message the user can see in
 *     full, to prove they control the address (costs nothing, moves nothing)
 *   • read the ETH balance and the GENIUS balance of that public address from
 *     the chain's public RPC
 *
 * What this file cannot do, and no future edit may add:
 *   • request a transaction signature of any kind. The site therefore has no
 *     way to move funds or approve transfers, the mechanism behind
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

  var CHAIN_ID = 4663;
  var CHAIN_HEX = '0x1237';
  var RPC = 'https://rpc.mainnet.chain.robinhood.com';
  var EXPLORER = 'https://robinhoodchain.blockscout.com';
  var LS_KEY = 'genius.wallet.name';

  /* ---------------------------------------------------------- discovery */

  var wallets = {};            // name → { name, icon, provider }
  var state = { provider: null, name: null, address: null, chainId: null, balance: null,
                token: undefined, verified: null, busy: false, error: null };

  // EIP-6963: every installed wallet announces itself; no more fighting over window.ethereum.
  window.addEventListener('eip6963:announceProvider', function (ev) {
    var d = ev.detail || {};
    if (!d.provider || !d.info || !d.info.name) return;
    wallets[d.info.name] = { name: d.info.name, icon: d.info.icon || '', provider: d.provider };
    render();
  });
  function discover() {
    try { window.dispatchEvent(new Event('eip6963:requestProvider')); } catch (e) {}
    if (window.ethereum && !Object.keys(wallets).length) {
      var p = window.ethereum;
      var name = p.isRabby ? 'Rabby' : p.isRobinhood ? 'Robinhood Wallet' : p.isMetaMask ? 'MetaMask' : 'Browser wallet';
      wallets[name] = { name: name, icon: '', provider: p };
    }
  }

  /* ------------------------------------------------------------ helpers */

  function short(a) { return a ? a.slice(0, 6) + '…' + a.slice(-4) : ''; }
  function pad(x) { return x.replace(/^0x/, '').toLowerCase().padStart(64, '0'); }

  function nonce() {
    var b = new Uint8Array(16); crypto.getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }

  // The message is shown to the user in full by the wallet before signing.
  // It is domain-bound and single-use so it cannot be replayed elsewhere.
  function ownershipMessage(address) {
    return 'GENIUS wants you to prove you control this address on Robinhood Chain:\n' + address +
      '\n\nThis signature proves ownership only. It costs nothing, moves nothing, ' +
      'and grants this site no permissions.\n\nDomain: ' + location.host +
      '\nNonce: ' + nonce() + '\nIssued At: ' + new Date().toISOString();
  }

  function rpc(method, params) {
    return fetch(RPC, { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: method, params: params }) })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (j.error) throw new Error(j.error.message || 'rpc error'); return j.result; });
  }

  function fetchBalance(address) {
    return rpc('eth_getBalance', [address, 'latest']).then(function (hex) { return parseInt(hex, 16) / 1e18; })
      .catch(function () { return null; });
  }

  // ERC-20 balanceOf + decimals through eth_call; a read, nothing else.
  function fetchTokenBalance(address, ca) {
    var bal = rpc('eth_call', [{ to: ca, data: '0x70a08231' + pad(address) }, 'latest']);
    var dec = rpc('eth_call', [{ to: ca, data: '0x313ce567' }, 'latest']);
    return Promise.all([bal, dec]).then(function (r) {
      var d = parseInt(r[1], 16) || 18;
      return Number(BigInt(r[0]) * 1000000n / (10n ** BigInt(d))) / 1e6;
    }).catch(function () { return null; });
  }

  /* ------------------------------------------------------------ actions */

  function connect(name, silent) {
    var w = wallets[name];
    if (!w || state.busy) return Promise.resolve();
    state.busy = true; state.error = null; render();
    var req = silent ? w.provider.request({ method: 'eth_accounts' })
                     : w.provider.request({ method: 'eth_requestAccounts' });
    return req.then(function (accounts) {
      if (!accounts || !accounts.length) { if (!silent) throw new Error('No account returned'); return; }
      state.provider = w.provider; state.name = name; state.address = accounts[0];
      state.verified = null; state.balance = null; state.token = undefined;
      try { localStorage.setItem(LS_KEY, name); } catch (e) {}
      try {
        w.provider.on('accountsChanged', function (a) { if (!a || !a.length) disconnect(true); else { state.address = a[0]; state.verified = null; refresh(); } });
        w.provider.on('chainChanged', function (c) { state.chainId = parseInt(c, 16); render(); });
        w.provider.on('disconnect', function () { disconnect(true); });
      } catch (e) {}
      return w.provider.request({ method: 'eth_chainId' }).then(function (c) { state.chainId = parseInt(c, 16); })
        .catch(function () {}).then(refresh);
    }).catch(function (e) {
      if (!silent) state.error = (e && e.message) || 'Connection rejected';
    }).then(function () { state.busy = false; render(); });
  }

  function refresh() {
    render();
    var T = window.GENIUS_TOKEN;
    if (T && T.ca && T.chain === 'robinhood') fetchTokenBalance(state.address, T.ca).then(function (b) { state.token = b; render(); });
    return fetchBalance(state.address).then(function (b) { state.balance = b; render(); });
  }

  // Wallet prompt to switch networks; adds the chain if the wallet lacks it.
  // Changes a wallet setting. Cannot move funds.
  function switchChain() {
    if (!state.provider) return;
    state.busy = true; state.error = null; render();
    state.provider.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: CHAIN_HEX }] })
      .catch(function (e) {
        if (e && (e.code === 4902 || /unrecognized|not added|4902/i.test(e.message || ''))) {
          return state.provider.request({ method: 'wallet_addEthereumChain', params: [{
            chainId: CHAIN_HEX, chainName: 'Robinhood Chain', rpcUrls: [RPC],
            nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 }, blockExplorerUrls: [EXPLORER] }] });
        }
        throw e;
      })
      .then(function () { return state.provider.request({ method: 'eth_chainId' }); })
      .then(function (c) { state.chainId = parseInt(c, 16); })
      .catch(function (e) { state.error = (e && e.message) || 'Switch rejected'; })
      .then(function () { state.busy = false; render(); });
  }

  function disconnect(silent) {
    state.provider = null; state.name = null; state.address = null; state.chainId = null;
    state.balance = null; state.token = undefined; state.verified = null;
    if (!silent) { try { localStorage.removeItem(LS_KEY); } catch (e) {} }
    render();
  }

  // personal_sign: the wallet shows the full text and signs it only if it holds
  // the key for this address. The signature is shown, not sent anywhere.
  function prove() {
    if (!state.provider || !state.address || state.busy) return;
    state.busy = true; state.error = null; render();
    var msg = ownershipMessage(state.address);
    var hex = '0x' + Array.prototype.map.call(new TextEncoder().encode(msg), function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
    state.provider.request({ method: 'personal_sign', params: [hex, state.address] })
      .then(function (sig) { state.verified = (sig && /^0x[0-9a-fA-F]{130}$/.test(sig)) ? 'yes' : 'no'; })
      .catch(function (e) { state.error = (e && e.message) || 'Signature rejected'; })
      .then(function () { state.busy = false; render(); });
  }

  /* ------------------------------------------------------------ render */

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
    var h = '<div class="wp-head"><span>Wallet</span><span class="wp-net">Robinhood Chain · read-only</span>' +
            '<button class="wp-x" data-act="close" aria-label="Close">×</button></div>';

    if (state.address) {
      h += '<div class="wp-row"><span>Address</span><code title="' + esc(state.address) + '" data-act="copy">' +
           esc(short(state.address)) + '</code></div>';
      if (state.chainId && state.chainId !== CHAIN_ID) {
        h += '<div class="wp-row"><span>Network</span><b><span class="wp-bad">not Robinhood Chain</span> ' +
             '<button class="wp-mini" data-act="switch"' + (state.busy ? ' disabled' : '') + '>Switch</button></b></div>';
      }
      h += '<div class="wp-row"><span>ETH balance</span><b>' +
           (state.balance === null ? '…' : esc(state.balance.toFixed(5)) + ' ETH') + '</b></div>';
      var T2 = window.GENIUS_TOKEN;
      if (T2 && T2.ca && T2.chain === 'robinhood') h += '<div class="wp-row"><span>GENIUS</span><b>' +
           (state.token === undefined ? '…' : state.token === null ? '<span class="wp-dim">unavailable</span>' :
            esc(Number(state.token).toLocaleString('en-US', { maximumFractionDigits: 2 }))) + '</b></div>';
      h += '<div class="wp-row"><span>Ownership</span><b>' +
           (state.verified === 'yes' ? '<span class="wp-ok">Signed ✓</span>' :
            state.verified === 'no' ? '<span class="wp-bad">Signature did not verify</span>' :
            '<span class="wp-dim">not proven</span>') + '</b></div>';
      h += '<div class="wp-actions">' +
           '<button class="btn solid" data-act="prove"' + (state.busy ? ' disabled' : '') +
           '>Prove ownership</button>' +
           '<a class="btn ghost" href="' + EXPLORER + '/address/' + esc(state.address) + '" target="_blank" rel="noopener noreferrer">Explorer</a>' +
           '<button class="btn ghost" data-act="disconnect">Disconnect</button></div>';
    } else if (names.length) {
      h += '<div class="wp-list">' + names.map(function (n) {
        var w = wallets[n];
        return '<button class="wp-wallet" data-act="connect" data-name="' + esc(n) + '"' +
               (state.busy ? ' disabled' : '') + '>' +
               (w.icon ? '<img src="' + esc(w.icon) + '" alt="">' : '') + esc(n) + '</button>';
      }).join('') + '</div>';
    } else {
      h += '<p class="wp-none">No browser wallet detected.<br>Install ' +
           '<a href="https://metamask.io" target="_blank" rel="noopener noreferrer">MetaMask</a>, ' +
           '<a href="https://rabby.io" target="_blank" rel="noopener noreferrer">Rabby</a> or the ' +
           '<a href="https://robinhood.com/web3-wallet" target="_blank" rel="noopener noreferrer">Robinhood Wallet</a>, then reload.</p>';
    }
    if (state.error) h += '<p class="wp-err">' + esc(state.error) + '</p>';

    h += '<ul class="wp-rules">' +
         '<li>We never ask for a seed phrase or private key. Nobody legitimate does.</li>' +
         '<li>This site never requests a transaction signature, so it cannot move funds or approve transfers. That rule is enforced by a test in the codebase.</li>' +
         '<li>Only your public address is read. There is no server; nothing is stored anywhere but your browser.</li>' +
         '<li>This site will never ask you to claim, buy or mint anything. If a page that looks like this one does, it is not us.</li>' +
         '</ul>';
    panel.innerHTML = h;
  }

  document.addEventListener('click', function (ev) {
    var t = ev.target.closest('[data-act]');
    var btn = document.getElementById('wallet-btn');
    var panel = document.getElementById('wallet-panel');
    if (ev.target === btn) { open = !open; if (open) discover(); render(); return; }
    if (!t) { if (open && panel && !panel.contains(ev.target)) { open = false; render(); } return; }
    var act = t.getAttribute('data-act');
    if (act === 'close') { open = false; render(); }
    else if (act === 'connect') connect(t.getAttribute('data-name'), false);
    else if (act === 'disconnect') disconnect(false);
    else if (act === 'prove') prove();
    else if (act === 'switch') switchChain();
    else if (act === 'copy' && state.address && navigator.clipboard) navigator.clipboard.writeText(state.address);
  });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && open) { open = false; render(); } });

  // Silent reconnect to the wallet used last time, never prompts.
  window.addEventListener('load', function () {
    discover();
    var last = null; try { last = localStorage.getItem(LS_KEY); } catch (e) {}
    setTimeout(function () { if (last && wallets[last]) connect(last, true); render(); }, 150);
  });
})();
