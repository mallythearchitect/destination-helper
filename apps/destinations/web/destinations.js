/* Destinations: the pack on a map, ranked for a goal, with your list on top. */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const act = App.act('destinations');
const S = { opt: null, kind: 'us_city', goal: 'growth', q: '', tier: '', maxCost: '', sort: 'fit', minPop: 250000, places: [], current: null, compare: [], map: null, markers: [], tab: 'atlas' };
try { S.kind = localStorage.getItem('dest.kind') || S.kind; S.goal = localStorage.getItem('dest.goal') || S.goal; S.compare = JSON.parse(localStorage.getItem('dest.compare') || '[]'); } catch (e) {}
const CONF = { 'hand-set': ['hand', 'hand-set'], 'index-derived': ['index', 'from an index'], verified: ['verified', 'verified'], estimate: ['estimate', 'estimate'], you: ['verified', 'you'] };
const badge = c => { const [cls, label] = CONF[c] || ['', c]; return `<span class="badge ${cls}" title="confidence">${esc(label)}</span>`; };
const miles = n => n == null ? '—' : n.toLocaleString() + ' mi';
const TIER_LABEL = { core: 'Core', expansion: 'Expansion', watch: 'Watch', S: 'S', A: 'A', B: 'B', C: 'C', D: 'D' };
const pop = n => n == null ? '' : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(n);
const goalLabel = g => (S.opt.goals.find(x => x.id === g) || { label: g }).label;

const showTab = App.tabs({ render: { atlas: renderAtlas, compare: renderCompare, trip: renderTrip, saved: renderSaved, sources: renderSources }, onShow: t => { S.tab = t; } });
function renderSide() {
  const plural = { us_city: 'US business cities', intl_city: 'International business cities', leisure: 'Leisure destinations', world_city: 'World cities, 15k+', us_place: 'US places' };
  $('#kinds').innerHTML = [...S.opt.kinds, { id: 'all', label: 'Scored + big cities', count: null }].map(k => `<button class="${S.kind === k.id ? 'on' : ''}" data-kind="${k.id}">${esc(plural[k.id] || k.label)}<span class="n">${k.count != null ? k.count.toLocaleString() : ''}</span></button>`).join('');
  $('#goals').innerHTML = S.opt.goals.map(g => `<button class="${S.goal === g.id ? 'on' : ''}" data-goal="${g.id}">${esc(g.label)}</button>`).join('');
}
$('#kinds').addEventListener('click', async e => { const b = e.target.closest('[data-kind]'); if (!b) return; S.kind = b.dataset.kind; try { localStorage.setItem('dest.kind', S.kind); } catch (x) {} renderSide(); await load(); showTab(S.tab); });
$('#goals').addEventListener('click', async e => { const b = e.target.closest('[data-goal]'); if (!b) return; S.goal = b.dataset.goal; try { localStorage.setItem('dest.goal', S.goal); } catch (x) {} renderSide(); await load(); showTab(S.tab); });

async function load() {
  const q = new URLSearchParams({ kind: S.kind, goal: S.goal, sort: S.sort, q: S.q }); if (S.tier) q.set('tier', S.tier); if (S.maxCost) q.set('max_cost', S.maxCost); if (S.kind === 'world_city' || S.kind === 'all') q.set('min_pop', S.minPop);
  S.places = await api('GET', '/v1/destinations/places?' + q);
  $('#pill').innerHTML = `<b>${S.places.length}</b> places · home ${esc(S.opt.home.name)}`;
}

