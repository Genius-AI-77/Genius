/* GENIUS Floor: the room where the six agents live.
 *
 * A pixel-art trading floor drawn on a canvas at 384x216 and scaled up with
 * image-rendering: pixelated. Everything it shows comes from window.GENIUS_DATA
 * (the lab's latest run): each agent's stance, the open position, equity, the
 * last decision, and whether a fill just happened. No libraries, no assets;
 * sprites and the tiny font are defined below as text.
 */
(function () {
  'use strict';

  var W = 384, H = 216;
  var C = {
    wall: '#0c1013', wallLo: '#10161a', trim: '#1e2528', floorA: '#0f1517', floorB: '#121a1d',
    deskTop: '#2b3438', deskFront: '#1a2124', screen: '#050a08', frame: '#232c30',
    volt: '#a6e22e', cyan: '#35d6e8', red: '#ff5a5a', amber: '#f0a53c',
    ink: '#f0f3f2', ink2: '#9aa5a7', dim: '#4a5459', skin: '#e8c39e', skinD: '#c9a07e',
    door: '#141b1e', doorLight: '#35d6e8'
  };

  /* -------------------------------------------------------- 3x5 font */
  var GLYPH = {
    '0':'111101101101111','1':'010110010010111','2':'111001111100111','3':'111001111001111',
    '4':'101101111001001','5':'111100111001111','6':'111100111101111','7':'111001001001001',
    '8':'111101111101111','9':'111101111001111',
    'A':'010101111101101','B':'110101110101110','C':'111100100100111','D':'110101101101110',
    'E':'111100110100111','F':'111100110100100','G':'111100101101111','H':'101101111101101',
    'I':'111010010010111','J':'001001001101111','K':'101101110101101','L':'100100100100111',
    'M':'101111111101101','N':'110101101101101','O':'111101101101111','P':'111101111100100',
    'Q':'111101101111001','R':'111101110101101','S':'111100111001111','T':'111010010010010',
    'U':'101101101101111','V':'101101101101010','W':'101101111111101','X':'101101010101101',
    'Y':'101101010010010','Z':'111001010100111',
    ' ':'000000000000000','.':'000000000000010',',':'000000000010100',':':'000010000010000',
    '$':'010111110011111','+':'000010111010000','-':'000000111000000','%':'101001010100101',
    '/':'001001010100100','(':'010100100100010',')':'010001001001010','\'':'010010000000000',
    '#':'101111101111101','!':'010010010000010','>':'100010001010100','<':'001010100010001'
  };
  function text(ctx, s, x, y, color) {
    ctx.fillStyle = color;
    s = String(s).toUpperCase();
    for (var i = 0; i < s.length; i++) {
      var g = GLYPH[s[i]] || GLYPH[' '];
      for (var p = 0; p < 15; p++) if (g[p] === '1') ctx.fillRect(x + (p % 3), y + ((p / 3) | 0), 1, 1);
      x += 4;
    }
  }
  function textW(s) { return String(s).length * 4 - 1; }

  /* --------------------------------------------------------- sprites */
  // H hair  F face  E eye  S shirt  s shirt shade  P pants  B boots  A accessory  . empty
  var BODY = [
    '....HHHH....',
    '...HHHHHH...',
    '...FFFFFF...',
    '...FEFFEF...',
    '...FFFFFF...',
    '....FFFF....',
    '..SSSSSSSS..',
    '.SSSSSSSSSS.',
    '.S.SSssSS.S.',
    '.S.SSssSS.S.',
    '...SSSSSS...',
    '...PPPPPP...',
    '...PP..PP...',
    '...PP..PP...',
    '...BB..BB...',
    '...BB..BB...'
  ];
  var AGENTS = [
    { name: 'ATLAS',  role: 'FUNDAMENTALS', hair: '#3a2a1f', shirt: '#6f9a1c', shade: '#557a14', pants: '#1e2528', glasses: true },
    { name: 'EUCLID', role: 'TECHNICALS',   hair: '#e8e2d0', shirt: '#1f8f9e', shade: '#176f7a', pants: '#1e2528', band: true },
    { name: 'FLUX',   role: 'ORDER FLOW',   hair: '#35d6e8', shirt: '#35d6e8', shade: '#22a9b8', pants: '#0f1416', hood: true },
    { name: 'VETO',   role: 'RISK',         hair: '#1a1a1a', shirt: '#c43c3c', shade: '#9a2e2e', pants: '#1a1a1a', big: true },
    { name: 'HERMES', role: 'EXECUTION',    hair: '#a6e22e', shirt: '#2b3438', shade: '#1e2528', pants: '#0f1416', cap: true },
    { name: 'LEDGER', role: 'AUDIT',        hair: '#5a5a5a', shirt: '#8a939a', shade: '#6b747a', pants: '#2b3438', book: true }
  ];

  function sprite(ctx, a, x, y, frame, facingLeft) {
    var map = { H: a.hair, F: C.skin, E: '#111', S: a.shirt, s: a.shade, P: a.pants, B: '#0a0d0f' };
    var bob = frame ? 1 : 0;
    for (var r = 0; r < BODY.length; r++) {
      var row = BODY[r];
      // legs alternate on the walk frame
      if (frame && (r === 12 || r === 13)) row = r === 12 ? '...PP..PP...' : '..PP....PP..';
      for (var c = 0; c < row.length; c++) {
        var ch = row[c]; if (ch === '.') continue;
        var cx = facingLeft ? (11 - c) : c;
        var yy = r < 11 ? y + r - bob : y + r;   // torso bobs, legs stay planted
        ctx.fillStyle = map[ch]; ctx.fillRect(x + cx, yy, 1, 1);
      }
    }
    // accessories
    var t = y - bob;
    if (a.glasses) { ctx.fillStyle = '#0a0d0f'; ctx.fillRect(x + 3, t + 3, 2, 1); ctx.fillRect(x + 7, t + 3, 2, 1); ctx.fillRect(x + 5, t + 3, 2, 1); }
    if (a.band)    { ctx.fillStyle = C.cyan; ctx.fillRect(x + 3, t + 1, 6, 1); }
    if (a.hood)    { ctx.fillStyle = a.shade; ctx.fillRect(x + 3, t + 0, 6, 1); ctx.fillRect(x + 2, t + 1, 1, 4); ctx.fillRect(x + 9, t + 1, 1, 4); }
    if (a.cap)     { ctx.fillStyle = '#6f9a1c'; ctx.fillRect(x + 3, t, 7, 1); ctx.fillRect(x + 4, t - 1, 5, 1); ctx.fillRect(x + 9, t + 1, 2, 1); }
    if (a.big)     { ctx.fillStyle = a.shirt; ctx.fillRect(x + 0, t + 7, 1, 3); ctx.fillRect(x + 11, t + 7, 1, 3); }
    if (a.book)    { ctx.fillStyle = C.ink; ctx.fillRect(x + 10, t + 8, 3, 3); ctx.fillStyle = C.amber; ctx.fillRect(x + 10, t + 8, 1, 3); }
  }

  function bubble(ctx, x, y, kind) {
    // 9x7 speech bubble above a sprite; kind: long | short | flat | veto | fill
    ctx.fillStyle = '#e9ecea'; ctx.fillRect(x, y, 9, 7); ctx.fillRect(x + 3, y + 7, 2, 1);
    ctx.fillStyle = C.frame; ctx.fillRect(x - 1, y + 1, 1, 5); ctx.fillRect(x + 9, y + 1, 1, 5);
    if (kind === 'long')  { ctx.fillStyle = '#4e8f0e'; ctx.fillRect(x + 4, y + 1, 1, 1); ctx.fillRect(x + 3, y + 2, 3, 1); ctx.fillRect(x + 2, y + 3, 5, 1); ctx.fillRect(x + 4, y + 4, 1, 2); }
    if (kind === 'short') { ctx.fillStyle = '#c43c3c'; ctx.fillRect(x + 4, y + 1, 1, 2); ctx.fillRect(x + 2, y + 3, 5, 1); ctx.fillRect(x + 3, y + 4, 3, 1); ctx.fillRect(x + 4, y + 5, 1, 1); }
    if (kind === 'flat')  { ctx.fillStyle = '#7a848a'; ctx.fillRect(x + 2, y + 3, 1, 1); ctx.fillRect(x + 4, y + 3, 1, 1); ctx.fillRect(x + 6, y + 3, 1, 1); }
    if (kind === 'veto')  { ctx.fillStyle = '#c43c3c'; ctx.fillRect(x + 4, y + 1, 1, 3); ctx.fillRect(x + 4, y + 5, 1, 1); }
    if (kind === 'fill')  { ctx.fillStyle = '#4e8f0e'; ctx.fillRect(x + 2, y + 3, 1, 1); ctx.fillRect(x + 3, y + 4, 1, 1); ctx.fillRect(x + 4, y + 3, 1, 1); ctx.fillRect(x + 5, y + 2, 1, 1); ctx.fillRect(x + 6, y + 1, 1, 1); }
  }

  /* ------------------------------------------------------------ room */
  var DESKS = [ // x,y of desk top-left for each agent, in AGENTS order
    { x: 34, y: 118 }, { x: 150, y: 118 }, { x: 266, y: 118 },
    { x: 34, y: 172 }, { x: 150, y: 172 }, { x: 266, y: 172 }
  ];
  var DOOR = { x: 344, y: 36, w: 30, h: 66 };

  function money(v) { return (v < 0 ? '-$' : '$') + Math.abs(Math.round(v)).toLocaleString('en-US'); }
  function money2(v) { var a = Math.abs(v); return (v < 0 ? '-$' : '$') + (a < 1000 ? a.toFixed(2) : Math.round(a).toLocaleString('en-US')); }

  function drawRoom(ctx, D, t) {
    var d = D.desk || {}, m = D.meta || {}, stances = d.stances || {};
    // wall + floor
    ctx.fillStyle = C.wall; ctx.fillRect(0, 0, W, 104);
    ctx.fillStyle = C.wallLo; ctx.fillRect(0, 96, W, 8);
    ctx.fillStyle = C.trim; ctx.fillRect(0, 104, W, 2);
    for (var fy = 106; fy < H; fy += 8) for (var fx = 0; fx < W; fx += 8) {
      ctx.fillStyle = ((fx + fy) / 8) % 2 ? C.floorA : C.floorB; ctx.fillRect(fx, fy, 8, 8);
    }
    // LED ticker strip along the top
    ctx.fillStyle = '#000'; ctx.fillRect(0, 4, W, 9);
    var price = D.equity_curve && D.equity_curve.length ? D.equity_curve[D.equity_curve.length - 1].price : 0;
    var tick = ((d.coin || 'ETH') + ' ') + money(price) + '   EQUITY ' + money(d.equity || 0) + '   SESSION ' + (d.session_pnl >= 0 ? '+' : '') + money(d.session_pnl || 0) +
               '   ' + (m.execution === 'live' ? 'LIVE EXECUTION' : m.execution === 'shadow' ? 'SHADOW MODE' : 'PAPER EXECUTION') + '   REAL MARKET, REAL DECISIONS   ';
    var tw = textW(tick) + 8, off = (t / 40) % tw;
    ctx.save(); ctx.beginPath(); ctx.rect(0, 4, W, 9); ctx.clip();
    text(ctx, tick, W - off, 6, C.amber); text(ctx, tick, W - off + tw, 6, C.amber); ctx.restore();

    // wall screen: equity sparkline + numbers
    var sx = 96, sy = 20, sw = 192, sh = 62;
    ctx.fillStyle = C.frame; ctx.fillRect(sx - 2, sy - 2, sw + 4, sh + 4);
    ctx.fillStyle = C.screen; ctx.fillRect(sx, sy, sw, sh);
    text(ctx, 'GENIUS DESK', sx + 4, sy + 4, C.ink2);
    var tag = d.halted ? 'HALTED' : m.execution === 'live' ? 'LIVE' : m.execution === 'shadow' ? 'SHADOW' : 'PAPER';
    text(ctx, tag, sx + sw - textW(tag) - 4, sy + 4, d.halted ? C.red : m.execution === 'live' ? C.volt : C.amber);
    ctx.fillStyle = C.trim; ctx.fillRect(sx + 4, sy + 11, sw - 8, 1);
    text(ctx, 'EQUITY', sx + 4, sy + 15, C.ink2);
    text(ctx, money(d.equity || 0), sx + 4, sy + 22, C.ink);
    var sp = d.session_pnl || 0;
    text(ctx, 'SESSION', sx + 4, sy + 31, C.ink2);
    text(ctx, (sp >= 0 ? '+' : '') + money(sp), sx + 4, sy + 38, sp >= 0 ? C.volt : C.red);
    var pos = d.position;
    if (d.books && d.books.length) {
      // three books: name + total P&L, the leaderboard in miniature
      var bs = d.books.slice().sort(function (a, b) { return b.total_pnl - a.total_pnl; });
      for (var bi = 0; bi < Math.min(3, bs.length); bi++) {
        var bk = bs[bi], yy = sy + 47 + bi * 6;
        text(ctx, bk.name, sx + 4, yy, C.ink2);
        var pv = (bk.total_pnl >= 0 ? '+' : '') + money2(bk.total_pnl);
        text(ctx, pv, sx + 34, yy, bk.total_pnl > 0 ? C.volt : bk.total_pnl < 0 ? C.red : C.dim);
        if (bk.position) text(ctx, bk.position.side === 'long' ? '>' : '<', sx + 76, yy, bk.position.side === 'long' ? C.volt : C.red);
      }
    } else {
      text(ctx, 'POSITION', sx + 4, sy + 47, C.ink2);
      text(ctx, pos ? (pos.side.toUpperCase() + ' ' + (pos.unrealized >= 0 ? '+' : '') + money(pos.unrealized)) : 'FLAT', sx + 4, sy + 54,
           pos ? (pos.unrealized >= 0 ? C.volt : C.red) : C.dim);
    }
    // sparkline of the last 120 equity points
    var eq = (D.equity_curve || []).slice(-120);
    if (eq.length > 1) {
      var gx = sx + 84, gy = sy + 15, gw = sw - 88, gh = 44;
      var lo = Infinity, hi = -Infinity;
      eq.forEach(function (p) { lo = Math.min(lo, p.equity); hi = Math.max(hi, p.equity); });
      var rng = hi - lo || 1;
      ctx.fillStyle = '#0a1a10'; ctx.fillRect(gx, gy, gw, gh);
      var up = eq[eq.length - 1].equity >= eq[0].equity;
      ctx.fillStyle = up ? C.volt : C.red;
      for (var i = 0; i < eq.length; i++) {
        var px = gx + Math.round(i * (gw - 1) / (eq.length - 1));
        var py = gy + gh - 1 - Math.round((eq[i].equity - lo) / rng * (gh - 1));
        ctx.fillRect(px, py, 1, 1);
        if (i) { // connect vertically for a continuous line
          var prevY = gy + gh - 1 - Math.round((eq[i - 1].equity - lo) / rng * (gh - 1));
          var a = Math.min(py, prevY), b = Math.max(py, prevY);
          ctx.fillRect(px, a, 1, b - a + 1);
        }
      }
    }

    // decor: wall sign, clock, plant, coffee machine
    ctx.fillStyle = C.frame; ctx.fillRect(14, 22, 62, 14);
    ctx.fillStyle = '#0a0d0f'; ctx.fillRect(15, 23, 60, 12);
    text(ctx, 'GENIUS LAB', 20, 27, C.volt);
    ctx.fillStyle = C.frame; ctx.fillRect(30, 50, 26, 26); ctx.fillStyle = '#0a0d0f'; ctx.fillRect(31, 51, 24, 24);
    var now = new Date(), ang = (now.getUTCMinutes() / 60) * Math.PI * 2 - Math.PI / 2, hang = ((now.getUTCHours() % 12) / 12) * Math.PI * 2 - Math.PI / 2;
    ctx.fillStyle = C.ink2;
    for (var q = 0; q < 12; q++) { ctx.fillRect(43 + Math.round(Math.cos(q / 12 * Math.PI * 2) * 9), 63 + Math.round(Math.sin(q / 12 * Math.PI * 2) * 9), 1, 1); }
    for (var l = 0; l < 8; l++) { ctx.fillStyle = C.ink; ctx.fillRect(43 + Math.round(Math.cos(ang) * l), 63 + Math.round(Math.sin(ang) * l), 1, 1); }
    for (var l2 = 0; l2 < 5; l2++) { ctx.fillStyle = C.volt; ctx.fillRect(43 + Math.round(Math.cos(hang) * l2), 63 + Math.round(Math.sin(hang) * l2), 1, 1); }
    // plant, bottom right corner
    ctx.fillStyle = '#5a3a1f'; ctx.fillRect(356, 192, 12, 10); ctx.fillStyle = '#3a2512'; ctx.fillRect(357, 200, 10, 2);
    ctx.fillStyle = '#2f7a2a'; ctx.fillRect(354, 178, 16, 14); ctx.fillStyle = '#3f9a38'; ctx.fillRect(358, 172, 8, 8); ctx.fillRect(352, 184, 4, 4); ctx.fillRect(368, 182, 4, 4);
    ctx.fillStyle = '#5ac24e'; ctx.fillRect(360, 174, 3, 3); ctx.fillRect(356, 186, 2, 2);
    // coffee machine on a side table, bottom left
    ctx.fillStyle = C.deskFront; ctx.fillRect(6, 178, 22, 10); ctx.fillStyle = C.deskTop; ctx.fillRect(6, 174, 22, 4);
    ctx.fillStyle = '#1e2528'; ctx.fillRect(9, 160, 12, 14); ctx.fillStyle = C.red; ctx.fillRect(11, 163, 2, 2);
    ctx.fillStyle = (t / 900 | 0) % 2 ? '#e9ecea' : C.dim; ctx.fillRect(15, 155 - ((t / 300 | 0) % 3), 1, 1); ctx.fillRect(17, 153 - ((t / 400 | 0) % 3), 1, 1);
    ctx.fillStyle = C.ink; ctx.fillRect(22, 170, 4, 4);

    // exchange door
    ctx.fillStyle = C.frame; ctx.fillRect(DOOR.x - 2, DOOR.y - 2, DOOR.w + 4, DOOR.h + 2);
    ctx.fillStyle = C.door; ctx.fillRect(DOOR.x, DOOR.y, DOOR.w, DOOR.h);
    ctx.fillStyle = (t / 600 | 0) % 2 ? C.doorLight : '#1c8a9b'; ctx.fillRect(DOOR.x + 4, DOOR.y + 4, DOOR.w - 8, 3);
    text(ctx, 'EXCHANGE', DOOR.x + 1, DOOR.y + 10, C.cyan);
    ctx.fillStyle = C.ink2; ctx.fillRect(DOOR.x + DOOR.w - 7, DOOR.y + 36, 2, 2);

    // clock + cadence, bottom left
    var last = m.last_bar_ts ? new Date(m.last_bar_ts * 1000) : null;
    var hh = last ? ('0' + last.getUTCHours()).slice(-2) + ':' + ('0' + last.getUTCMinutes()).slice(-2) : '--:--';
    text(ctx, 'LAST CYCLE ' + hh + ' UTC', 6, H - 9, C.ink2);
    text(ctx, 'HOURLY BARS', W - textW('HOURLY BARS') - 6, H - 9, C.dim);

    // desks + agents
    var last_dec = d.last_decision ? d.last_decision.decision : '';
    for (var k = 0; k < AGENTS.length; k++) {
      var a = AGENTS[k], dk = DESKS[k], frame = ((t / 480 + k * 130) | 0) % 2;
      var st = stances[a.name] || 'flat';
      if (a.big)  st = last_dec === 'VETOED' ? 'short' : 'flat';   // VETO: red only when it said no
      if (a.cap)  st = d.fill_last_cycle ? 'long' : 'flat';         // HERMES: green when it filled
      if (a.book) st = 'flat';
      // desk
      ctx.fillStyle = C.deskFront; ctx.fillRect(dk.x, dk.y + 6, 60, 10);
      ctx.fillStyle = C.deskTop; ctx.fillRect(dk.x, dk.y, 60, 6);
      // monitor on desk with stance-coloured screen
      var mc = st === 'long' ? C.volt : st === 'short' ? C.red : C.dim;
      ctx.fillStyle = C.frame; ctx.fillRect(dk.x + 38, dk.y - 12, 18, 13);
      ctx.fillStyle = C.screen; ctx.fillRect(dk.x + 39, dk.y - 11, 16, 11);
      ctx.fillStyle = mc; ctx.fillRect(dk.x + 41, dk.y - 9 + (frame ? 1 : 0), 12, 1); ctx.fillRect(dk.x + 41, dk.y - 6, 8, 1); ctx.fillRect(dk.x + 41, dk.y - 3, 10, 1);
      // VETO's big red button
      if (a.big) {
        var hot = last_dec === 'VETOED';
        ctx.fillStyle = C.frame; ctx.fillRect(dk.x + 6, dk.y - 4, 12, 5);
        ctx.fillStyle = hot && (t / 250 | 0) % 2 ? '#ff8a8a' : C.red; ctx.fillRect(dk.x + 8, dk.y - 7, 8, 4);
      }
      // sprite: HERMES walks to the door on a fill
      var ax = dk.x + 10, ay = dk.y - 18, walking = false, left = false;
      if (a.cap && d.fill_last_cycle) {
        var ph = (t / 3000) % 2;             // 0..2: out and back
        var prog = ph < 1 ? ph : 2 - ph;
        var tx = DOOR.x - 16, ty = DOOR.y + DOOR.h - 12;
        ax = Math.round(ax + (tx - ax) * prog); ay = Math.round(ay + (ty - ay) * prog);
        walking = true; left = ph >= 1;
      }
      sprite(ctx, a, ax, ay, walking ? frame : frame, left);
      // bubble
      var kind = a.big ? (last_dec === 'VETOED' ? 'veto' : 'flat')
               : a.cap ? (d.fill_last_cycle ? 'fill' : 'flat')
               : st;
      if (!(a.book)) bubble(ctx, ax + 2, ay - 11, kind);
      // name plate
      text(ctx, a.name, dk.x + 2, dk.y + 8, C.ink);
      text(ctx, a.role, dk.x + 2, dk.y + 18 - 4, C.dim);
    }
  }

  /* --------------------------------------------------------- panel */
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function ago(ts) {
    var s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (s < 3600) return Math.round(s / 60) + ' min ago';
    if (s < 86400) return Math.round(s / 3600) + ' h ago';
    return Math.round(s / 86400) + ' d ago';
  }
  function panel(el, D) {
    var d = D.desk || {}, m = D.meta || {}, pos = d.position, sp = d.session_pnl || 0;
    var exec = m.execution === 'live' ? ['LIVE EXECUTION', 'fl-live'] : m.execution === 'shadow' ? ['SHADOW MODE', 'fl-shadow'] : ['PAPER EXECUTION', 'fl-paper'];
    if (d.halted) exec = ['HALTED', 'fl-halted'];
    var roles = { ATLAS: 'Fundamentals', EUCLID: 'Technicals', FLUX: 'Order flow', VETO: 'Risk', HERMES: 'Execution', LEDGER: 'Audit' };
    var h = '<div class="fl-head"><span class="fl-badge fl-market">Live market</span><span class="fl-badge ' + exec[1] + '">' + exec[0] + '</span>' +
            '<span class="fl-when">Last cycle ' + (m.last_bar_ts ? esc(ago(m.last_bar_ts)) : '') + '</span></div>';
    h += '<div class="fl-nums"><div><span>Equity</span><b>' + money2(d.equity || 0) + '</b></div>' +
         '<div><span>Session</span><b class="' + (sp >= 0 ? 'fl-up' : 'fl-down') + '">' + (sp >= 0 ? '+' : '') + money2(sp) + '</b></div></div>';
    if (d.halted) h += '<div class="fl-pos fl-halt">DESK HALTED: ' + esc(d.halt_reason || 'kill switch') + '</div>';
    if (d.books && d.books.length) {
      var sorted = d.books.slice().sort(function (a, b) { return b.total_pnl - a.total_pnl; });
      h += '<div class="fl-board">';
      sorted.forEach(function (bk, i) {
        var p2 = bk.position;
        h += '<div class="fl-book"><span class="fl-rank">' + (i + 1) + '</span><b>' + esc(bk.name) + '</b>' +
             '<span class="fl-book-eq">' + money2(bk.equity) + '</span>' +
             '<span class="' + (bk.total_pnl > 0 ? 'fl-up' : bk.total_pnl < 0 ? 'fl-down' : 'fl-dim') + '">' + (bk.total_pnl >= 0 ? '+' : '') + money2(bk.total_pnl) + '</span>' +
             '<em>' + (p2 ? ('<span class="' + (p2.side === 'long' ? 'fl-up' : 'fl-down') + '">' + p2.side + '</span> ' + esc(p2.qty) + ' @ ' + money(p2.entry) +
                              ' <span class="' + (p2.unrealized >= 0 ? 'fl-up' : 'fl-down') + '">' + (p2.unrealized >= 0 ? '+' : '') + money2(p2.unrealized) + '</span>')
                          : esc(bk.last_decision === 'VETOED' ? 'vetoed' : 'flat')) + '</em></div>';
      });
      h += '</div>';
    } else if (pos) {
      h += '<div class="fl-pos"><div class="fl-pos-h"><b class="' + (pos.side === 'long' ? 'fl-up' : 'fl-down') + '">' + pos.side.toUpperCase() + '</b> ' +
           esc(pos.qty) + ' ' + esc(d.coin || 'ETH') + ' <span class="' + (pos.unrealized >= 0 ? 'fl-up' : 'fl-down') + '">' + (pos.unrealized >= 0 ? '+' : '') + money(pos.unrealized) + '</span></div>' +
           '<div class="fl-pos-r"><span>Entry</span><b>' + money(pos.entry) + '</b><span>Mark</span><b>' + money(pos.mark) + '</b>' +
           '<span>Stop</span><b>' + (pos.stop ? money(pos.stop) : 'none') + '</b><span>Held</span><b>' + esc(pos.bars_held) + ' bars</b></div></div>';
    } else {
      h += '<div class="fl-pos fl-flat">No open position. The desk is standing aside.</div>';
    }
    var ld = d.last_decision;
    if (ld) h += '<div class="fl-dec"><span>Last decision</span><b class="fl-' + esc(ld.decision) + '">' + esc(ld.decision.replace('_', ' ')) + '</b> <i>' + esc(ld.detail || '') + '</i></div>';
    h += '<ul class="fl-agents">';
    var dec = (d.last_decision || {}).decision || '';
    AGENTS.forEach(function (a) {
      var st = (d.stances || {})[a.name] || 'flat', line = (d.lines || {})[a.name] || '', label = st, cls = st;
      if (a.name === 'VETO')   { label = dec === 'VETOED' ? 'said no' : 'armed';   cls = dec === 'VETOED' ? 'short' : 'on'; }
      if (a.name === 'HERMES') { label = d.fill_last_cycle ? 'filled' : 'ready';    cls = d.fill_last_cycle ? 'long' : 'on'; }
      if (a.name === 'LEDGER') { label = 'watching'; cls = 'on'; }
      h += '<li><b>' + a.name + '</b><span class="fl-role">' + roles[a.name] + '</span><span class="fl-st fl-st-' + cls + '">' + label + '</span><p>' + esc(line) + '</p></li>';
    });
    h += '</ul>';
    el.innerHTML = h;
  }

  /* --------------------------------------------------------- mount */
  function mount(root, D) {
    if (!root || !D) return;
    var cv = root.querySelector('canvas'); var pn = root.querySelector('.fl-panel');
    if (!cv) { cv = document.createElement('canvas'); root.insertBefore(cv, root.firstChild); }
    cv.width = W; cv.height = H; cv.style.imageRendering = 'pixelated';
    var ctx = cv.getContext('2d'); ctx.imageSmoothingEnabled = false;
    if (pn) panel(pn, D);
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    function frame(t) { drawRoom(ctx, D, reduce ? 0 : t); if (!reduce) requestAnimationFrame(frame); }
    requestAnimationFrame(frame);
  }
  window.GENIUS_FLOOR = { mount: mount };
  document.addEventListener('DOMContentLoaded', function () {
    var root = document.getElementById('floor');
    if (root && window.GENIUS_DATA) mount(root, window.GENIUS_DATA);
  });
})();
