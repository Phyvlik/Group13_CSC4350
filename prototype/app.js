/* Epoch front end (pages only).
   Market data, trades, cash and position math, statistics and feedback are NOT computed here.
   They come from `api` (see mock-api.js), which the backend endpoints will replace.
   Still local for now: sign in and accounts (auth issue #6), kept in localStorage so the pages can be navigated. */
(() => {
'use strict';

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (n) => (n < 0 ? '-' : '') + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const signed = (n) => (n > 0 ? '+' : '') + money(n);
const pct = (n, d = 0) => (Number.isFinite(n) ? n.toFixed(d) + '%' : 'n/a');
const price = (n) => (n >= 100 ? n.toFixed(2) : n >= 10 ? n.toFixed(3) : n.toFixed(4));
const qtyText = (n) => (+n).toFixed(4).replace(/\.?0+$/, '') || '0';
const cls = (n) => (n > 0 ? 'gain' : n < 0 ? 'loss' : '');
const go = (h) => { if (location.hash === h) route(); else location.hash = h; };
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  $('#toasts').append(t);
  setTimeout(() => t.remove(), 2800);
}

/* ---------- accounts (local until auth endpoints exist) ---------- */
const KEY = 'epoch.users', UID = 'epoch.uid';
let users = loadUsers();
function loadUsers() {
  try { const d = JSON.parse(localStorage.getItem(KEY)); if (Array.isArray(d) && d.length) return d; } catch (e) {}
  return [
    { id: 'u1', name: 'Admin', email: 'admin@epoch.test', pass: 'admin-demo', role: 'Admin', status: 'Active' },
    { id: 'u2', name: 'Demo Trader', email: 'demo@epoch.test', pass: 'demo-demo', role: 'Trader', status: 'Active' },
  ];
}
function saveUsers() { try { localStorage.setItem(KEY, JSON.stringify(users)); } catch (e) {} }
function me() { try { const id = localStorage.getItem(UID); return users.find((u) => u.id === id && u.status === 'Active') || null; } catch (e) { return null; } }
function setMe(id) { try { id ? localStorage.setItem(UID, id) : localStorage.removeItem(UID); } catch (e) {} }

/* ---------- chart (draws only the bars the server sent) ---------- */
const colors = () => { const c = getComputedStyle(document.documentElement); const g = (v) => c.getPropertyValue(v).trim(); return { text: g('--text'), muted: g('--muted'), line: g('--line'), gain: g('--gain'), loss: g('--loss'), accent: g('--accent'), hatch: g('--hatch'), onAccent: g('--on-accent') }; };
function drawChart(canvas, bars, opt = {}) {
  const W = opt.window || 64, F = opt.future ?? 14, dpr = devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!bars.length || !w) return;
  if (canvas.width !== w * dpr || canvas.height !== h * dpr) { canvas.width = w * dpr; canvas.height = h * dpr; }
  const x = canvas.getContext('2d'); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, w, h);
  const C = colors(), left = 58, bottom = 24, top = 10, pw = w - left - 6, ph = h - top - bottom, slot = pw / (W + F);
  const vis = bars.slice(-W);
  let lo = Math.min(...vis.map((b) => b.l)), hi = Math.max(...vis.map((b) => b.h)); const padv = (hi - lo) * 0.07 || 1; lo -= padv; hi += padv;
  const Y = (v) => top + (1 - (v - lo) / (hi - lo)) * ph, off = W - vis.length;
  x.font = '11px "Geist Mono", monospace'; x.textBaseline = 'middle';
  for (let i = 0; i <= 4; i++) { const v = lo + ((hi - lo) * i) / 4, y = Y(v); x.strokeStyle = C.line; x.lineWidth = 1; x.beginPath(); x.moveTo(left, y + .5); x.lineTo(w - 6, y + .5); x.stroke(); x.fillStyle = C.muted; x.textAlign = 'right'; x.fillText(price(v), left - 8, y); }
  /* hidden future zone */
  const fx = left + W * slot; x.save(); x.beginPath(); x.rect(fx + 4, top, F * slot - 4, ph); x.clip(); x.strokeStyle = C.hatch; x.lineWidth = 1;
  for (let k = -ph; k < F * slot; k += 9) { x.beginPath(); x.moveTo(fx + 4 + k, top + ph); x.lineTo(fx + 4 + k + ph, top); x.stroke(); } x.restore();
  x.strokeStyle = C.line; x.strokeRect(fx + 4.5, top + .5, F * slot - 5, ph - 1);
  x.fillStyle = C.muted; x.textAlign = 'center'; x.font = '12px "Geist", sans-serif';
  if (F * slot > 70) { const cx = fx + 4 + (F * slot - 4) / 2; x.fillText('Future prices', cx, top + ph / 2 - 8); x.fillText('hidden', cx, top + ph / 2 + 8); }
  x.font = '11px "Geist Mono", monospace';
  vis.forEach((b, i) => {
    const cx = left + (off + i + 0.5) * slot, up = b.c >= b.o, col = up ? C.gain : C.loss, bw = Math.max(2, slot * 0.62);
    x.strokeStyle = col; x.fillStyle = col; x.lineWidth = 1; x.beginPath(); x.moveTo(cx, Y(b.h)); x.lineTo(cx, Y(b.l)); x.stroke();
    const y1 = Y(Math.max(b.o, b.c)), y2 = Y(Math.min(b.o, b.c)); x.fillRect(cx - bw / 2, y1, bw, Math.max(1, y2 - y1));
  });
  const last = vis[vis.length - 1], ly = Y(last.c);
  x.setLineDash([3, 4]); x.strokeStyle = C.accent; x.beginPath(); x.moveTo(left, ly + .5); x.lineTo(fx, ly + .5); x.stroke(); x.setLineDash([]);
  x.fillStyle = C.accent; x.fillRect(0, ly - 9, left - 4, 18); x.fillStyle = C.onAccent; x.textAlign = 'right'; x.fillText(price(last.c), left - 8, ly);
  x.fillStyle = C.muted; x.textAlign = 'center';
  [0, Math.floor(vis.length / 2), vis.length - 1].forEach((i) => { const cx = left + (off + i + .5) * slot; x.fillText(vis[i].d.slice(2), Math.min(Math.max(cx, left + 30), fx - 20), h - 9); });
  if (opt.hover != null && opt.hover >= 0 && opt.hover < vis.length) {
    const b = vis[opt.hover], cx = left + (off + opt.hover + .5) * slot;
    x.strokeStyle = C.muted; x.setLineDash([2, 3]); x.beginPath(); x.moveTo(cx, top); x.lineTo(cx, top + ph); x.stroke(); x.setLineDash([]);
    x.textAlign = 'left'; x.fillStyle = C.text; x.fillText(b.d + '   O ' + price(b.o) + '  H ' + price(b.h) + '  L ' + price(b.l) + '  C ' + price(b.c), left + 8, top + 10);
  }
  if (opt.hoverY != null && opt.hoverY > top && opt.hoverY < top + ph) {
    const v = lo + (1 - (opt.hoverY - top) / ph) * (hi - lo);
    x.strokeStyle = C.muted; x.setLineDash([2, 3]); x.beginPath(); x.moveTo(left, opt.hoverY + .5); x.lineTo(fx, opt.hoverY + .5); x.stroke(); x.setLineDash([]);
    x.fillStyle = C.line; x.fillRect(0, opt.hoverY - 9, left - 4, 18); x.fillStyle = C.text; x.textAlign = 'right'; x.fillText(price(v), left - 8, opt.hoverY);
  }
  canvas._geom = { left, slot, off, n: vis.length };
}