// ---------- atlas ----------------------------------------------------------------
function renderAtlas() {
  const p = $('#p-atlas');
  if (!p.dataset.built) {
    p.innerHTML = `<div class="toolbar"><input type="search" id="q" placeholder="Search a place, a tag, a region…" value="${esc(S.q)}">
      <select id="tier"><option value="">any tier</option>${S.opt.tiers.map(t => `<option value="${t}" ${S.tier === t ? 'selected' : ''}>${esc(TIER_LABEL[t] || t)}</option>`).join('')}</select>
      <input type="number" id="maxcost" placeholder="max $/day" value="${esc(S.maxCost)}" style="width:110px">
      <select id="minpop" title="smallest city to show">${S.opt.pop_steps.map(v => `<option value="${v}" ${S.minPop === v ? 'selected' : ''}>≥ ${pop(v)} people</option>`).join('')}</select>
      <select id="sort">${[['fit', 'by fit'], ['cost', 'by cost'], ['distance', 'by distance'], ['population', 'by population'], ['tier', 'by tier'], ['name', 'by name']].map(([v, l]) => `<option value="${v}" ${S.sort === v ? 'selected' : ''}>${l}</option>`).join('')}</select></div>
      <div class="atlas"><div id="map"></div><div class="list" id="list"></div></div>
      <div class="help">Every filter thins the map too. Fit is how well a place matches the goal chosen above, from its scores<span class="dev-only"> (the weights are yours to change in Settings → Logic)</span>; hand-set scores are marked, index-derived ones name their index in the detail. World cities are from <a href="https://www.geonames.org/" target="_blank">GeoNames</a> (CC BY 4.0); they have no scores unless they are also business cities, and the population filter keeps the map readable.</div>`;
    p.dataset.built = '1';
    let t; $('#q').oninput = e => { clearTimeout(t); t = setTimeout(async () => { S.q = e.target.value; await load(); renderAtlas(); }, 200); };
    $('#tier').onchange = async e => { S.tier = e.target.value; await load(); renderAtlas(); };
    $('#maxcost').onchange = async e => { S.maxCost = e.target.value; await load(); renderAtlas(); };
    $('#sort').onchange = async e => { S.sort = e.target.value; await load(); renderAtlas(); };
    $('#minpop').onchange = async e => { S.minPop = Number(e.target.value); await load(); renderAtlas(); };
    $('#list').addEventListener('click', e => { const cb = e.target.closest('input[data-cmp]'); if (cb) { toggleCompare(cb.dataset.cmp, cb.checked); return; } const it = e.target.closest('.item'); if (it) openPlace(it.dataset.id); });
    initMap();
  }
  $('#list').innerHTML = S.places.map(x => `<div class="item ${S.current === x.id ? 'on' : ''}" data-id="${x.id}">
    <div><div class="nm">${x.tier ? `<span class="tier ${esc(x.tier)}">${esc(TIER_LABEL[x.tier] || x.tier)}</span>` : ''}${esc(x.name)}${x.region && x.kind !== 'leisure' ? `<span class="small">, ${esc(x.region)}</span>` : ''}${x.hub ? ` <span class="small">via ${esc(x.hub)}</span>` : ''}${x.status ? `<span class="badge verified">${esc(x.status)}</span>` : ''}</div>
     <div class="sub">${x.kind === 'world_city' ? esc(x.country) + ' · ' + pop(x.population) + ' people · ' : ''}${x.cost_per_day != null ? '$' + x.cost_per_day + ' a day · ' : ''}${miles(x.distance_miles)} from home</div>
     ${x.tags.length ? `<div class="tags">${x.tags.slice(0, 4).map(t => `<span>${esc(t)}</span>`).join('')}</div>` : ''}</div>
    <div class="side">${x.fit != null ? `<div class="ring" style="--v:${Math.round(x.fit)}"><b>${Math.round(x.fit)}</b><small>fit</small></div>` : ''}<label class="cmp" title="tick to compare"><input type="checkbox" data-cmp="${x.id}" ${S.compare.includes(x.id) ? 'checked' : ''}> compare</label></div></div>`).join('') || '<div class="item small">Nothing matches.</div>';
  drawMarkers();
}
function initMap() {
  if (!window.maplibregl) { $('#map').innerHTML = '<div class="small" style="padding:12px">The map library did not load (needs internet for tiles and the library). The list still works.</div>'; return; }
  S.map = new maplibregl.Map({ container: 'map', style: 'https://tiles.openfreemap.org/styles/positron', center: [S.opt.home.lon, S.opt.home.lat], zoom: 2.2, attributionControl: { compact: false, customAttribution: 'World cities © <a href="https://www.geonames.org/" target="_blank">GeoNames</a> (CC BY 4.0)' } });
  S.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  new maplibregl.Marker({ color: '#17242B' }).setLngLat([S.opt.home.lon, S.opt.home.lat]).setPopup(new maplibregl.Popup().setText('Home: ' + S.opt.home.name)).addTo(S.map);
}
function drawMarkers() {
  if (!S.map) return;
  S.markers.forEach(m => m.remove()); S.markers = [];
  const pts = S.places.filter(x => x.lat != null && x.lon != null);
  pts.forEach(x => {
    const scored = x.fit != null, size = scored ? 8 + x.fit / 12 : x.kind === 'world_city' ? 4 + Math.min(6, Math.log10(Math.max(1, x.population || 1)) - 3) : 7;
    const el = document.createElement('div'); el.style.cssText = `width:${size}px;height:${size}px;border-radius:50%;background:${x.status ? '#2E8B57' : scored ? '#E4643B' : x.kind === 'leisure' ? '#17788A' : '#8A959A'};border:1.5px solid #fff;box-shadow:0 1px 3px rgba(23,36,43,.35);cursor:pointer;opacity:${scored ? .95 : .7}`;
    el.title = x.name; el.onclick = () => openPlace(x.id);
    S.markers.push(new maplibregl.Marker({ element: el }).setLngLat([x.lon, x.lat]).addTo(S.map));
  });
  if (pts.length && pts.length < 400) { const b = new maplibregl.LngLatBounds(); pts.forEach(x => b.extend([x.lon, x.lat])); b.extend([S.opt.home.lon, S.opt.home.lat]); S.map.fitBounds(b, { padding: 40, maxZoom: 6, duration: 600 }); }
}

