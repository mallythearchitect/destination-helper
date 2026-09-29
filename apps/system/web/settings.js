/* Settings page. Renders itself from GET /v1/settings (the registry), saves
   each field on change with the version it last saw, shows both versions on a
   conflict, and lists History with Undo. No framework: one file, plain JS. */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const act = App.act('settings');
const ZONES = ['America/New_York','America/Chicago','America/Denver','America/Los_Angeles','America/Toronto','Europe/London','Europe/Paris','Asia/Dubai','Asia/Shanghai','Asia/Tokyo','UTC'];

const STATE = { sections: [], byKey: {} };

// ---------- rendering ----------------------------------------------------
function control(s) {
  const v = s.value, id = 'f-' + s.key.replace(/\./g, '-');
  switch (s.type) {
    case 'text': return `<input type="text" id="${id}" value="${esc(v)}">`;
    case 'time': return `<input type="time" id="${id}" value="${esc(v)}">`;
    case 'time_zone': return `<input type="text" id="${id}" list="tz" value="${esc(v)}"><datalist id="tz">${ZONES.map(z => `<option value="${z}">`).join('')}</datalist>`;
    case 'integer': case 'number':
      return `<span class="row"><input type="${s.type === 'integer' ? 'number' : 'text'}" id="${id}" value="${esc(v)}" ${s.min != null ? `min="${s.min}"` : ''} ${s.max != null ? `max="${s.max}"` : ''} ${s.type === 'integer' ? 'step="1"' : ''}>${s.unit ? `<span class="muted">${esc(s.unit)}${s.unit === 'cents' ? ` = $${(v / 100).toFixed(2)}` : ''}</span>` : ''}</span>`;
    case 'select': return `<select id="${id}">${s.options.map(o => `<option ${o === v ? 'selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
    case 'toggle': return `<label class="checks"><input type="checkbox" id="${id}" ${v ? 'checked' : ''}> ${v ? 'On' : 'Off'}</label>`;
    case 'multiselect': return `<div class="checks" id="${id}">${s.options.map(o => `<label><input type="checkbox" value="${esc(o)}" ${v.includes(o) ? 'checked' : ''}>${esc(o)}</label>`).join('')}</div>`;
    case 'list': return `<textarea id="${id}" placeholder="one per line">${esc(v.join('\n'))}</textarea>`;
    case 'map': return `<textarea id="${id}" placeholder="bank = account">${esc(Object.entries(v).map(([k, x]) => `${k} = ${x}`).join('\n'))}</textarea>`;
    case 'place': return `<span class="row" id="${id}"><input type="text" data-p="name" value="${esc(v.name)}" placeholder="City, ST" style="max-width:220px"><input type="text" data-p="lat" value="${v.lat}" placeholder="lat"><input type="text" data-p="lon" value="${v.lon}" placeholder="lon"></span>`;
    case 'sources': return `<table class="t" id="${id}"><tr><th>Source</th><th>On</th><th>Refresh</th></tr>${v.map((r, i) => `<tr data-i="${i}" data-id="${esc(r.id)}" data-label="${esc(r.label)}"><td>${esc(r.label)}</td><td><input type="checkbox" ${r.on ? 'checked' : ''}></td><td><select>${s.options.map(o => `<option ${o === r.refresh ? 'selected' : ''}>${o}</option>`).join('')}</select></td></tr>`).join('')}</table>`;
    case 'jobs': return `<table class="t" id="${id}"><tr><th>Job</th><th>Model</th><th>Backup</th></tr>${s.extra.jobs.map(([j, lbl]) => `<tr data-job="${j}"><td>${esc(lbl)}</td><td><select data-k="model">${s.options.map(o => `<option ${o === v[j]?.model ? 'selected' : ''}>${o}</option>`).join('')}</select></td><td><select data-k="fallback">${s.options.map(o => `<option ${o === v[j]?.fallback ? 'selected' : ''}>${o}</option>`).join('')}</select></td></tr>`).join('')}</table>`;
    case 'visibility': return `<table class="t" id="${id}"><tr><th>Data</th><th>May be seen by</th></tr>${s.extra.scopes.map(([k, lbl]) => `<tr data-scope="${k}"><td>${esc(lbl)}</td><td><select>${s.options.map(o => `<option ${o === v[k] ? 'selected' : ''}>${o === 'cloud' ? 'cloud: any model' : o === 'local' ? 'local: only a model on this machine' : 'none: no model'}</option>`).join('')}</select></td></tr>`).join('')}</table>`;
    default: return `<textarea id="${id}" style="min-height:${Math.min(360, 40 + JSON.stringify(v, null, 1).split('\n').length * 18)}px;max-width:640px">${esc(JSON.stringify(v, null, 1))}</textarea>`;
  }
}
function readControl(s) {
  const id = 'f-' + s.key.replace(/\./g, '-'), el = document.getElementById(id);
  const num = x => { const n = Number(String(x).trim()); if (String(x).trim() === '' || Number.isNaN(n)) throw new Error('not a number'); return n; };
  switch (s.type) {
    case 'text': case 'time': case 'time_zone': case 'select': return el.value.trim();
    case 'integer': return Math.trunc(num(el.value));
    case 'number': return num(el.value);
    case 'toggle': return el.checked;
    case 'multiselect': return [...el.querySelectorAll('input:checked')].map(i => i.value);
    case 'list': return el.value.split('\n').map(x => x.trim()).filter(Boolean);
    case 'map': { const o = {}; el.value.split('\n').forEach(l => { if (!l.trim()) return; const [k, ...r] = l.split('='); if (!r.length) throw new Error(`"${l.trim()}" needs an =`); o[k.trim()] = r.join('=').trim(); }); return o; }
    case 'place': return { name: el.querySelector('[data-p=name]').value.trim(), lat: num(el.querySelector('[data-p=lat]').value), lon: num(el.querySelector('[data-p=lon]').value) };
    case 'sources': return [...el.querySelectorAll('tr[data-i]')].map(tr => ({ id: tr.dataset.id, label: tr.dataset.label, on: tr.querySelector('input').checked, refresh: tr.querySelector('select').value }));
    case 'jobs': { const o = {}; el.querySelectorAll('tr[data-job]').forEach(tr => { o[tr.dataset.job] = { model: tr.querySelector('[data-k=model]').value, fallback: tr.querySelector('[data-k=fallback]').value }; }); return o; }
    case 'visibility': { const o = {}; el.querySelectorAll('tr[data-scope]').forEach(tr => { o[tr.dataset.scope] = tr.querySelector('select').value.split(':')[0]; }); return o; }
    default: try { return JSON.parse(el.value); } catch (e) { throw new Error('not valid JSON: ' + e.message); }
  }
}
function fieldHTML(s) {
  return `<div class="setting" data-key="${s.key}">
    <label class="lbl">${esc(s.label)}<span class="state" data-state></span></label>
    <div>${control(s)}
      ${s.help ? `<div class="help">${esc(s.help)}</div>` : ''}
      ${s.extra && s.extra.used_by ? `<div class="help" style="margin-top:-6px">Read by: <span class="mono">${esc(s.extra.used_by.join(', '))}</span></div>` : ''}
      <div class="meta" data-meta>${metaText(s)}</div>
      <div data-conflict></div>
    </div></div>`;
}
function metaText(s) {
  return s.stored ? `Changed ${fmtWhen(s.updated_at)} by ${esc(s.updated_by)} · v${s.version}<a href="#" data-reset="${s.key}">Reset to default</a>` : 'Default';
}
function secretHTML(x) {
  return `<div class="setting secret" data-secret="${x.name}">
    <label class="lbl">${esc(x.label)}</label>
    <div><span class="row"><span class="status ${x.set ? 'set' : 'unset'}" data-status>${x.set ? '● Set' : '○ Not set'}</span>
      <input type="password" autocomplete="off" placeholder="${x.set ? 'paste a new key to replace it' : 'paste the key'}" style="max-width:300px">
      <button class="sbtn" data-act="set">Save key</button>${x.set ? '<button class="sbtn" data-act="clear">Clear</button>' : ''}</span>
      <div class="help">${esc(x.help)} Stored in <span class="mono">.env</span> on this computer, never in the vault or git.</div>
    </div></div>`;
}
function render() {
  const nav = $('#nav'), content = $('#content');
  const secs = STATE.sections;
  nav.innerHTML = secs.map(s => `<a href="#${s.id}">${esc(s.label)}</a>`).join('') + `<a href="#backups-panel">Backups</a><a href="#history">History</a>`;
  const GROUP = { trips: 'Trips', destinations: 'Destinations', ai: 'AI', records: 'Records', sources: 'Sources', backup: 'Backups', limits: 'Engine' };
  const grouped = sec => { const g = {}; sec.settings.forEach(s => { const k = s.key.split('.')[1]; (g[k] = g[k] || []).push(s); }); return Object.entries(g).map(([k, list]) => `<h3 style="font-size:16px;margin:16px 0 2px;color:var(--gold)">${esc(GROUP[k] || k)}</h3>${list.map(fieldHTML).join('')}`).join(''); };
  content.innerHTML = secs.map(sec => `<section class="sec" id="${sec.id}"><h2>${esc(sec.label)}</h2><p class="blurb">${esc(sec.blurb)}</p>
     ${sec.id === 'logic' ? grouped(sec) : sec.settings.map(fieldHTML).join('')}${sec.secrets.map(secretHTML).join('')}
     ${sec.id === 'backup' ? backupPanelShell() : ''}</section>`).join('')
    + `<section class="sec" id="history"><h2>History</h2><p class="blurb">Every change, newest first. Undo puts a setting back the way it was; the undo is itself a change, so it can be undone too.</p>
       ${downloadPanel()}<ul class="hist" id="hist"></ul></section>`;
  secs.forEach(sec => sec.settings.forEach(s => { STATE.byKey[s.key] = s; }));
  content.querySelectorAll('.setting[data-key]').forEach(f => f.addEventListener('change', () => save(f.dataset.key)));
  content.addEventListener('click', onClick);
  content.addEventListener('change', ev => { if (ev.target.id === 'dl-range') $('#dl-custom').hidden = ev.target.value !== 'custom'; });
  applyTheme();
  loadHistory(); loadBackups();
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { nav.querySelectorAll('a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id)); } }), { rootMargin: '-10% 0px -80% 0px' });
  content.querySelectorAll('section.sec').forEach(s => io.observe(s));
}
function applyTheme() {
  const t = STATE.byKey['display.theme']?.value || 'dark';
  const dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
}

// ---------- saving ------------------------------------------------------
async function save(key, force) {
  const s = STATE.byKey[key], f = $(`.setting[data-key="${key}"]`), st = f.querySelector('[data-state]');
  let value;
  try { value = readControl(s); } catch (e) { st.className = 'state err'; st.textContent = e.message; return; }
  st.className = 'state saving'; st.textContent = 'saving…';
  try {
    const r = await api('PUT', `/v1/settings/${key}`, { value, version: force ?? s.version });
    Object.assign(s, r); st.className = 'state saved'; st.textContent = 'saved';
    f.querySelector('[data-meta]').innerHTML = metaText(s); f.querySelector('[data-conflict]').innerHTML = '';
    if (key === 'display.theme') applyTheme();
    if (key.startsWith('backup.')) loadBackups();
    loadHistory();
  } catch (e) {
    if (e.status === 409) {
      const d = e.detail, box = f.querySelector('[data-conflict]');
      box.innerHTML = `<div class="conflict"><b>Saved elsewhere first.</b> Another window changed this ${fmtWhen(d.theirs.updated_at)} (by ${esc(d.theirs.updated_by || 'unknown')}).<br>
        Theirs: <code>${esc(JSON.stringify(d.theirs.value))}</code><br>Yours: <code>${esc(JSON.stringify(d.yours.value))}</code><br>
        <span class="row" style="margin-top:6px"><button class="sbtn" data-keep="theirs" data-key="${key}">Keep theirs</button><button class="sbtn gold" data-keep="mine" data-key="${key}" data-version="${d.theirs.version}">Use mine</button></span></div>`;
      st.className = 'state err'; st.textContent = 'conflict';
    } else { st.className = 'state err'; st.textContent = e.message; toast('Not saved: ' + e.message, 4000); }
  }
}
async function reload() {
  const d = await api('GET', '/v1/settings'); STATE.sections = d.sections; render();
}
async function onClick(ev) {
  const t = ev.target.closest('a[data-reset],button[data-keep],button[data-act],button[data-undo],button[data-bk],button[data-dl]');
  if (!t) return;
  ev.preventDefault();
  try {
    if (t.hasAttribute('data-dl')) { downloadHistory(); return; }
    if (t.dataset.reset) { await api('DELETE', `/v1/settings/${t.dataset.reset}`); toast('Back to default'); await reload(); }
    else if (t.dataset.keep === 'theirs') { await reload(); }
    else if (t.dataset.keep === 'mine') { await save(t.dataset.key, Number(t.dataset.version)); }
    else if (t.dataset.act) {
      const f = t.closest('[data-secret]'), name = f.dataset.secret, inp = f.querySelector('input');
      if (t.dataset.act === 'set') { if (!inp.value.trim()) { toast('Paste the key first'); return; } await api('PUT', `/v1/secrets/${name}`, { value: inp.value }); inp.value = ''; toast('Key saved to .env'); }
      else { if (!confirm(`Clear ${name}?`)) return; await api('DELETE', `/v1/secrets/${name}`); toast('Key cleared'); }
      await reload();
    }
    else if (t.dataset.undo) { await api('POST', `/v1/history/${t.dataset.undo}/undo`); toast('Undone'); await reload(); }
    else if (t.dataset.bk) await backupAction(t);
  } catch (e) { toast(e.message, 4000); }
}

// ---------- history download ----------------------------------------------
// Each option is one row here; add a row and the form grows. The engine takes
// since / until / key / tbl / app / format (GET /v1/history/export).
const RANGES = [
  ['all', 'All time', () => ({})],
  ['7d', 'Last 7 days', () => ({ since: daysAgo(7) })],
  ['30d', 'Last 30 days', () => ({ since: daysAgo(30) })],
  ['year', 'This year', () => ({ since: new Date().getFullYear() + '-01-01' })],
  ['custom', 'Pick dates…', null],
];
const daysAgo = n => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
function downloadPanel() {
  const keys = Object.values(STATE.byKey).length ? Object.values(STATE.byKey) : STATE.sections.flatMap(s => s.settings);
  return `<div class="dl" id="dl">
    <span class="row">
      <label>Range <select id="dl-range">${RANGES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
      <span id="dl-custom" hidden><input type="date" id="dl-from" title="from"> <span class="muted">to</span> <input type="date" id="dl-to" title="to"></span>
      <label>Setting <select id="dl-key"><option value="">every setting</option>${keys.map(s => `<option value="${s.key}">${esc(s.label)}</option>`).join('')}</select></label>
      <label>Format <select id="dl-format"><option value="json">JSON</option><option value="csv">CSV (opens in Excel)</option></select></label>
      <button class="sbtn gold" data-dl>Download</button>
    </span>
    <div class="help">Downloads a file of the changes you chose. All time with every setting is the complete record. More choices will appear here as the apps grow.</div>
  </div>`;
}
function downloadHistory() {
  const range = $('#dl-range').value, key = $('#dl-key').value, format = $('#dl-format').value;
  let q;
  if (range === 'custom') {
    q = {}; if ($('#dl-from').value) q.since = $('#dl-from').value; if ($('#dl-to').value) q.until = $('#dl-to').value;
    if (!q.since && !q.until) { toast('Pick a from or to date'); return; }
  } else q = RANGES.find(r => r[0] === range)[2]();
  if (key) q.key = key;
  q.format = format;
  location.href = '/v1/history/export?' + new URLSearchParams(q).toString();
  toast('Downloading…');
}

// ---------- history -------------------------------------------------------
async function loadHistory() {
  const h = await api('GET', '/v1/history?limit=40');
  const label = k => STATE.byKey[k]?.label || k;
  const show = v => v == null ? '<i>none</i>' : `<code>${esc(JSON.stringify(v.value))}</code>`;
  $('#hist').innerHTML = h.length ? h.map(e => `<li class="${e.undone_by ? 'undone' : ''}"><div><div><b>${esc(label(e.row_key))}</b> · ${e.action.replace('settings.', '').replace('history.', '')} <span class="when">${fmtWhen(e.ts)} · ${esc(e.app)}</span></div><div>${show(e.before)} → ${show(e.after)}</div></div><div>${e.undone_by ? '<span class="muted">undone</span>' : `<button class="sbtn" data-undo="${e.id}">Undo</button>`}</div></li>`).join('')
    : '<li class="muted">No changes yet.</li>';
}

// ---------- backups -------------------------------------------------------
function backupPanelShell() {
  return `<div id="backups-panel" style="padding-top:14px;border-top:1px solid var(--line)">
    <div class="row"><button class="sbtn gold" data-bk="make">Back up now</button><button class="sbtn" data-bk="test">Run the restore test</button><span class="muted" id="bk-next"></span></div>
    <div class="help" style="margin-top:8px">A backup is a copy of the vault. The restore test opens the newest copy, checks it, and compares every setting with the live vault, which proves it can be read back. Restoring replaces the vault with a copy; a safety backup is taken first.</div>
    <ul id="bk-list"></ul><div class="log" id="bk-log"></div></div>`;
}
async function loadBackups() {
  if (!$('#bk-list')) return;
  const d = await api('GET', '/v1/backups');
  $('#bk-next').textContent = `Nightly at ${STATE.byKey['backup.time']?.value}, next ${fmtWhen(d.next_run)} · ${d.destination}`;
  $('#bk-list').innerHTML = d.backups.length ? d.backups.map(b => `<li><span class="mono">${esc(b.file)}</span><span class="muted">${(b.bytes / 1024).toFixed(0)} KB · ${fmtWhen(b.modified)}</span><button class="sbtn" data-bk="test" data-file="${esc(b.file)}">Test</button><button class="sbtn danger" data-bk="restore" data-file="${esc(b.file)}">Restore</button></li>`).join('') : '<li class="muted">No backups yet.</li>';
  $('#bk-log').innerHTML = d.log.slice(0, 8).map(l => `<div><span class="${l.ok ? 'ok' : 'bad'}">${l.ok ? '✓' : '✗'}</span> ${esc(l.kind.replace('_', ' '))} ${l.file ? `<span class="mono">${esc(l.file)}</span>` : ''} · ${fmtWhen(l.ts)}${l.detail && l.detail.changed_since_backup ? ` · ${l.detail.rows_in_backup} rows, ${l.detail.changed_since_backup.length} changed since` : ''}${typeof l.detail === 'string' ? ' · ' + esc(l.detail) : ''}</div>`).join('');
}
async function backupAction(t) {
  const file = t.dataset.file;
  if (t.dataset.bk === 'make') { const r = await api('POST', '/v1/backups'); toast(`Backed up: ${r.file}`); }
  else if (t.dataset.bk === 'test') { const r = await api('POST', '/v1/backups/restore-test' + (file ? `?file=${encodeURIComponent(file)}` : '')); toast(r.ok ? `Restore test passed: ${r.rows_in_backup} settings read back from ${r.file}` : `Restore test failed: ${r.reason || r.integrity}`, 4000); }
  else if (t.dataset.bk === 'restore') {
    if (!confirm(`Replace the live vault with ${file}?\nA safety backup is taken first. Changes made since this backup will be gone (but in the safety copy).`)) return;
    const r = await api('POST', '/v1/backups/restore', { file, confirm: true }); toast(`Restored ${r.restored}. Safety copy: ${r.safety_backup}`, 5000); await reload(); return;
  }
  await loadBackups();
}

// ---------- boot ----------------------------------------------------------
(async () => {
  try {
    const h = await api('GET', '/v1/health'); const p = $('#health'); p.className = 'pill ok'; p.innerHTML = `engine <b>ok</b> · ${h.settings_stored} saved`;
    await reload();
    if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  } catch (e) { const p = $('#health'); p.className = 'pill bad'; p.innerHTML = 'engine <b>down</b>'; $('#content').innerHTML = `<p>The engine isn't running. Start it with <span class="mono">scripts/dev.sh</span> and reload.</p>`; }
})();