/* ---------- views ---------- */
const app = $('#app');
let cleanup = null;
const NAV = [['dashboard', 'Dashboard'], ['practice', 'Practice'], ['stats', 'Statistics'], ['journal', 'Journal'], ['feedback', 'Feedback'], ['profile', 'Profile']];

function shell(active, body) {
  const u = me(), admin = u.role === 'Admin';
  return `<header class="bar"><div class="bar-in">
    <a class="logo" href="#/${admin ? 'admin' : 'dashboard'}">Epoch<i>.</i></a>
    <nav class="nav" aria-label="Main">${admin ? '<a href="#/admin" aria-current="page">Admin workspace</a>' : NAV.map(([k, l]) => `<a href="#/${k}" ${k === active ? 'aria-current="page"' : ''}>${l}</a>`).join('')}</nav>
    <div class="bar-end"><button class="btn ghost small" data-act="theme" type="button">Theme</button><button class="btn small" data-act="signout" type="button">Sign out</button></div>
  </div></header><main class="page">${body}</main>`;
}
const loading = (active) => (app.innerHTML = shell(active, '<p class="muted">Loading...</p>'));
const failed = (e) => (app.querySelector('main').innerHTML = `<div class="panel empty"><h2>Something went wrong</h2><p>${esc(e.message || 'Could not reach the server.')}</p></div>`);