// ---------- detail ---------------------------------------------------------------
async function openPlace(id) {
  let p; try { p = await api('GET', `/v1/destinations/places/${id}`); } catch (e) { toast(e.message); return; }
  S.current = id;
  const bars = p.scores.map(s => `<tr><td style="width:130px">${esc(s.label || s.domain)}</td><td><div class="score"><i style="width:${s.value}%"></i></div></td><td class="num" style="width:40px">${s.value}</td><td style="width:120px">${badge(s.confidence)}${s.from_indexes.length ? `<span class="small"> ${esc(s.from_indexes.join(', '))}</span>` : ''}</td></tr>`).join('');
  const idx = p.index_values.map(v => `<tr><td>${esc(v.name)} <span class="small">${esc(v.edition || '')}</span></td><td class="num">${v.value}</td><td>${v.urls.length ? `<a href="${esc(v.urls[0])}" target="_blank" class="small">source ↗</a>` : ''}</td></tr>`).join('');
  $('#detail-body').innerHTML = `<div class="small">${esc(p.kind_label)}${p.tier ? ' · ' + esc(TIER_LABEL[p.tier] || p.tier) : ''}</div><h2>${esc(p.name)}${p.region && p.kind !== 'leisure' ? `, ${esc(p.region)}` : ''}</h2>
    <div class="row" style="margin:6px 0 12px"><span class="small">Get there from ${esc(p.home.name)}:</span>${p.ways_there.map(w => `<a class="sbtn mini gold" href="${esc(w.url)}" target="_blank" rel="noopener" title="${esc(w.means)}">${esc(w.label)} ↗</a>`).join('')}<span class="small">live sites · ${miles(p.distance_miles)}</span></div>
    <p style="margin:4px 0 10px;color:var(--paper-2)">${esc(p.description || '')}</p>
    <div class="row" style="margin-bottom:10px"><span>${p.cost_per_day != null ? `<b>$${p.cost_per_day}</b>/day ${badge('estimate')} <span class="small">${p.cost_split.map(c => `${c.part} $${Math.round(c.amount)}`).join(' · ')}</span>` : ''}</span><span>${miles(p.distance_miles)} from ${esc(p.home.name)}${p.hub ? ` · hub ${esc(p.hub)}` : ''}</span>${p.population ? `<span class="small">${pop(p.population)} people · ${esc(p.country || '')}${p.timezone ? ' · ' + esc(p.timezone) : ''}</span>` : ''}${p.tags.length ? `<span class="small">${esc(p.tags.join(' · '))}</span>` : ''}</div>
    <div class="row status-btns" style="margin-bottom:12px"><span class="small">My list:</span>${S.opt.statuses.map(([v, l]) => `<button class="sbtn mini ${p.status === v ? 'on' : ''}" data-status="${v}">${esc(l)}</button>`).join('')}${p.status ? '<button class="sbtn mini" data-status="">clear</button>' : ''}${p.record_id ? `<a class="sbtn mini" href="/apps/system/web/browse.html#${p.record_id}">notes &amp; history (${p.notes}) ›</a>` : ''}</div>
    <form class="row" id="note-form" style="margin-bottom:12px"><input type="text" id="note-in" placeholder="add a note about this place" style="flex:1"><button class="sbtn mini">Add note</button></form>
    ${p.scores.length ? `<h3 style="margin:10px 0 6px">Scores <span class="small">fit for ${esc(goalLabel(S.goal))}: <b>${p.goal_fits[S.goal] ?? '—'}</b></span></h3><table class="t">${bars}</table>` : '<div class="small" style="margin:8px 0">No scores for this place yet: it is on the map from GeoNames for the whole-world view. Business and leisure scoring covers the 184 scored places; more come with outside data in phase 7.</div>'}
    ${idx ? `<h3 style="margin:14px 0 6px">Index values</h3><table class="t">${idx}</table>` : ''}
    ${p.dataset ? `<h3 style="margin:14px 0 6px">Where this comes from</h3><div class="small"><b>${esc(p.dataset.name)}</b> ${badge(p.dataset.confidence)}<br>${esc(p.dataset.origin || '')}<br>${esc(p.dataset.method || '')}</div>` : ''}`;
  $('#detail').showModal();
  $('#detail-body').querySelectorAll('[data-status]').forEach(b => b.onclick = async () => { try { await act('destinations.set_status', { place_id: id, status: b.dataset.status || null }); toast(b.dataset.status ? 'Marked ' + b.dataset.status : 'Cleared'); await load(); openPlace(id); if (S.tab === 'atlas') renderAtlas(); } catch (e) { toast(e.message, 4000); } });
  $('#note-form').onsubmit = async e => { e.preventDefault(); const v = $('#note-in').value.trim(); if (!v) return; try { await act('destinations.add_note', { place_id: id, body: v }); toast('Note added'); await load(); openPlace(id); } catch (x) { toast(x.message, 4000); } };
}
$('#detail-close').onclick = () => $('#detail').close();

