/* ---- The shared helpers every page uses, once. Load before the page's own script.
   App.$, App.esc, App.toast, App.api, App.act(app), App.money, App.fmtD, App.fmtWhen,
   App.tabs({...}), App.detail(title, html), App.remember(key, value?), App.down(), App.isDev(), App.onMode(fn). */
(function () {
  'use strict';
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let toastT;
  function toast(msg, ms = 2600) {
    let t = $('#toast'); if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), ms);
  }
  async function api(method, path, body, raw) {
    const opts = { method };
    if (raw) opts.body = body; else if (body !== undefined) { opts.headers = { 'content-type': 'application/json' }; opts.body = JSON.stringify(body); }
    const r = await fetch(path, opts);
    const data = r.status === 204 ? null : await r.json().catch(() => null);
    if (!r.ok) { const e = new Error((data && (data.detail?.message || data.detail)) || r.statusText); e.status = r.status; e.detail = data && data.detail; throw e; }
    return data;
  }
  const act = app => (name, payload) => api('POST', `/v1/actions/${name}`, { ...payload, app });
  const $$ = (n, d = 0) => n == null ? '—' : (n < 0 ? '-' : '') + '$' + (Math.abs(n) / 100).toLocaleString([], { minimumFractionDigits: d, maximumFractionDigits: d });
  const money = n => $$(n, 2), money0 = n => $$(n, 0);
  const fmtD = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString([], { month: 'short', day: 'numeric' }) : '';
  const fmtWhen = iso => iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '';
  const remember = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
  /* Sidebar tabs: nav = '#tabs' with <a href="#id">, panels = '#p-<id>', render = { id: fn }. */
  function tabs({ nav = '#tabs', render, names, onShow }) {
    const list = names || Object.keys(render);
    function show(t) {
      if (!list.includes(t)) t = list[0];
      location.hash = t;
      document.querySelectorAll(nav + ' a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + t));
      document.querySelectorAll('.panel').forEach(p => p.classList.toggle('on', p.id === 'p-' + t));
      if (onShow) onShow(t);
      return render[t] && render[t]();
    }
    $(nav).addEventListener('click', e => { const a = e.target.closest('a'); if (!a) return; e.preventDefault(); show(a.getAttribute('href').slice(1)); });
    return show;
  }
  function detail(title, html) {
    let d = $('#detail');
    if (!d) { d = document.createElement('dialog'); d.className = 'detail-dialog'; d.id = 'detail'; d.innerHTML = '<button class="close" id="detail-close">Close</button><div id="detail-body"></div>'; document.body.appendChild(d); $('#detail-close').onclick = () => d.close(); }
    $('#detail-body').innerHTML = `<h2>${title}</h2>${html}`; d.showModal(); return d;
  }
  const down = (sel, msg) => { const el = $(sel); if (el) el.innerHTML = `<p>${msg || "The engine isn't running. Start it with <span class=\"mono\">scripts/dev.sh</span> and reload."}</p>`; };
  /* User / Developer mode. User mode is the app as a traveller sees it; Developer mode
     shows the engine behind it (workflows, tracking, the AI inbox, rule codes, Logic).
     Anything with class="dev-only" is hidden in user mode; pages re-render on 'modechange'. */
  const MODE_KEY = 'dh.mode';
  const mode = () => remember(MODE_KEY) || 'user';
  const isDev = () => mode() === 'dev';
  function applyMode() {
    document.body.classList.toggle('mode-dev', isDev()); document.body.classList.toggle('mode-user', !isDev());
    const sw = $('#mode-switch'); if (sw) sw.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.mode === mode()));
    document.querySelectorAll('[data-user-label]').forEach(el => { el.textContent = isDev() ? (el.dataset.devLabel || el.dataset.userLabel) : el.dataset.userLabel; });
  }
  function setMode(m) { remember(MODE_KEY, m); applyMode(); document.dispatchEvent(new CustomEvent('modechange', { detail: m })); }
  function mountMode() {
    const right = $('.appbar-right'); if (!right || $('#mode-switch')) return;
    const sw = document.createElement('div'); sw.id = 'mode-switch'; sw.className = 'mode-switch'; sw.title = 'User mode shows the app as a traveller sees it. Developer mode shows the engine behind it.';
    sw.innerHTML = '<button data-mode="user">User</button><button data-mode="dev">Developer</button>';
    right.appendChild(sw); sw.onclick = e => { const b = e.target.closest('[data-mode]'); if (b) setMode(b.dataset.mode); };
    applyMode();
  }
  applyMode();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountMode); else mountMode();
  const onMode = fn => document.addEventListener('modechange', e => fn(e.detail));
  window.App = { $, esc, toast, api, act, money, money0, fmtD, fmtWhen, remember, tabs, detail, down, mode, isDev, setMode, onMode };
})();