function authView(mode) {
  const signin = mode === 'signin';
  app.innerHTML = `<div class="auth"><section class="auth-form"><a class="logo" href="#/signin">Epoch<i>.</i></a>
    <h1>${signin ? 'Sign in' : 'Create account'}</h1><p class="sub">${signin ? 'Access your Epoch account.' : 'Create a trader account to save your practice.'}</p>
    <form id="authform" novalidate>
      ${signin ? '' : '<div class="field"><label for="n">Display name</label><input id="n" name="name" autocomplete="nickname"></div>'}
      <div class="field"><label for="e">Email</label><input id="e" name="email" type="email" autocomplete="email"></div>
      <div class="field"><label for="p">Password</label><input id="p" name="pass" type="password" autocomplete="${signin ? 'current-password' : 'new-password'}"></div>
      ${signin ? '' : '<div class="field"><label for="p2">Confirm password</label><input id="p2" name="pass2" type="password" autocomplete="new-password"></div>'}
      <p class="err" id="err" role="alert"></p>
      <button class="btn primary block" type="submit">${signin ? 'Sign in' : 'Create account'}</button>
    </form>
    <p class="auth-alt">${signin ? 'New to Epoch? <a href="#/signup">Create an account</a>' : 'Already registered? <a href="#/signin">Sign in</a>'}</p>
    ${signin ? '<p class="hint" style="margin-top:28px">Placeholder logins: demo@epoch.test / demo-demo (trader), admin@epoch.test / admin-demo (admin).</p>' : ''}
  </section><section class="auth-art" aria-hidden="true"><canvas></canvas><p>Practice on past markets. Decide first, see the outcome after.</p></section></div>`;
  /* decorative chart on the placeholder bars; the pointer scrubs through it */
  const cv = $('.auth-art canvas'), bars = window.MOCK_BARS; let n = reduceMotion ? 150 : 40, scrub = false;
  const draw = () => drawChart(cv, bars.slice(0, n), { window: 90, future: 24 });
  draw(); const rs = () => draw(); addEventListener('resize', rs);
  const iv = reduceMotion ? null : setInterval(() => { if (scrub) return; n = n >= 200 ? 40 : n + 1; draw(); }, 420);
  const art = $('.auth-art');
  art.addEventListener('pointermove', (e) => { const r = art.getBoundingClientRect(), nn = 40 + Math.round(((e.clientX - r.left) / r.width) * 160); scrub = true; if (nn !== n) { n = nn; draw(); } });
  art.addEventListener('pointerleave', () => { scrub = false; });
  cleanup = () => { removeEventListener('resize', rs); iv && clearInterval(iv); };
  $('#authform').addEventListener('submit', (ev) => {
    ev.preventDefault(); const f = Object.fromEntries(new FormData(ev.target)), err = $('#err'); err.textContent = '';
    const email = (f.email || '').trim().toLowerCase();
    if (!/^\S+@\S+\.\S+$/.test(email)) return (err.textContent = 'Enter a valid email address.');
    if (!f.pass) return (err.textContent = 'Enter your password.');
    if (signin) {
      const u = users.find((x) => x.email === email && x.pass === f.pass);
      if (!u) return (err.textContent = 'Email or password is incorrect.');
      if (u.status !== 'Active') return (err.textContent = 'This account is disabled. Contact an admin.');
      setMe(u.id); go(u.role === 'Admin' ? '#/admin' : '#/dashboard');
    } else {
      if (!(f.name || '').trim()) return (err.textContent = 'Enter a display name.');
      if (f.pass.length < 8) return (err.textContent = 'Use at least 8 characters for your password.');
      if (f.pass !== f.pass2) return (err.textContent = 'Passwords do not match.');
      if (users.some((x) => x.email === email)) return (err.textContent = 'An account with this email already exists.');
      const u = { id: 'u' + Date.now(), name: f.name.trim(), email, pass: f.pass, role: 'Trader', status: 'Active' };
      users.push(u); saveUsers(); setMe(u.id); toast('Account created.'); go('#/dashboard');
    }
  });
}

async function dashboardView() {
  const u = me(); loading('dashboard');
  const ss = (await api.sessions()).slice().reverse();
  const rows = ss.map((s) => { const live = s.status === 'In progress'; return `<tr>
    <td><b>${esc(s.sym)}</b></td><td class="mono">${s.start} to ${s.end}</td>
    <td><span class="tag ${live ? 'live' : ''}">${s.status}</span></td>
    <td class="mono ${cls(s.pl)}">${signed(s.pl)}</td>
    <td class="r"><a class="btn small" href="${live ? '#/replay/' + s.id : '#/stats/' + s.id}">${live ? 'Resume' : 'Results'}</a></td></tr>`; }).join('');
  app.innerHTML = shell('dashboard', `<div class="head"><div><h1>Dashboard</h1><p class="sub">Welcome back, ${esc(u.name)}. Choose a session or start a new practice.</p></div><a class="btn primary" href="#/new">Start new session</a></div>
    <h2 style="margin-bottom:12px">Practice sessions</h2>
    <div class="panel scroll-x">${ss.length ? `<table class="table"><thead><tr><th>Instrument</th><th>Historical period</th><th>Status</th><th>Profit / loss</th><th></th></tr></thead><tbody>${rows}</tbody></table>`
      : `<div class="empty"><h2>No sessions yet</h2><p>Pick an instrument and a past period to place your first practice trade.</p><a class="btn primary" href="#/new">Start new session</a></div>`}</div>`);
}