// ---------- compare ---------------------------------------------------------------
function toggleCompare(id, on) {
  const max = (S.opt.defaults || {}).compare_limit || 4;
  if (on && !S.compare.includes(id)) { if (S.compare.length >= max) { toast(`Compare holds ${max}; untick one first`); renderAtlas(); return; } S.compare.push(id); }
  if (!on) S.compare = S.compare.filter(x => x !== id);
  try { localStorage.setItem('dest.compare', JSON.stringify(S.compare)); } catch (e) {}
}
async function renderCompare() {
  const ps = await Promise.all(S.compare.map(id => api('GET', `/v1/destinations/places/${id}`).catch(() => null))); const list = ps.filter(Boolean);
  $('#p-compare').innerHTML = `<h2 class="sec">Compare <span class="small">${list.length} of ${(S.opt.defaults || {}).compare_limit || 4}</span></h2><div class="help">Tick places on the Atlas list to add them here.</div>
   ${list.length ? `<div class="scroll"><table class="t"><thead><tr><th></th>${list.map(p => `<th>${esc(p.name)}<br><span class="small">${esc(p.kind_label)}</span></th>`).join('')}</tr></thead><tbody>
    <tr><td>Fit for ${esc(goalLabel(S.goal))}</td>${list.map(p => `<td class="num"><b>${p.goal_fits[S.goal] ?? '—'}</b></td>`).join('')}</tr>
    ${S.opt.domains.map(d => `<tr><td>${esc(d.label)}</td>${list.map(p => { const s = p.scores.find(x => x.domain === d.id); return `<td class="num">${s ? s.value + ' ' + badge(s.confidence) : '—'}</td>`; }).join('')}</tr>`).join('')}
    <tr><td>Population</td>${list.map(p => `<td class="num">${pop(p.population) || '—'}</td>`).join('')}</tr>
    <tr><td>Cost per day</td>${list.map(p => `<td class="num">${p.cost_per_day != null ? '$' + p.cost_per_day : '—'}</td>`).join('')}</tr>
    <tr><td>Distance from home</td>${list.map(p => `<td class="num">${miles(p.distance_miles)}</td>`).join('')}</tr>
    <tr><td>Tier</td>${list.map(p => `<td>${esc(TIER_LABEL[p.tier] || p.tier || '—')}</td>`).join('')}</tr>
    <tr><td>Tags</td>${list.map(p => `<td class="small">${esc(p.tags.join(', ')) || '—'}</td>`).join('')}</tr>
    <tr><td>My status</td>${list.map(p => `<td>${esc(p.status || '—')}</td>`).join('')}</tr>
    <tr><td></td>${list.map(p => `<td><button class="sbtn mini" data-uncmp="${p.id}">remove</button></td>`).join('')}</tr></tbody></table></div>` : ''}`;
  $('#p-compare').querySelectorAll('[data-uncmp]').forEach(b => b.onclick = () => { toggleCompare(b.dataset.uncmp, false); renderCompare(); });
}

