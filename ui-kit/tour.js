/* The guided tour and the "Go to" menu, shared by every page.
   A page calls Tour.init({ page: 'trips', steps: [...] }). Each step:
   { target: '#css', title, text, before: fn? , tab: 'bills'? }. The tour
   starts by itself the first time a page opens (remembered per browser),
   and again from the "? Tour" button. "Go to" lists every page. */
(function () {
  'use strict';
  const PAGES = [
    ['Home', '/apps/launcher/web/', 'your trips at a glance, what is coming up, the apps'],
    ['Trips', '/apps/trips/web/', 'plan a trip, check the plan, prepare, run it live'],
    ['Destinations', '/apps/destinations/web/', 'places scored with sources, your shortlist, trip cost'],
    ['History', '/apps/system/web/browse.html', 'every trip, place and note you have kept', { dev: 'Browse', devDesc: 'every record: find, link, tag, note, attach, undo' }],
    ['Settings', '/apps/system/web/settings.html', 'home city, time zone, appearance, keys', { devDesc: 'profile, keys, display, AI, backups, every rule as data, history' }],
    ['AI inbox', '/apps/ai/web/', 'suggestions waiting for your OK, models, spend, test scores', { devOnly: true }],
  ];
  const pages = () => { const dev = document.body.classList.contains('mode-dev'); return PAGES.filter(([, , , o]) => dev || !(o && o.devOnly)).map(([n, h, d, o]) => [dev && o && o.dev ? o.dev : n, h, dev && o && o.devDesc ? o.devDesc : d]); };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
  let cfg = null, i = 0, els = null;

  function mountButtons() {
    const right = document.querySelector('.appbar-right');
    if (!right || document.getElementById('tour-go')) return;
    const go = document.createElement('button'); go.id = 'tour-go'; go.className = 'tour-btn'; go.textContent = '☰ Go to'; go.title = 'Jump to any page';
    const help = document.createElement('button'); help.id = 'tour-help'; help.className = 'tour-btn'; help.textContent = '? Tour'; help.title = 'Walk me through this page';
    right.prepend(help); right.prepend(go);
    go.onclick = openMenu; help.onclick = () => start(0);
  }
  function openMenu() {
    let m = document.getElementById('tour-menu');
    if (m) { m.remove(); return; }
    m = document.createElement('div'); m.id = 'tour-menu';
    m.innerHTML = `<div class="tour-menu-in"><div class="tour-menu-head"><b>Go to</b><button class="tour-x" data-close>×</button></div>
      ${pages().map(([n, h, d]) => `<a href="${h}" class="${location.pathname.startsWith(h) ? 'on' : ''}"><b>${esc(n)}</b><span>${esc(d)}</span></a>`).join('')}
      <div class="tour-menu-foot"><button class="tour-btn" data-tour>? Tour this page</button><a href="https://github.com/mallythearchitect/destination-helper/blob/main/docs/how-it-works.md" target="_blank" class="tour-btn">Read the guide</a></div></div>`;
    document.body.appendChild(m);
    m.addEventListener('click', e => { if (e.target === m || e.target.closest('[data-close]')) m.remove(); if (e.target.closest('[data-tour]')) { m.remove(); start(0); } });
  }

  function ui() {
    if (els) return els;
    const dim = document.createElement('div'); dim.id = 'tour-dim';
    const spot = document.createElement('div'); spot.id = 'tour-spot';
    const card = document.createElement('div'); card.id = 'tour-card';
    document.body.append(dim, spot, card);
    dim.onclick = end;
    card.addEventListener('click', e => {
      if (e.target.closest('[data-next]')) show(i + 1);
      else if (e.target.closest('[data-back]')) show(i - 1);
      else if (e.target.closest('[data-end]')) end();
    });
    document.addEventListener('keydown', e => { if (!cfg || !document.body.classList.contains('touring')) return; if (e.key === 'Escape') end(); if (e.key === 'ArrowRight' || e.key === 'Enter') show(i + 1); if (e.key === 'ArrowLeft') show(i - 1); });
    window.addEventListener('resize', () => { if (document.body.classList.contains('touring')) place(); });
    return (els = { dim, spot, card });
  }
  function start(at) { if (!cfg || !cfg.steps.length) return; ui(); document.body.classList.add('touring'); show(at || 0); }
  function end() { document.body.classList.remove('touring'); store.set('tour.done.' + cfg.page, '1'); }
  async function show(n) {
    if (n < 0) n = 0;
    if (n >= cfg.steps.length) return end();
    i = n;
    const s = cfg.steps[i];
    if (s.before) { try { await s.before(); } catch (e) {} }
    await new Promise(r => setTimeout(r, s.before ? 250 : 0));
    const t = s.target ? document.querySelector(s.target) : null;
    if (s.target && !t) return show(n + (n >= i ? 1 : -1));   // skip steps whose target isn't on screen right now
    const { card } = ui();
    card.innerHTML = `<div class="tour-step">${i + 1} of ${cfg.steps.length}</div><h3>${esc(s.title)}</h3><p>${s.text}</p>
      <div class="tour-actions"><button class="tour-btn" data-end>Skip</button><span style="flex:1"></span>${i > 0 ? '<button class="tour-btn" data-back>‹ Back</button>' : ''}<button class="tour-btn gold" data-next>${i + 1 === cfg.steps.length ? 'Done' : 'Next ›'}</button></div>`;
    if (t) t.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setTimeout(place, t ? 350 : 0);
  }
  function place() {
    const s = cfg.steps[i], { spot, card } = ui();
    const t = s.target ? document.querySelector(s.target) : null;
    if (!t) { spot.style.display = 'none'; card.style.top = '50%'; card.style.left = '50%'; card.style.transform = 'translate(-50%,-50%)'; return; }
    const r = t.getBoundingClientRect(), pad = 6;
    spot.style.display = 'block'; spot.style.transform = 'none';
    Object.assign(spot.style, { top: (r.top - pad + window.scrollY) + 'px', left: (r.left - pad + window.scrollX) + 'px', width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px' });
    card.style.transform = 'none';
    const cw = Math.min(360, window.innerWidth - 24), ch = card.offsetHeight || 180;
    let top = r.bottom + 12 + window.scrollY, left = Math.max(12, Math.min(r.left + window.scrollX, window.innerWidth - cw - 12));
    if (r.bottom + ch + 24 > window.innerHeight) top = Math.max(12 + window.scrollY, r.top - ch - 12 + window.scrollY);
    if (r.bottom + ch + 24 > window.innerHeight && r.top - ch - 12 < 0) { top = window.scrollY + window.innerHeight - ch - 12; }
    card.style.top = top + 'px'; card.style.left = left + 'px'; card.style.width = cw + 'px';
  }

  window.Tour = {
    init(c) {
      cfg = c;
      const go = () => { mountButtons(); if (!store.get('tour.done.' + c.page) && !c.noAuto) setTimeout(() => start(0), 700); };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
    },
    start, end,
  };
})();