async function newView() {
  loading('practice');
  const inst = await api.instruments();
  app.innerHTML = shell('practice', `<div class="head"><div><h1>New practice session</h1><p class="sub">Choose one instrument and a historical period.</p></div></div>
    <form class="panel pad" id="nf" style="max-width:560px" novalidate>
      <div class="field"><label for="i">Instrument</label><select id="i" name="sym"><option value="">Select an instrument</option>${inst.map((i) => `<option value="${esc(i.sym)}" data-from="${i.from}" data-to="${i.to}">${esc(i.sym)} - ${esc(i.name)}</option>`).join('')}</select></div>
      <div class="row" style="margin-top:16px"><div class="field"><label for="a">Start date</label><input id="a" name="start" type="date"></div><div class="field"><label for="b">End date</label><input id="b" name="end" type="date"></div></div>
      <p class="hint" id="range" style="margin-top:10px">Pick an instrument to see its available dates.</p>
      <p class="hint" style="margin-top:14px">Virtual starting cash is assigned when the session starts.</p>
      <p class="err" id="err" role="alert" style="margin-top:12px"></p>
      <div style="display:flex;gap:10px;margin-top:22px"><button class="btn primary" type="submit">Start practice</button><a class="btn" href="#/dashboard">Cancel</a></div>
    </form>`);
  $('#i').addEventListener('change', (e) => {
    const o = e.target.selectedOptions[0]; if (!o || !o.value) return;
    $('#a').min = $('#b').min = o.dataset.from; $('#a').max = $('#b').max = o.dataset.to; $('#range').textContent = 'Available: ' + o.dataset.from + ' to ' + o.dataset.to + '.';
  });
  $('#nf').addEventListener('submit', async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)), err = $('#err'); err.textContent = '';
    if (!f.sym) return (err.textContent = 'Select an instrument.');
    if (!f.start || !f.end) return (err.textContent = 'Enter both a start and an end date.');
    if (f.start >= f.end) return (err.textContent = 'The end date must be after the start date.');
    try { const s = await api.createSession({ sym: f.sym, start: f.start, end: f.end }); location.hash = '#/replay/' + s.id; } catch (x) { err.textContent = x.message; }
  });
}

async function practiceRedirect() {
  const live = (await api.sessions()).filter((s) => s.status === 'In progress').pop();
  location.hash = live ? '#/replay/' + live.id : '#/new';
}

async function replayView(id) {
  loading('practice');
  let state = await api.replay(id), hover = null, hoverY = null, pace = 1, pending = 0;
  const s = state.session;
  app.innerHTML = shell('practice', `<div class="head"><div><h1>Practice replay</h1><p class="sub">Replay historical prices and save a practice trade.</p></div></div>
    <div class="grid-2"><div>
      <div class="panel chart-wrap"><div class="chart-top"><div><span class="sym">${esc(s.sym)}</span> <span class="muted mono" id="when"></span></div><div class="mono" id="px"></div></div>
        <canvas class="chart" id="cv" aria-label="Historical price chart for ${esc(s.sym)}. Future prices are hidden."></canvas></div>
      <div class="pace"><div class="field"><label for="pace">Replay pace</label><select id="pace"><option value="1">1 bar at a time</option><option value="5">5 bars at a time</option><option value="10">10 bars at a time</option></select></div>
        <button class="btn" id="reveal" type="button"></button></div>
    </div>
    <aside class="stack">
      <div class="panel account"><div><div class="label">Cash</div><div class="v" id="cash"></div></div><div><div class="label">Position</div><div class="v" id="pos"></div></div><div><div class="label">Equity</div><div class="v" id="eq"></div></div></div>
      <form class="panel pad" id="tf" novalidate>
        <div class="field"><span class="label">Side</span><div class="seg" role="radiogroup" aria-label="Side"><input type="radio" name="side" id="sb" value="buy" checked><label for="sb">Buy</label><input type="radio" name="side" id="ss" value="sell"><label for="ss">Sell</label></div></div>
        <div class="field"><label for="q">Quantity</label><input id="q" name="qty" type="number" min="0" step="any" inputmode="decimal" placeholder="Enter amount"><span class="hint" id="est">Order value $0.00</span></div>
        <div class="field"><label for="r">Trade reasoning</label><textarea id="r" name="why" placeholder="Why are you making this trade?"></textarea></div>
        <p class="err" id="err" role="alert" style="margin-top:12px"></p>
        <button class="btn primary block" type="submit" style="margin-top:16px">Save trade and reasoning</button>
      </form>
      <button class="btn block" id="end" type="button">End session / Results</button>
    </aside></div>`);
  const cv = $('#cv');
  const last = () => state.bars[state.bars.length - 1];
  const paint = () => {
    const b = last(), prev = state.bars[state.bars.length - 2] || b, ch = ((b.c / prev.c) - 1) * 100, a = state.account;
    $('#when').textContent = '| ' + b.d; $('#px').innerHTML = `${price(b.c)} <span class="${cls(ch)}">${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%</span>`;
    $('#cash').textContent = money(a.cash); $('#pos').textContent = qtyText(a.position); $('#eq').textContent = money(a.equity);
    const n = Math.min(pace, state.remaining), rv = $('#reveal'); rv.disabled = state.remaining === 0; rv.textContent = state.remaining === 0 ? 'Period complete' : n === 1 ? 'Reveal next bar' : 'Reveal next ' + n + ' bars';
    drawChart(cv, state.bars, { hover, hoverY }); upd();
  };
  const upd = () => { const q = parseFloat($('#q').value) || 0; $('#est').textContent = 'Order value ' + money(q * last().c); };
  paint(); const rs = () => paint(); addEventListener('resize', rs);
  cleanup = () => removeEventListener('resize', rs);
  cv.addEventListener('mousemove', (e) => { const g = cv._geom; if (!g) return; const r = cv.getBoundingClientRect(); const i = Math.floor((e.clientX - r.left - g.left) / g.slot) - g.off; hover = i >= 0 && i < g.n ? i : null; hoverY = e.clientY - r.top; if (!pending) { pending = requestAnimationFrame(() => { pending = 0; drawChart(cv, state.bars, { hover, hoverY }); }); } });
  cv.addEventListener('mouseleave', () => { hover = null; hoverY = null; drawChart(cv, state.bars, {}); });
  $('#pace').addEventListener('change', (e) => { pace = +e.target.value; paint(); });
  $('#q').addEventListener('input', upd);
  $('#reveal').addEventListener('click', async () => { try { state = await api.reveal(id, pace); paint(); } catch (x) { toast(x.message); } });
  $('#tf').addEventListener('submit', async (e) => {
    e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)), err = $('#err'); err.textContent = '';
    const qty = parseFloat(f.qty);
    if (!(qty > 0)) return (err.textContent = 'Enter a quantity greater than zero.');
    if (!(f.why || '').trim()) return (err.textContent = 'Add your reasoning before saving the trade.');
    try { const r = await api.placeTrade(id, { side: f.side, qty, reasoning: f.why.trim() }); state.account = r.account; $('#q').value = ''; $('#r').value = ''; paint(); toast(r.trade.id + ' saved to your journal.'); } catch (x) { err.textContent = x.message; }
  });
  $('#end').addEventListener('click', async () => {
    if (state.account.position > 0 && !confirm('You still hold an open position. It will be marked at the current price. End the session?')) return;
    try { await api.endSession(id); location.hash = '#/stats/' + id; } catch (x) { toast(x.message); }
  });
}