// ---------- trip cost ---------------------------------------------------------------
async function renderTrip() {
  const p = $('#p-trip');
  const opts = S.places.filter(x => x.cost_per_day != null).map(x => `<option value="${x.id}" ${S.current === x.id ? 'selected' : ''}>${esc(x.name)}${x.region && x.kind !== 'leisure' ? ', ' + esc(x.region) : ''}</option>`).join('');
  p.innerHTML = `<h2 class="sec">Trip cost</h2><div class="help">A rough figure with every input visible: days × people × cost per day, plus flights. Flights are guessed from distance unless you type your own.</div>
   <form class="row" id="tripform"><select id="t-place" style="min-width:220px">${opts}</select><label class="small">days <input type="number" id="t-days" value="7" min="1" style="width:70px"></label><label class="small">people <input type="number" id="t-people" value="1" min="1" style="width:60px"></label><label class="small">flight each $ <input type="number" id="t-flight" placeholder="guess" style="width:90px"></label><label class="small"><input type="checkbox" id="t-housing" checked> I need a place to stay</label><button class="sbtn gold mini">Work it out</button></form>
   <div class="help">Cost per day is one person's typical day: somewhere modest to stay, three meals, getting around, a little extra. It's split by fixed shares (lodging 45%, food 30%, transport 10%, other 15%); untick housing if you have a place, and lodging drops out. The Sources tab has the full method.</div>
   <div id="trip-out" style="margin-top:12px"></div>`;
  $('#tripform').onsubmit = async e => {
    e.preventDefault(); const q = new URLSearchParams({ place_id: $('#t-place').value, days: $('#t-days').value, people: $('#t-people').value, housing: $('#t-housing').checked }); if ($('#t-flight').value) q.set('flight_each', $('#t-flight').value);
    try { const r = await api('GET', '/v1/destinations/trip-cost?' + q);
      $('#trip-out').innerHTML = `<div class="card"><h3>${esc(r.place.name)}${r.place.hub ? ' via ' + esc(r.place.hub) : ''}${r.housing ? '' : ' · no lodging'}</h3><table class="t">
        ${r.lines.map(l => `<tr><td class="small">${esc(l.part)}: $${l.per_day} a day × ${r.days} × ${r.people} <span class="small">(${esc(l.means)})</span></td><td class="num">$${l.total.toLocaleString()}</td></tr>`).join('')}
        <tr><td>${r.days} days × ${r.people} × $${r.per_day_used}/day</td><td class="num">$${r.daily_total.toLocaleString()}</td></tr>
        <tr><td>Flights: ${r.people} × $${r.flight_each}${r.assumption ? ` <span class="small">(${esc(r.assumption)})</span>` : ''}</td><td class="num">$${r.flights_total.toLocaleString()}</td></tr>
        <tr><td><b>Total</b></td><td class="num"><b>$${r.total.toLocaleString()}</b></td></tr></table></div>`; } catch (x) { toast(x.message, 4000); }
  };
  if (opts) $('#tripform').requestSubmit();
}

