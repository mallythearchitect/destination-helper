/* Browse: find any record, open it, link / tag / note / attach / undo. */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const act = App.act('browse');
const S = { types: [], rels: [], type: null, q: '', current: null, list: [] };
// What each relationship word means, as the middle of a sentence. A link is
// stored one way (from → to); read from the other side it flips.
const REL = {
  about:    { out: 'is about',          in: 'is about this' },
  for:      { out: 'is for',            in: 'is for this' },
  part_of:  { out: 'is part of',        in: 'is part of this' },
  related:  { out: 'is related to',     in: 'is related to this' },
  same_as:  { out: 'is the same as',    in: 'is the same as this' },
  mentions: { out: 'mentions',          in: 'mentions this' },
};
const relText = (rel, dir) => ((S.relations && S.relations[rel]) || REL[rel] || { out: rel.replace(/_/g, ' '), in: rel.replace(/_/g, ' ') + ' this' })[dir];
const typeWord = ty => (S.types.find(x => x.type === ty)?.label || ty).toLowerCase();

// ---------- list ----------------------------------------------------------
async function loadTypes() {
  const d = await api('GET', '/v1/types'); S.types = d.types; S.rels = d.rels; S.relations = d.relations || null;
  const total = d.types.reduce((a, t) => a + t.count, 0);
  $('#count').innerHTML = `<b>${total}</b> records`;
  $('#types').innerHTML = `<button class="chip ${S.type ? '' : 'on'}" data-type="">All<span class="n">${total}</span></button>` +
    d.types.filter(t => t.count || t.type === S.type).map(t => `<button class="chip ${S.type === t.type ? 'on' : ''}" data-type="${t.type}">${esc(t.label)}<span class="n">${t.count}</span></button>`).join('');
  $('#n-type').innerHTML = d.types.map(t => `<option value="${t.type}">${esc(t.label)}</option>`).join('');
}
async function loadList() {
  const p = new URLSearchParams({ q: S.q, limit: 100 }); if (S.type) p.set('type', S.type);
  S.list = await api('GET', '/v1/search?' + p);
  $('#list').innerHTML = S.list.length ? S.list.map(r => `<a class="item ${S.current?.id === r.id ? 'on' : ''}" href="#${r.id}" data-id="${r.id}">
      <div class="ty">${esc(r.type)}</div><div class="nm">${esc(r.name)}</div>
      ${r.snippet ? `<div class="sn">${esc(r.snippet).replace(/\[([^\]]+)\]/g, '<b>$1</b>')}</div>` : ''}
      ${r.tags.length ? `<div class="tg">${r.tags.map(esc).join(' · ')}</div>` : ''}</a>`).join('')
    : `<div class="item muted">${S.q ? 'Nothing matches.' : 'No records yet. Make one with + New.'}</div>`;
}
let qT;
$('#q').addEventListener('input', e => { S.q = e.target.value; clearTimeout(qT); qT = setTimeout(loadList, 150); });
$('#types').addEventListener('click', e => { const c = e.target.closest('.chip'); if (!c) return; S.type = c.dataset.type || null; loadTypes(); loadList(); });
$('#list').addEventListener('click', e => { const a = e.target.closest('a.item'); if (!a) return; e.preventDefault(); open(a.dataset.id); });