async function statsView(sid) {
  loading('stats');
  const ss = await api.sessions(), sel = sid && ss.find((s) => s.id === sid) ? sid : 'all';
  const d = ss.length ? await api.stats(sel) : null, sm = d && d.summary;
  app.innerHTML = shell('stats', `<div class="head"><div><h1>Statistics</h1><p class="sub">Review a completed session or your overall practice performance.</p></div>
    <div class="field" style="min-width:260px"><label for="v">View</label><select id="v"><option value="all">All sessions</option>${ss.map((s) => `<option value="${s.id}" ${s.id === sel ? 'selected' : ''}>${esc(s.sym)}, ${s.start} to ${s.end}</option>`).join('')}</select></div></div>
    ${d ? `<div class="stats"><div class="stat"><div class="label">Profit / loss</div><div class="v ${cls(d.pl)}">${signed(d.pl)}</div></div>
      <div class="stat"><div class="label">Win rate</div><div class="v">${pct(d.winRate)}</div></div>
      <div class="stat"><div class="label">Risk exposure</div><div class="v">${pct(d.exposure)}</div></div>
      <div class="stat"><div class="label">Trades</div><div class="v">${d.trades}</div></div></div>
      <div class="summary"><span class="muted">Session summary</span>${sel !== 'all' ? `<span>Ending cash <b>${money(sm.endingCash)}</b></span><span>Open position <b>${esc(sm.openPosition)}</b></span><span>Status <b>${esc(sm.status)}</b></span>` : `<span>Sessions <b>${sm.sessions}</b></span><span>Open positions <b>${sm.openPositions}</b></span>`}</div>
      <div class="actions"><a class="btn primary" href="#/journal">Review journal</a><a class="btn" href="#/feedback">View feedback</a><a class="btn ghost" href="#/dashboard">Return to dashboard</a></div>`
      : `<div class="panel empty"><h2>Nothing to review yet</h2><p>Statistics appear after your first practice session.</p><a class="btn primary" href="#/new">Start new session</a></div>`}`);
  $('#v')?.addEventListener('change', (e) => (location.hash = e.target.value === 'all' ? '#/stats' : '#/stats/' + e.target.value));
}