// ---------- my list ---------------------------------------------------------------
async function renderSaved() {
  const list = await api('GET', `/v1/destinations/places?kind=all&saved=true&goal=${S.goal}&sort=name`);
  $('#p-saved').innerHTML = `<h2 class="sec">My list <span class="small">${list.length}</span></h2><div class="help">Places you marked or noted. Each is a record in the vault: open one in Browse for its notes, tags, files, links and history.</div>
   ${list.length ? `<table class="t"><thead><tr><th>Place</th><th>Status</th><th class="num">Fit</th><th class="num">$/day</th><th class="num">Distance</th><th>Notes</th><th></th></tr></thead><tbody>
    ${list.map(x => `<tr><td><a href="#" data-open="${x.id}">${esc(x.name)}${x.region && x.kind !== 'leisure' ? ', ' + esc(x.region) : ''}</a> <span class="small">${esc(x.kind_label)}</span></td><td>${esc(x.status || '—')}</td><td class="num">${x.fit != null ? Math.round(x.fit) : '—'}</td><td class="num">${x.cost_per_day != null ? '$' + x.cost_per_day : '—'}</td><td class="num">${miles(x.distance_miles)}</td><td class="num">${x.notes}</td><td>${x.record_id ? `<a class="sbtn mini" href="/apps/system/web/browse.html#${x.record_id}">open ›</a>` : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="small">Nothing yet. Open a place and mark it Shortlist, Want to go, Base candidate or Visited.</div>'}`;
  $('#p-saved').querySelectorAll('[data-open]').forEach(a => a.onclick = e => { e.preventDefault(); openPlace(a.dataset.open); });
}

// ---------- sources ---------------------------------------------------------------
async function renderSources() {
  const v = await api('GET', '/v1/destinations/sources');
  const st = s => `<span class="badge ${s === 'ok' ? 'verified' : s === 'unchecked' ? '' : 'hand'}">${esc(s)}</span>`;
  $('#p-sources').innerHTML = `<h2 class="sec">Sources</h2><div class="help">Every figure on this page can be traced here: the dataset it belongs to, the published index it was derived from, and the method. The checker re-fetches every link and flags what changed or died.</div>
   <div class="card"><h3>What the words mean</h3><table class="t">${Object.entries(v.method.classification || {}).map(([k, txt]) => `<tr><td style="width:150px"><b>${esc(k.replace(/_/g, ' '))}</b></td><td>${esc(txt)}</td></tr>`).join('')}</table></div>
   <div class="card"><h3>Cost per day</h3><div>${esc((v.method.cost_per_day || {}).means || '')}</div><table class="t" style="margin-top:8px"><tr><th>Part</th><th class="num">Share</th><th>Means</th></tr>${((v.method.cost_per_day || {}).split || []).map(([p, s, m]) => `<tr><td>${esc(p)}</td><td class="num">${Math.round(s * 100)}%</td><td class="small">${esc(m)}</td></tr>`).join('')}</table><div class="small" style="margin-top:6px">${esc((v.method.cost_per_day || {}).split_note || '')}</div></div>
   <div class="card"><h3>The rules, as data</h3><div class="help">These live in <a href="/apps/system/web/settings.html#logic">Settings → Logic</a> and can be edited there; the page follows.</div><table class="t">
    <tr><td style="width:170px">Cost per day shares</td><td class="small">${esc(Object.entries(v.method.cost_split_shares || {}).map(([k, s]) => `${k} ${Math.round(s * 100)}%`).join(' · '))}</td></tr>
    <tr><td>Flight guess</td><td class="small">miles × $${(v.method.flight_guess || {}).dollars_per_mile_each_way} × 2, never under $${(v.method.flight_guess || {}).floor}</td></tr>
    <tr><td>Goals</td><td class="small">${esc(Object.entries(v.method.goal_weights || {}).map(([g, w]) => `${g}: ${Object.entries(w).map(([d, x]) => `${d} ×${x}`).join(', ')}`).join(' · '))}</td></tr>
    <tr><td>Scores from indexes</td><td class="small">${esc(Object.entries(v.method.extra_domains || {}).map(([d, r]) => `${d} = clamp(${r.index} × ${r.multiply} + ${r.add})`).join(' · '))}</td></tr></table></div>
   <div class="card"><h3>Ways to get there <span class="small">live sites, opened from each place's popup</span></h3><table class="t">${(v.travel || []).map(w => `<tr><td>${esc(w.label)}</td><td class="small">${esc(w.means)}</td><td><a href="${esc(w.url)}" target="_blank" class="small">↗</a></td></tr>`).join('')}</table></div>
   <div class="card"><h3>Datasets in the pack <span class="small">built ${esc(v.pack.built_at || '')}</span></h3><table class="t">${v.datasets.map(d => `<tr><td><b>${esc(d.name)}</b> ${badge(d.confidence)}<div class="small">${esc(d.what || '')}</div><div class="small">${esc(d.origin || '')}</div><div class="small">${esc(d.method || '')}</div></td></tr>`).join('')}</table></div>
   <div class="card"><h3>Published indexes</h3><table class="t">${v.indexes.map(i => `<tr><td><b>${esc(i.name)}</b> <span class="small">${esc(i.edition || '')}</span><div class="small">used for: ${esc(i.used_for || '')}</div></td><td>${i.urls.map((u, n) => `<a href="${esc(u)}" target="_blank" class="small">link ${n + 1} ↗</a>`).join(' ')}</td></tr>`).join('')}</table></div>
   <div class="card"><h3>Method</h3>${(v.method.domains || []).map(d => `<div style="margin-bottom:8px"><b>${esc(d.label)}</b> <span class="small">${esc(d.means)}</span><div class="small">${esc(d.from)}</div></div>`).join('')}${v.method.fit ? `<div class="small"><b>Fit:</b> ${esc(typeof v.method.fit === 'string' ? v.method.fit : JSON.stringify(v.method.fit))}</div>` : ''}${v.method.tier ? `<div class="small"><b>Tier:</b> ${esc(typeof v.method.tier === 'string' ? v.method.tier : JSON.stringify(v.method.tier))}</div>` : ''}</div>
   <div class="card"><h3>Services</h3><table class="t">${v.services.map(s => `<tr><td>${esc(s.name)}</td><td class="small">${esc(s.used_for || '')}</td><td>${s.url ? `<a href="${esc(s.url)}" target="_blank" class="small">↗</a>` : ''}</td></tr>`).join('')}</table></div>
   <div class="card"><h3>The source registry <span class="small">${v.registry.length} links</span></h3><div class="row" style="margin-bottom:8px"><button class="sbtn gold mini" id="check-all">Check every link now</button><span class="small">Fetches each one; takes a minute.</span></div>
    <table class="t"><thead><tr><th>Source</th><th>Kind</th><th>Status</th><th>Last checked</th></tr></thead><tbody>${v.registry.map(s => `<tr><td><a href="${esc(s.url)}" target="_blank">${esc(s.name)}</a><div class="small">${esc(s.url).slice(0, 80)}</div></td><td class="small">${esc(s.kind)}</td><td>${st(s.status)}${s.http_status ? ` <span class="small">${s.http_status}</span>` : ''}</td><td class="small">${s.last_checked ? new Date(s.last_checked).toLocaleString() : '—'}</td></tr>`).join('')}</tbody></table></div>`;
  $('#check-all').onclick = async () => { $('#check-all').disabled = true; toast('Checking every link…', 60000); try { const r = await api('POST', '/v1/destinations/sources/check'); toast(`${r.checked} checked: ${r.ok} ok, ${r.changed} changed, ${r.dead} dead, ${r.error} errors`, 6000); renderSources(); } catch (e) { toast(e.message, 5000); $('#check-all').disabled = false; } };
}

(async () => {
  try { S.opt = await api('GET', '/v1/destinations/options'); const D = S.opt.defaults || {}; if (!App.remember('dest.kind')) S.kind = D.kind || S.kind; if (!App.remember('dest.goal')) S.goal = D.goal || S.goal; S.minPop = D.min_population || S.minPop; renderSide(); await load(); showTab(['atlas', 'compare', 'trip', 'saved', 'sources'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'atlas'); }
  catch (e) { $('#p-atlas').innerHTML = `<p>The engine isn't running. Start it with <span class="mono">scripts/dev.sh</span> and reload.</p>`; }
})();