// ---------- detail --------------------------------------------------------
async function open(id) {
  try { S.current = await api('GET', `/v1/entities/${id}`); } catch (e) { toast(e.message); return; }
  location.hash = id; document.body.classList.add('showing');
  renderDetail(); loadList();
}
function renderDetail() {
  const e = S.current, d = $('#detail');
  if (!e) { d.innerHTML = '<p class="muted">Pick a record, or make one with + New.</p>'; return; }
  const kv = Object.entries(e.data);
  d.innerHTML = `
   <div class="row" style="justify-content:space-between;align-items:flex-start">
    <div><div class="ty">${esc(e.type)}${e.deleted_at ? ' · deleted' : ''}</div><h2 contenteditable="true" id="d-name" spellcheck="false">${esc(e.name)}</h2>
     <div class="small">v${e.version} · changed ${fmtWhen(e.updated_at)} by ${esc(e.updated_by)}${e.source ? ` · from ${esc(e.source)}` : ''}</div></div>
    <span class="row"><button class="sbtn mini back" id="d-back">‹ List</button><select id="d-type" class="mini" title="Type">${S.types.map(t => `<option value="${t.type}" ${t.type === e.type ? 'selected' : ''}>${esc(t.label)}</option>`).join('')}</select>${e.deleted_at ? '' : '<button class="sbtn mini danger" id="d-del">Delete</button>'}</span>
   </div>
   <div data-conflict></div>
   <div class="blk"><h3>Details</h3>
    ${kv.length ? `<div class="kv">${kv.map(([k, v]) => `<span class="k">${esc(k)}</span><span>${esc(typeof v === 'object' ? JSON.stringify(v) : v)}</span>`).join('')}</div>` : '<div class="small">No details yet.</div>'}
    <form class="row" id="d-kv" style="margin-top:8px"><input type="text" placeholder="detail, e.g. city" id="kv-k" required><input type="text" placeholder="value" id="kv-v"><button class="sbtn mini">Set</button></form>
    ${Object.keys(e.external_ids).length ? `<div class="small" style="margin-top:8px">Outside ids: ${Object.entries(e.external_ids).map(([k, v]) => `${esc(k)} ${esc(v)}`).join(' · ')}</div>` : ''}
    <form class="row" id="d-ext" style="margin-top:6px"><input type="text" placeholder="outside id name, e.g. sec_cik" id="ext-k" required><input type="text" placeholder="id" id="ext-v" required><button class="sbtn mini">Set id</button></form>
   </div>
   <div class="blk"><h3>Tags</h3>
    <div class="row">${e.tags.map(t => `<span class="chip on">${esc(t)} <span data-untag="${esc(t)}" style="cursor:pointer" title="remove">×</span></span>`).join('')}
     <form id="d-tag" class="row" style="flex:1"><input type="text" placeholder="add a tag" id="tag-in" required><button class="sbtn mini">Tag</button></form></div>
   </div>
   <div class="blk"><h3>Links</h3>
    <div class="small" style="margin-bottom:6px">How this ${esc(typeWord(e.type))} connects to other records. Click a name to go to it.</div>
    <ul class="plain" id="d-links">${e.links.map(l => {
      const other = `<a href="#${l.other_id}" data-open="${l.other_id}">${esc(l.other_name)}</a> <span class="small">(${esc(typeWord(l.other_type))})</span>`;
      const sentence = l.direction === 'out' ? `This ${esc(typeWord(e.type))} ${esc(relText(l.rel, 'out'))} ${other}` : `${other} ${esc(relText(l.rel, 'in'))} ${esc(typeWord(e.type))}`;
      return `<li><span style="flex:1">${sentence}${l.note ? ` <span class="small">— ${esc(l.note)}</span>` : ''}</span><button class="sbtn mini x" data-unlink="${l.id}">Unlink</button></li>`; }).join('') || '<li class="small">Not linked to anything yet.</li>'}</ul>
    <form id="d-link" class="row" style="margin-top:10px"><span class="small">This ${esc(typeWord(e.type))}</span><select id="link-rel" class="mini">${S.rels.map(r => `<option value="${r}">${esc(relText(r, 'out'))}</option>`).join('')}</select>
     <span class="picker" style="flex:2;min-width:180px"><input type="text" id="link-q" placeholder="which record? type a name…" autocomplete="off"><div class="drop" id="link-drop" hidden></div></span>
     <input type="hidden" id="link-to"><input type="text" id="link-note" placeholder="why (optional)"><button class="sbtn mini">Link</button></form>
   </div>
   <div class="blk"><h3>Notes</h3>
    <ul class="plain" id="d-notes">${e.notes.map(n => `<li><span style="white-space:pre-wrap;flex:1">${esc(n.body)}</span><span class="small">${fmtWhen(n.created_at)}</span><button class="sbtn mini x" data-delnote="${n.id}">Delete</button></li>`).join('') || '<li class="small">No notes.</li>'}</ul>
    <form id="d-note" style="margin-top:8px"><textarea id="note-in" placeholder="write a note"></textarea><div class="row" style="margin-top:6px"><button class="sbtn mini">Add note</button></div></form>
   </div>
   <div class="blk"><h3>Files</h3>
    <ul class="plain" id="d-files">${e.files.map(f => `<li><a href="/v1/files/${f.id}" target="_blank">${esc(f.name)}</a><span class="small">${f.bytes < 1024 ? f.bytes + ' bytes' : (f.bytes / 1024).toFixed(1) + ' KB'} · ${esc(f.media_type)} · ${fmtWhen(f.created_at)}</span><button class="sbtn mini x" data-delfile="${f.id}">Delete</button></li>`).join('') || '<li class="small">No files.</li>'}</ul>
    <form id="d-file" class="row" style="margin-top:8px"><input type="file" id="file-in" required><button class="sbtn mini">Attach</button></form>
   </div>
   <div class="blk"><h3>History of this record</h3>
    <ul class="plain hist">${e.history.map(h => `<li class="${h.undone_by ? 'undone' : ''}"><div><div>${esc(h.action)} <span class="small">${fmtWhen(h.ts)} · ${esc(h.app)}</span></div><code>${esc(summarize(h))}</code></div><div>${h.undone_by ? '<span class="small">undone</span>' : `<button class="sbtn mini" data-undo="${h.id}">Undo</button>`}</div></li>`).join('')}</ul>
   </div>`;
  wireDetail();
}
function summarize(h) {
  const pick = o => { if (!o) return 'none'; const c = { ...o }; ['id', 'entity_id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'version', 'sha256', 'from_id', 'to_id'].forEach(k => delete c[k]); return JSON.stringify(c); };
  if (h.tbl === 'links') { const l = h.after || h.before || {}; return `link: ${relText(l.rel, 'out').replace(/^is /, '')}${l.note ? ' — ' + l.note : ''}${l.deleted_at ? ' (removed)' : ''}`; }
  return `${pick(h.before)} → ${pick(h.after)}`.slice(0, 220);
}
function wireDetail() {
  const e = S.current, id = e.id;
  const act = fn => async ev => { ev.preventDefault(); try { await fn(); await open(id); loadTypes(); } catch (x) { if (x.status === 409) conflict(x.detail); else toast(x.message, 4000); } };
  $('#d-back').onclick = () => { document.body.classList.remove('showing'); };
  $('#d-name').addEventListener('blur', act(async () => { const n = $('#d-name').textContent.trim(); if (n !== e.name) await api('PUT', `/v1/entities/${id}`, { name: n, version: e.version }); }));
  $('#d-name').addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); ev.target.blur(); } });
  $('#d-type').onchange = act(() => api('PUT', `/v1/entities/${id}`, { type: $('#d-type').value, version: e.version }));
  const del = $('#d-del'); if (del) del.onclick = act(async () => { if (!confirm(`Delete "${e.name}"? It can be undone from History.`)) throw new Error('kept'); await api('DELETE', `/v1/entities/${id}`); toast('Deleted. Undo is in this record\'s history.'); });
  $('#d-kv').onsubmit = act(() => { const k = $('#kv-k').value.trim(), v = $('#kv-v').value; const data = { ...e.data }; if (v === '') delete data[k]; else data[k] = isNaN(v) || v.trim() === '' ? v : Number(v); return api('PUT', `/v1/entities/${id}`, { data, version: e.version }); });
  $('#d-ext').onsubmit = act(() => api('PUT', `/v1/entities/${id}`, { external_ids: { ...e.external_ids, [$('#ext-k').value.trim()]: $('#ext-v').value.trim() }, version: e.version }));
  $('#d-tag').onsubmit = act(() => api('POST', `/v1/entities/${id}/tags`, { tag: $('#tag-in').value }));
  $('#d-note').onsubmit = act(() => api('POST', `/v1/entities/${id}/notes`, { body: $('#note-in').value }));
  $('#d-file').onsubmit = act(async () => { const f = $('#file-in').files[0]; if (!f) throw new Error('Choose a file first'); const fd = new FormData(); fd.append('file', f); await api('POST', `/v1/entities/${id}/files`, fd, true); toast('Attached'); });
  $('#d-link').onsubmit = act(async () => { const to = $('#link-to').value; if (!to) throw new Error('Pick a record to link to'); await api('POST', `/v1/entities/${id}/links`, { to_id: to, rel: $('#link-rel').value, note: $('#link-note').value || null }); });
  let lt; $('#link-q').addEventListener('input', ev => { clearTimeout(lt); lt = setTimeout(async () => {
    const q = ev.target.value.trim(); const drop = $('#link-drop'); if (!q) { drop.hidden = true; return; }
    const hits = (await api('GET', '/v1/search?q=' + encodeURIComponent(q) + '&limit=8')).filter(h => h.id !== id);
    drop.innerHTML = hits.map(h => `<div data-pick="${h.id}" data-name="${esc(h.name)}"><span class="small">${esc(h.type)}</span> ${esc(h.name)}</div>`).join('') || '<div class="small">nothing matches</div>'; drop.hidden = false; }, 150); });
  $('#link-drop').addEventListener('click', ev => { const p = ev.target.closest('[data-pick]'); if (!p) return; $('#link-to').value = p.dataset.pick; $('#link-q').value = p.dataset.name; $('#link-drop').hidden = true; });
  $('#detail').onclick = ev => {
    const t = ev.target.closest('[data-untag],[data-unlink],[data-delnote],[data-delfile],[data-undo],[data-open]'); if (!t) return;
    ev.preventDefault();
    if (t.dataset.open) return open(t.dataset.open);
    const run = t.dataset.untag ? () => api('DELETE', `/v1/entities/${id}/tags/${encodeURIComponent(t.dataset.untag)}`)
      : t.dataset.unlink ? () => api('DELETE', `/v1/links/${t.dataset.unlink}`)
      : t.dataset.delnote ? () => api('DELETE', `/v1/notes/${t.dataset.delnote}`)
      : t.dataset.delfile ? () => api('DELETE', `/v1/files/${t.dataset.delfile}`)
      : () => api('POST', `/v1/history/${t.dataset.undo}/undo?app=browse`).then(() => toast('Undone'));
    act(run)(ev);
  };
}
function conflict(d) {
  $('#detail [data-conflict]').innerHTML = `<div class="conflict"><b>Saved elsewhere first.</b> Another window changed this record ${fmtWhen(d.theirs.updated_at)} (by ${esc(d.theirs.updated_by)}). Their version is now shown; make your change again.</div>`;
  open(S.current.id);
}

// ---------- new record ----------------------------------------------------
$('#new').onclick = () => { $('#n-name').value = ''; $('#n-source').value = ''; if (S.type) $('#n-type').value = S.type; $('#newdlg').showModal(); $('#n-name').focus(); };
$('#n-cancel').onclick = () => $('#newdlg').close();
$('#newform').onsubmit = async ev => {
  ev.preventDefault();
  try { const r = await api('POST', '/v1/entities', { type: $('#n-type').value, name: $('#n-name').value, source: $('#n-source').value || null }); $('#newdlg').close(); await loadTypes(); await open(r.id); toast('Created'); }
  catch (e) { toast(e.message, 4000); }
};

// ---------- boot ----------------------------------------------------------
(async () => {
  try { await loadTypes(); await loadList(); if (location.hash.length > 1) open(location.hash.slice(1)); }
  catch (e) { $('#list').innerHTML = `<div class="item">The engine isn't running. Start it with <span class="mono">scripts/dev.sh</span> and reload.</div>`; }
})();