async function journalView(arg) {
  loading('journal');
  let q = '', selId = arg || null, editing = false;
  const all = (await api.trades()).slice().reverse();
  app.innerHTML = shell('journal', `<div class="head"><div><h1>Trade journal</h1><p class="sub">Browse, search, and edit the reasoning saved with each trade.</p></div></div>
    <form class="search" id="sf" style="margin-bottom:20px;max-width:520px"><div class="field" style="flex:1"><label for="sq">Search journal</label><input id="sq" type="search" placeholder="Instrument or text"></div><button class="btn" type="submit" style="align-self:end">Search</button></form>
    <div class="grid-2" style="grid-template-columns:minmax(0,5fr) minmax(0,7fr)"><div class="panel divide" id="lst" style="overflow:hidden"></div><div class="panel pad" id="det"></div></div>`);
  const paint = () => {
    const rows = all.filter((t) => !q || (t.sym + ' ' + t.reasoning + ' ' + t.id).toLowerCase().includes(q));
    $('#lst').innerHTML = rows.length ? rows.map((t) => `<button class="list-item" data-id="${t.id}" aria-selected="${t.id === selId}"><div class="li-top"><span>${esc(t.sym)} <span class="${t.side === 'buy' ? 'gain' : 'loss'}">${t.side === 'buy' ? 'Buy' : 'Sell'}</span></span><span class="mono">${qtyText(t.qty)} @ ${price(t.price)}</span></div><div class="li-sub">${t.ts} / ${t.id}</div></button>`).join('')
      : `<div class="empty"><h2>${all.length ? 'No matches' : 'No trades saved'}</h2><p>${all.length ? 'Try a different instrument or word.' : 'Trades and their reasoning appear here after you practice.'}</p>${all.length ? '' : '<a class="btn primary" href="#/new">Start new session</a>'}</div>`;
    const t = all.find((x) => x.id === selId);
    $('#det').innerHTML = t ? `<h2>${esc(t.sym)} ${t.side === 'buy' ? 'buy' : 'sale'}</h2>
      <div class="meta"><span>Trade <b>${t.id}</b></span><span>Session <b>${esc(t.sid)}</b></span><span>Time <b>${t.ts}</b></span><span>Quantity <b>${qtyText(t.qty)}</b></span><span>Price <b>${price(t.price)}</b></span>${t.pnl != null ? `<span>Result <b class="${cls(t.pnl)}">${signed(t.pnl)}</b></span>` : ''}</div>
      <form id="ef" novalidate><div class="field"><label for="rs">Reasoning</label><textarea id="rs" ${editing ? '' : 'readonly'} style="min-height:150px">${esc(t.reasoning)}</textarea></div><p class="err" id="err" role="alert" style="margin-top:10px"></p>
      <div style="display:flex;gap:10px;margin-top:18px">${editing ? '<button class="btn primary" type="submit">Save changes</button><button class="btn" type="button" data-act="cancel">Cancel edit</button>' : '<button class="btn" type="button" data-act="edit">Edit reasoning</button>'}</div></form>`
      : `<div class="empty"><h2>Select a trade</h2><p>Choose a trade from the list to view or edit its reasoning.</p></div>`;
  };
  paint();
  $('#sf').addEventListener('submit', (e) => { e.preventDefault(); q = $('#sq').value.trim().toLowerCase(); paint(); });
  $('#lst').addEventListener('click', (e) => { const b = e.target.closest('.list-item'); if (b) { selId = b.dataset.id; editing = false; paint(); } });
  $('#det').addEventListener('click', (e) => { const a = e.target.dataset.act; if (a === 'edit') { editing = true; paint(); $('#rs').focus(); } if (a === 'cancel') { editing = false; paint(); } });
  $('#det').addEventListener('submit', async (e) => { e.preventDefault(); const v = $('#rs').value.trim(); if (!v) return ($('#err').textContent = 'Reasoning cannot be empty.');
    try { await api.updateReasoning(selId, v); all.find((x) => x.id === selId).reasoning = v; editing = false; paint(); toast('Reasoning updated.'); } catch (x) { $('#err').textContent = x.message; } });
}

async function feedbackView() {
  loading('feedback');
  const d = await api.feedback();
  app.innerHTML = shell('feedback', `<div class="head"><div><h1>Behavior feedback</h1><p class="sub">Review trading habits and choose a metric to track.</p></div></div>
    <div class="grid-2" style="grid-template-columns:minmax(0,1fr) 360px"><section class="panel pad">${d.patterns.length ? d.patterns.map((p) => `<div class="pattern"><h2>${esc(p.title)}</h2><dl><dt>Explanation</dt><dd>${esc(p.explanation)}</dd><dt>Evidence</dt><dd>${p.tradeIds.map((i) => `<span class="chip">${esc(i)}</span>`).join('')}<div style="margin-top:6px">${esc(p.evidence)}</div></dd></dl><a class="btn small" style="margin-top:18px" href="#/journal/${esc(p.tradeIds[0])}">Review supporting trades in Journal</a></div>`).join('')
      : `<div class="empty"><h2>No feedback yet</h2><p>Complete a few practice sessions and Epoch will look for repeated habits.</p><a class="btn primary" href="#/new">Start new session</a></div>`}</section>
    <aside class="panel pad"><form id="mf"><div class="field"><label for="m">Habit or metric to track</label><select id="m"><option value="">Select a habit or metric</option>${d.metrics.map((m) => `<option value="${esc(m.key)}" ${m.key === d.tracked ? 'selected' : ''}>${esc(m.label)}</option>`).join('')}</select></div><button class="btn primary block" type="submit" style="margin-top:16px">Save selection</button></form>
    <div style="margin-top:26px"><h2>Trend across sessions</h2>${d.tracked && d.trend.length ? `<div class="trend">${d.trend.map((t) => `<div class="pt"><small>${esc(t.label)}</small>${esc(t.value)}</div>`).join('')}</div>` : '<p class="hint" style="margin-top:8px">Choose a metric above to follow it session by session.</p>'}</div></aside></div>`);
  $('#mf').addEventListener('submit', async (e) => { e.preventDefault(); const v = $('#m').value; if (!v) return toast('Select a habit or metric first.'); try { await api.saveTracked(v); toast('Saved. Your tracked metric was updated.'); feedbackView(); } catch (x) { toast(x.message); } });
}

function profileView() {
  const u = me();
  app.innerHTML = shell('profile', `<div class="head"><div><h1>Profile</h1><p class="sub">View and update your profile.</p></div></div>
    <form class="panel pad" id="pf" style="max-width:520px" novalidate><div class="field"><label for="n">Display name</label><input id="n" name="name" value="${esc(u.name)}"></div>
    <div class="field"><label for="e">Email</label><input id="e" name="email" type="email" value="${esc(u.email)}"></div>
    <p class="hint" style="margin-top:16px">Role: <b style="color:var(--text)">${u.role}</b></p><p class="err" id="err" role="alert" style="margin-top:10px"></p>
    <div style="display:flex;gap:10px;margin-top:22px"><button class="btn primary" type="submit">Save profile</button><a class="btn" href="#/dashboard">Cancel</a></div></form>`);
  $('#pf').addEventListener('submit', (e) => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.target)), err = $('#err'), em = f.email.trim().toLowerCase();
    if (!f.name.trim()) return (err.textContent = 'Enter a display name.'); if (!/^\S+@\S+\.\S+$/.test(em)) return (err.textContent = 'Enter a valid email address.');
    if (users.some((x) => x.email === em && x.id !== u.id)) return (err.textContent = 'That email is already in use.');
    u.name = f.name.trim(); u.email = em; saveUsers(); toast('Profile saved.'); });
}

async function adminView() {
  const u = me(); if (u.role !== 'Admin') return (location.hash = '#/dashboard');
  loading('admin');
  let find = '', pick = null;
  const [sets, usage] = await Promise.all([api.datasets(), api.usage()]);
  const setRows = (a) => a.map((d) => `<div style="padding:12px 0"><b>${esc(d.sym)}</b> <span class="muted mono">1D / ${esc(d.range)}</span> <span class="tag">${esc(d.status)}</span></div>`).join('');
  app.innerHTML = shell('admin', `<div class="head"><div><h1>Admin workspace</h1><p class="sub">Manage historical data and user accounts.</p></div></div>
    <div class="panel three" style="margin-bottom:28px"><div class="stat"><div class="label">Users</div><div class="v" id="cu"></div></div><div class="stat"><div class="label">Active sessions</div><div class="v">${usage.activeSessions}</div></div><div class="stat"><div class="label">Stored datasets</div><div class="v">${usage.datasets}</div></div></div>
    <div class="grid-2" style="grid-template-columns:1fr 1fr"><section class="panel pad"><h2 style="margin-bottom:16px">Historical market data</h2>
      <form id="df" novalidate><div class="field"><label for="di">Instrument</label><input id="di" list="dl" placeholder="Select or type a symbol"><datalist id="dl">${sets.map((i) => `<option value="${esc(i.sym)}">`).join('')}</datalist></div>
      <div class="field"><label for="dfile">Dataset file</label><input id="dfile" type="file" accept=".csv"><span class="hint">CSV with columns date, open, high, low, close. One row per day.</span></div><p class="err" id="derr" role="alert" style="margin-top:10px"></p>
      <button class="btn primary" type="submit" style="margin-top:16px">Import dataset</button></form>
      <div class="divide" id="dsl" style="margin-top:24px">${setRows(sets)}</div></section>
    <section class="panel pad"><h2 style="margin-bottom:16px">User accounts</h2><div class="field"><label for="uf">Find a user</label><input id="uf" placeholder="Email or display name"></div><div class="divide panel" id="ul" style="margin-top:14px;overflow:hidden"></div>
      <form id="uef" style="margin-top:18px" novalidate><div class="row"><div class="field"><label for="ur">Role</label><select id="ur"><option>Trader</option><option>Admin</option></select></div><div class="field"><label for="us">Status</label><select id="us"><option>Active</option><option>Disabled</option></select></div></div>
      <p class="err" id="uerr" role="alert" style="margin-top:10px"></p><button class="btn primary" type="submit" style="margin-top:16px" id="usv" disabled>Save user</button></form></section></div>`);
  $('#cu').textContent = users.length;
  const ulist = () => { const f = find.toLowerCase(), us = users.filter((x) => !f || (x.email + x.name).toLowerCase().includes(f));
    $('#ul').innerHTML = us.length ? us.map((x) => `<button class="list-item" data-id="${x.id}" aria-selected="${x.id === pick}"><div class="li-top"><span>${esc(x.name)}</span><span class="muted">${x.role} / ${x.status}</span></div><div class="li-sub">${esc(x.email)}</div></button>`).join('') : '<div class="empty" style="padding:28px">No users match.</div>'; };
  ulist();
  $('#uf').addEventListener('input', (e) => { find = e.target.value.trim(); ulist(); });
  $('#ul').addEventListener('click', (e) => { const b = e.target.closest('.list-item'); if (!b) return; pick = b.dataset.id; const x = users.find((y) => y.id === pick); $('#ur').value = x.role; $('#us').value = x.status; $('#usv').disabled = false; ulist(); });
  $('#uef').addEventListener('submit', (e) => { e.preventDefault(); const x = users.find((y) => y.id === pick), err = $('#uerr'); err.textContent = ''; if (!x) return;
    if (x.id === u.id && ($('#ur').value !== 'Admin' || $('#us').value !== 'Active')) return (err.textContent = 'You cannot demote or disable your own account.');
    x.role = $('#ur').value; x.status = $('#us').value; saveUsers(); ulist(); toast('User saved.'); });
  $('#df').addEventListener('submit', async (e) => { e.preventDefault(); const err = $('#derr'); err.textContent = ''; const sym = $('#di').value.trim().toUpperCase(), file = $('#dfile').files[0];
    if (!sym) return (err.textContent = 'Select or type an instrument.'); if (!file) return (err.textContent = 'Choose a CSV file to import.');
    try { await api.importDataset(sym, file); toast('Import request sent for ' + sym + '.'); } catch (x) { err.textContent = x.message; } });
}

/* ---------- router ---------- */
function route() {
  cleanup && cleanup(); cleanup = null;
  const [, page = '', arg] = location.hash.split('/'), u = me();
  if (!u) { if (page === 'signup') return authView('signup'); return authView('signin'); }
  if (u.role === 'Admin') return adminView().catch(failed);
  if (page === 'signin' || page === 'signup' || page === '') return (location.hash = '#/dashboard');
  window.scrollTo(0, 0);
  const view = ({ dashboard: dashboardView, new: newView, practice: practiceRedirect, replay: () => replayView(arg), stats: () => statsView(arg), journal: () => journalView(arg), feedback: feedbackView, profile: profileView, admin: () => (location.hash = '#/dashboard') }[page] || dashboardView)();
  if (view && view.catch) view.catch(failed);
}
addEventListener('hashchange', route);
document.addEventListener('click', (e) => {
  const a = e.target.closest('[data-act]'); if (!a) return;
  if (a.dataset.act === 'signout') { setMe(null); location.hash = '#/signin'; route(); }
  if (a.dataset.act === 'theme') { const root = document.documentElement, dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches; root.dataset.theme = dark ? 'light' : 'dark'; try { localStorage.setItem('epoch.theme', root.dataset.theme); } catch (x) {} route(); }
});

/* ---------- cursor interaction (fine pointers only, off under reduced motion) ---------- */
if (matchMedia('(hover: hover) and (pointer: fine)').matches && !reduceMotion) {
  const root = document.documentElement; let raf = 0, ev = null;
  document.addEventListener('pointermove', (e) => {
    ev = e; if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0; root.style.setProperty('--cx', ev.clientX + 'px'); root.style.setProperty('--cy', ev.clientY + 'px');
      const t = ev.target.closest && ev.target.closest('.panel, .stat, .list-item, .btn');
      if (t) { const r = t.getBoundingClientRect(); t.style.setProperty('--mx', ev.clientX - r.left + 'px'); t.style.setProperty('--my', ev.clientY - r.top + 'px'); }
      const m = ev.target.closest && ev.target.closest('.btn.primary');
      document.querySelectorAll('.btn.primary.pulled').forEach((b) => { if (b !== m) { b.classList.remove('pulled'); b.style.transform = ''; } });
      if (m && !m.disabled) { const r = m.getBoundingClientRect(); m.classList.add('pulled'); m.style.transform = 'translate(' + ((ev.clientX - r.left - r.width / 2) * 0.12).toFixed(1) + 'px,' + ((ev.clientY - r.top - r.height / 2) * 0.22).toFixed(1) + 'px)'; }
    });
  }, { passive: true });
  root.classList.add('fx');
}
route();
})();
