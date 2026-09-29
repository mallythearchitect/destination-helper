/* Trips: the Destination Helper. Plan → Prepare → Run, with the checker in the middle. */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const act = App.act('trips');
const S = { opt: null, trips: [], id: null, plan: null, helper: null, tab: 'timeline', hsec: 'all' };
try { S.id = localStorage.getItem('trips.id') || null; } catch (e) {}
const label = (list, id) => (Object.fromEntries(list)[id] || id || '—');
const words = () => S.opt.defaults;
const amt = (cents, cur) => cents == null ? '—' : (cur === 'USD' || !cur ? money(cents) : (cents / 100).toLocaleString([], { maximumFractionDigits: 0 }) + ' ' + cur);
const tOf = iso => iso && iso.length > 10 ? new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
const dOf = iso => iso ? new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) : '';
const home = () => S.plan.trip.home_currency;
const statusTag = s => `<span class="st ${s}">${esc(label(words().statuses, s))}</span>`;
const ICON = {
  flight: '<path d="M2 16l20-6-4 8-3-2-3 4-1-4-4-1zM22 10l-8-6-3 2 6 5"/>',
  train: '<rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 11h14M9 21l1.5-4M15 21l-1.5-4M9 7h6"/>',
  bus: '<rect x="4" y="4" width="16" height="13" rx="3"/><path d="M4 11h16M8 21v-4M16 21v-4M8 8h8"/>',
  van: '<path d="M3 16V8a2 2 0 0 1 2-2h9l5 5v5"/><circle cx="8" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>',
  ferry: '<path d="M3 17l2 3h14l2-3M5 17l-1-6h16l-1 6M8 11V7h8v4M12 7V4"/>',
  taxi: '<path d="M5 16l1.5-6h11L19 16M3 16h18v3H3zM9 6h6l1 4H8z"/><circle cx="7" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>',
  transfer: '<path d="M5 16l1.5-6h11L19 16M3 16h18v3H3zM9 6h6l1 4H8z"/><circle cx="7" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>',
  drive: '<path d="M4 15l2-6h12l2 6M3 15h18v4H3z"/><circle cx="7" cy="19" r="1.5"/><circle cx="17" cy="19" r="1.5"/>',
  stay: '<path d="M3 18V8M3 14h18v4M3 14V10h10v4M21 18v-6a2 2 0 0 0-2-2h-6"/><circle cx="7" cy="10" r="1.5"/>',
  activity: '<path d="M4 9a2 2 0 0 0 2-2V5h12v2a2 2 0 0 0 2 2v6a2 2 0 0 0-2 2v2H6v-2a2 2 0 0 0-2-2z"/><path d="M12 5v14" stroke-dasharray="2 2"/>',
  storage: '<rect x="4" y="7" width="16" height="13" rx="2"/><path d="M9 7V4h6v3M4 12h16"/>',
  meal: '<path d="M6 3v8a2 2 0 0 0 4 0V3M8 3v18M16 3c-2 0-3 3-3 6s1 4 3 4v8"/>',
  other: '<path d="M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z"/><circle cx="12" cy="10" r="2"/>',
  work: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5h6v2M3 12h18"/>',
};
const glyph = (k, tag) => `<svg viewBox="0 0 24 24">${ICON[tag === 'work' && k === 'activity' ? 'work' : k] || ICON.other}</svg>`;
const healthColor = h => h >= 60 ? 'var(--color-accent-2-500)' : h >= 40 ? 'var(--color-accent-400)' : 'var(--color-accent)';
const cur = (cents, c) => c === 'USD' || !c ? money(cents) : ({ THB: '฿', EUR: '€', GBP: '£', JPY: '¥' }[c] || c + ' ') + (cents / 100).toLocaleString([], { maximumFractionDigits: 0 });
const cur0 = (cents, c) => c === 'USD' || !c ? money0(cents) : cur(cents, c);
const paysWord = pb => pb === 'company' ? 'work pays' : pb === 'split' ? 'split' : 'you pay';
const flagOf = it => it.findings.some(f => f.severity === 'blocker') ? 'blocker' : it.findings.some(f => f.severity === 'warn') ? 'warn' : 'none';

const showTab = App.tabs({ render: { timeline: renderTimeline, checks: renderChecks, costs: renderCosts, prepare: renderPrepare, run: renderRun, confirm: renderConfirm, helper: renderHelper, region: renderRegion }, onShow: t => { S.tab = t; } });

// ---------- loading ----------------------------------------------------------------
async function loadTrips() {
  S.trips = await api('GET', '/v1/trips');
  if (!S.trips.find(t => t.id === S.id)) S.id = S.trips[0] ? S.trips[0].id : null;
  renderSide();
}
async function loadPlan() {
  S.plan = S.id ? await api('GET', `/v1/trips/${S.id}`) : null;
  const p = S.plan;
  $('#pill').innerHTML = p ? `<b>${esc(p.trip.name)}</b> · ${p.trip.headcount} going · ${p.items.length} items · ${p.finding_counts.blocker} blockers, ${p.finding_counts.warn} warnings` : 'no trip yet';
  renderHero();
}
async function refresh() { await loadTrips(); await loadPlan(); showTab(S.tab); }
function renderSide() {
  $('#trips').innerHTML = S.trips.map(t => `<button class="${t.id === S.id ? 'on' : ''}" data-trip="${t.id}">${esc(t.name)}<span class="n">${t.findings.blocker ? '⛔ ' + t.findings.blocker : ''}${t.to_book ? ' · ' + t.to_book + ' to book' : ''}</span></button>`).join('') || '<span class="small">No trips yet.</span>';
  renderHero();
}
function renderHero() {
  const p = S.plan, box = $('#hero');
  if (!p) { box.innerHTML = ''; return; }
  const t = p.trip, stages = words().stages, idx = stages.findIndex(([id]) => id === t.stage);
  const stageWord = { plan: 'Plan', prepare: 'Prepare', run: 'Run', done: 'Recap' };
  const nights = t.start_date && t.end_date ? Math.round((new Date(t.end_date) - new Date(t.start_date)) / 864e5) : null;
  const who = t.headcount === 1 ? 'just you' : `you + ${t.headcount - 1}`;
  const money_line = t.local_currency && t.local_currency !== t.home_currency ? ` · prices in ${esc(t.local_currency)} and ${esc(t.home_currency)}${t.fx_rate ? ` (1 ${esc(t.home_currency)} = ${t.fx_rate} ${esc(t.local_currency)})` : ''}` : '';
  const place = ((p.items.find(i => i.is_stay && i.from_place) || {}).from_place || '').split(/[,(]/)[0].trim() || (t.name.includes('·') ? t.name.split('·')[1].split(',')[0].trim() : t.name.split(',')[0]) || (p.region && p.region.name);
  box.innerHTML = `<div class="hero">
    <div><div class="ph" id="hero-photo"></div></div>
    <div><div class="stepper" id="stages">${stages.map(([id], i) => `${i ? '<span class="arrow">→</span>' : ''}<button class="${i < idx ? 'done' : ''} ${i === idx ? 'on' : ''}" data-stage="${id}"><i></i>${esc(stageWord[id] || id)}</button>`).join('')}</div>
      <h1>${esc(t.name)}</h1>
      <div class="meta">${t.start_date ? esc(fmtD(t.start_date)) + (t.end_date ? ' – ' + esc(fmtD(t.end_date)) : '') : 'no dates yet'}${nights ? ` · ${nights} days` : ''} · ${who}${money_line}</div>
      ${t.purpose_note ? `<div class="meta" style="margin-top:4px">${esc(t.purpose_note)}</div>` : ''}
      <div class="acts"><button class="sbtn gold" id="add-item">Add something</button><button class="sbtn" id="check-now">Check my plan</button><a class="sbtn" href="/v1/trips/${t.id}/calendar.ics">Add to calendar</a><button class="sbtn ghost" id="trip-settings">Settings</button><a class="sbtn ghost dev-only" href="/apps/system/web/browse.html#${t.entity_id}">Record</a></div></div>
    <div class="health" style="--h:${p.health};--h-col:${healthColor(p.health)}" title="Starts at 100 and drops for every open problem the checker finds"><b>${p.health}</b><small>health</small></div>
  </div>`;
  App.photo(place, $('#hero-photo'), 'circle');
  $('#add-item').onclick = () => itemForm(); $('#trip-settings').onclick = () => tripForm(t);
  $('#check-now').onclick = async () => { const r = await act('trips.run_checks', { trip_id: S.id }); toast(r.counts.blocker ? `${r.counts.blocker} to fix now, ${r.counts.warn} worth a look` : r.counts.warn ? `Nothing to fix now; ${r.counts.warn} worth a look` : 'Nothing wrong that the checks can see'); await refresh(); };
  $('#stages').addEventListener('click', async e => { const b = e.target.closest('[data-stage]'); if (!b) return; try { await act('trips.set_stage', { id: S.id, stage: b.dataset.stage }); toast(`Stage: ${stageWord[b.dataset.stage]}`); await refresh(); } catch (x) { toast(x.message, 5000); } });
  if (window.Helper) Helper.setTrip(S.id);
}
$('#new-trip').onclick = () => tripWizard();

// ---------- a small form builder --------------------------------------------------------
/* fields: [{k, l, t: text|number|date|datetime|select|textarea|check, o: [[v,l]], v, help, half}] */
function form(title, fields, onSave, extra) {
  const d = $('#form');
  const inp = f => {
    const v = f.v == null ? '' : f.v;
    if (f.t === 'select') return `<select name="${f.k}">${(f.o || []).map(([ov, ol]) => `<option value="${esc(ov)}" ${String(ov) === String(v) ? 'selected' : ''}>${esc(ol)}</option>`).join('')}</select>`;
    if (f.t === 'textarea') return `<textarea name="${f.k}" rows="3">${esc(v)}</textarea>`;
    if (f.t === 'check') return `<label class="row"><input type="checkbox" name="${f.k}" ${v ? 'checked' : ''}> ${esc(f.l)}</label>`;
    const type = f.t === 'datetime' ? 'datetime-local' : (f.t || 'text');
    return `<input type="${type}" name="${f.k}" value="${esc(v)}" ${f.t === 'number' ? 'step="any"' : ''} ${f.ph ? `placeholder="${esc(f.ph)}"` : ''}>`;
  };
  d.innerHTML = `<form method="dialog"><h2 style="margin:0 0 4px">${esc(title)}</h2>${extra || ''}<div class="grid">${fields.map(f => `<div ${f.wide ? 'style="grid-column:1/-1"' : ''}>${f.t === 'check' ? '' : `<label>${esc(f.l)}</label>`}${inp(f)}${f.help ? `<div class="small">${f.help}</div>` : ''}</div>`).join('')}</div>
    <div class="row" style="margin-top:14px;justify-content:flex-end"><button class="sbtn" value="cancel">Cancel</button><button class="sbtn gold" value="save" id="form-save">Save</button></div></form>`;
  d.showModal();
  d.querySelector('form').onsubmit = async e => {
    if (e.submitter && e.submitter.value === 'cancel') return;
    e.preventDefault();
    const fd = new FormData(e.target), out = {};
    for (const f of fields) {
      let v = f.t === 'check' ? fd.has(f.k) : fd.get(f.k);
      if (f.t === 'number') v = v === '' ? null : Number(v);
      if (f.t === 'cents') v = v === '' ? null : Math.round(Number(v) * 100);
      if (v === '') v = null;
      out[f.k] = v;
    }
    try { await onSave(out); d.close(); } catch (x) { toast(x.message, 6000); }
  };
}
const cents = f => ({ ...f, t: 'cents', v: f.v == null ? '' : (f.v / 100) });

// ---------- trip form -------------------------------------------------------------------
function tripForm(t) {
  const d = words();
  const F = [
    { k: 'name', l: 'Name', v: t ? t.name : '', wide: true, ph: 'Thailand, Nov 2026' },
    { k: 'purpose', l: 'Purpose', t: 'select', o: d.purposes, v: t ? t.purpose : 'personal' },
    { k: 'headcount', l: "How many are going (ask first, G01)", t: 'number', v: t ? t.headcount : d.headcount },
    { k: 'start_date', l: 'From', t: 'date', v: t ? t.start_date : '' }, { k: 'end_date', l: 'To', t: 'date', v: t ? t.end_date : '' },
    { k: 'travelers', l: 'Travelers (comma-separated)', v: t ? t.travelers.join(', ') : '', wide: true },
    { k: 'purpose_note', l: "What the trip is for", v: t ? t.purpose_note : '', wide: true, ph: 'active days, nightlife, water sports' },
    { k: 'handling', l: 'How much should the app handle?', t: 'select', o: d.handling, v: t ? t.handling : 'check_my_plan' },
    { k: 'may_contact', l: 'It may message, then call, businesses for me (W27)', t: 'check', v: t ? !!t.may_contact : false },
    { k: 'region_pack', l: 'Region pack', t: 'select', o: [['', '—']].concat(S.opt.regions.map(r => [r.id, r.name])), v: t ? t.region_pack : '' },
    { k: 'time_zone', l: 'Destination time zone', v: t ? t.time_zone : '', ph: 'Asia/Bangkok' },
    { k: 'home_currency', l: 'Home currency', v: t ? t.home_currency : d.home_currency }, { k: 'local_currency', l: 'Local currency', v: t ? t.local_currency : '' },
    { k: 'fx_rate', l: 'Rate: local per 1 home', t: 'number', v: t ? t.fx_rate : '' }, { k: 'fx_date', l: 'Rate checked on', t: 'date', v: t ? t.fx_date : '' },
    { k: 'passport_country', l: 'Passport country', v: t ? t.passport_country : d.passport_country }, { k: 'passport_expiry', l: 'Passport expires', t: 'date', v: t ? t.passport_expiry : '' },
    cents({ k: 'budget_night_cents', l: `Cap per night (${t ? t.home_currency : d.home_currency}, group) — ask before suggesting places (G02)`, v: t ? t.budget_night_cents : null }),
    cents({ k: 'budget_leg_cents', l: 'Cap per leg (group)', v: t ? t.budget_leg_cents : null }), cents({ k: 'budget_day_cents', l: 'Cap per day (group)', v: t ? t.budget_day_cents : null }),
  ].map(f => f.t === 'cents' ? { ...f, t: 'number', _cents: true } : f);
  form(t ? 'Trip settings' : 'New trip', F, async out => {
    for (const f of F) if (f._cents && out[f.k] != null) out[f.k] = Math.round(out[f.k] * 100);
    out.travelers = out.travelers ? out.travelers.split(',').map(s => s.trim()).filter(Boolean) : [];
    const clear = t ? Object.keys(out).filter(k => out[k] == null && t[k] != null && !['name', 'purpose', 'headcount', 'home_currency', 'travelers', 'handling', 'may_contact'].includes(k)) : [];
    for (const k of Object.keys(out)) if (out[k] == null) delete out[k];
    const r = t ? await act('trips.update', { id: t.id, clear, ...out }) : await act('trips.create', out);
    if (!t) { S.id = r.id; try { localStorage.setItem('trips.id', S.id); } catch (x) {} }
    toast(r.setup_missing && r.setup_missing.length ? 'Saved. Still to set up: ' + r.setup_missing.join('; ') : 'Saved.', 6000);
    await refresh();
  });
}

// ---------- new trip: the five onboarding questions (v5 of the brief) ------------------
function tripWizard() {
  const d = words(), A = { purpose: 'personal', headcount: 2, travelers: '', name: '', region_pack: '', start_date: '', end_date: '', date_flex: 'fixed', budget_night: '', purpose_note: '', booked: '', handling: 'check_my_plan', may_contact: false };
  const panel = $('#p-new'); let step = 0, region = null;
  const TITLES = ["Who's going?", 'Where, and when?', 'Your budget', "What's already booked", 'How much help you want'];
  const NEXT = ['Next: where and when', 'Next: budget', "Next: what's booked", 'Next: how much help', 'Start the trip'];
  const STEPS = [
    { q: "Who's going?", why: 'Sets the group size, so every price shows per person and for the group, and turns work tagging on or off.', body: () => `
      <div class="grid"><div><label class="f">How many are going</label><input type="number" name="headcount" min="1" value="${A.headcount}"></div><div><label class="f">Names (optional)</label><input type="text" name="travelers" value="${esc(A.travelers)}" placeholder="you, and who else"></div></div>
      <label class="f">What kind of trip</label>${d.purposes.map(([v, l]) => `<label class="opt"><input type="radio" name="purpose" value="${v}" ${A.purpose === v ? 'checked' : ''}><div><b>${esc(l)}</b><span>${v === 'work' ? 'Everything is tagged work and company pays unless you say otherwise.' : v === 'mixed' ? 'Tag each thing work or personal; costs split into company pays and you pay.' : 'Just you and yours.'}</span></div></label>`).join('')}`,
      take: fd => { A.headcount = Number(fd.get('headcount')) || 1; A.travelers = fd.get('travelers'); A.purpose = fd.get('purpose'); } },
    { q: 'Where, and when?', why: "A rough idea is fine. If you're not sure, we'll show you where the same trip costs less and what the season is like.", body: () => `
      <div class="grid"><div><label class="f">Where</label><input type="text" name="name" value="${esc(A.name)}" placeholder="Thailand · Bangkok, Krabi, Phuket"></div><div><label class="f">Local tips for</label><select name="region_pack">${[['', 'no pack yet']].concat(S.opt.regions.map(r => [r.id, r.name])).map(([v, l]) => `<option value="${v}" ${A.region_pack === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></div></div>
      <div class="grid"><div><label class="f">From</label><input type="date" name="start_date" value="${A.start_date}"></div><div><label class="f">To</label><input type="date" name="end_date" value="${A.end_date}"></div></div>
      <div style="margin-top:14px">${[['fixed', 'Dates are fixed', 'A client day or a wedding sets them.'], ['flexible', 'Dates can move a week or two', "We'll show you the cheaper weeks and what the weather is like."], ['unsure', 'Not sure where yet', 'See places where the same trip costs less, with the weather for your dates.']].map(([v, t, w]) => `<label class="opt"><input type="radio" name="date_flex" value="${v}" ${A.date_flex === v ? 'checked' : ''}><div><b>${t}</b><span>${w}</span></div></label>`).join('')}</div>`,
      take: fd => { A.name = fd.get('name'); A.region_pack = fd.get('region_pack'); A.start_date = fd.get('start_date'); A.end_date = fd.get('end_date'); A.date_flex = fd.get('date_flex'); },
      check: () => (A.name && A.name.trim()) || A.date_flex === 'unsure' ? null : 'Where to? A rough idea is fine, or pick "Not sure where yet".' },
    { q: 'Your budget', why: "Stops the app suggesting a $317 flight to someone who won't pay it, and tells it what matters when comparing places.", body: () => `
      <div class="grid"><div><label class="f">A night for everyone, at most (${esc(d.home_currency)})</label><input type="number" name="budget_night" value="${A.budget_night}" placeholder="80"></div></div>
      <label class="f">What matters most</label><input type="text" name="purpose_note" value="${esc(A.purpose_note)}" placeholder="beaches, snorkeling, nightlife, gyms, quiet mornings, meetings downtown">`,
      take: fd => { A.budget_night = fd.get('budget_night'); A.purpose_note = fd.get('purpose_note'); } },
    { q: "What's already booked", why: 'The checks start right away: on day one the app can say "your taxi is booked before you land". Paste confirmation details here; they are kept on the trip with a task to enter them.', body: () => `
      <label class="f">Paste or list what is booked (optional)</label><textarea name="booked" rows="6" placeholder="Nok Air DD130 DMK→KBV Nov 17 5:20 PM, conf ABC123&#10;Nomads Ao Nang Nov 17–20, conf NM-778">${esc(A.booked)}</textarea>`,
      take: fd => { A.booked = fd.get('booked'); } },
    { q: 'How much help you want', why: 'You plan it; we make sure nothing breaks. This is also where you allow the text-then-call confirmations; nothing is sent without your OK each time.', body: () => `
      ${d.handling.map(([v, l]) => `<label class="opt"><input type="radio" name="handling" value="${v}" ${A.handling === v ? 'checked' : ''}><div><b>${esc(l)}</b><span>${v === 'plan_for_me' ? 'Suggest routes, stays and activities; you approve.' : v === 'check_my_plan' ? 'You plan; it checks, reminds and confirms.' : 'Only deadlines and the day-of leave-by times.'}</span></div></label>`).join('')}
      <label class="opt" style="margin-top:8px"><input type="checkbox" name="may_contact" ${A.may_contact ? 'checked' : ''}><div><b>It may message, then call, businesses for me</b><span>Message first; a call only if there is no reply, and the call says it is automated.</span></div></label>`,
      take: fd => { A.handling = fd.get('handling'); A.may_contact = fd.has('may_contact'); } },
  ];
  const wizPlace = () => { if (!A.name) return region ? region.name : ''; const parts = A.name.split('·'); return (parts[1] || parts[0]).split(',')[0].trim(); };
  const side = () => {
    const place = wizPlace();
    const seasons = region && region.sections ? (region.sections['Seasons'] || []) : [];
    const entry = region && region.sections ? Object.entries(region.sections).find(([k]) => k.startsWith('Entry rules')) : null;
    return `<div class="ph" id="wiz-photo"></div>
      ${seasons.length ? `<div class="info"><span class="k">Season${A.start_date ? ', ' + esc(fmtD(A.start_date)) + (A.end_date ? ' – ' + esc(fmtD(A.end_date)) : '') : ''}</span>${seasons.slice(0, 2).map(l => `<p>${esc(l)}</p>`).join('')}<div class="src">${esc(region.name)} local tips</div></div>` : place ? `<div class="info"><span class="k">Season</span><p>No season notes for ${esc(place)} yet. They arrive with a local-tips pack for the country.</p></div>` : ''}
      ${entry ? `<div class="info"><span class="k">Before you go</span><p>${esc(entry[1][0])}</p><div class="src">${esc(entry[0])}</div></div>` : ''}`;
  };
  const draw = () => {
    const st = STEPS[step];
    panel.innerHTML = `<div class="wiz-top"><div class="small">New trip</div><a href="#" id="wz-later">Save and finish later</a></div>
      <div class="wiz"><aside class="rail"><h4>Five questions</h4>${TITLES.map((t, i) => `<div class="step ${i === step ? 'on' : ''} ${i < step ? 'done' : ''}"><i>${i < step ? '✓' : i + 1}</i>${esc(t)}</div>`).join('')}<p>That's all we need to start. We'll ask about passports or spending limits only if they come up.</p></aside>
      <form id="wz-form"><div class="k">${step + 1} of ${STEPS.length}</div><h1>${esc(st.q)}</h1><div class="why">${esc(st.why)}</div>${st.body()}
        <div class="nav"><button type="button" class="sbtn ghost" id="wz-back">${step ? 'Back' : 'Cancel'}</button><button type="submit" class="sbtn gold" id="wz-next">${NEXT[step]}</button></div></form>
      <aside class="side" id="wz-side">${side()}</aside></div>`;
    const place = wizPlace();
    if (place) App.photo(place, $('#wiz-photo')); else { $('#wiz-photo').classList.add('photo'); $('#wiz-photo').innerHTML = '<span>Where to?</span>'; }
    $('#wz-back').onclick = () => { if (!step) return close(); step--; draw(); };
    $('#wz-later').onclick = e => { e.preventDefault(); st.take(new FormData($('#wz-form'))); finish(true); };
    const sel = panel.querySelector('select[name="region_pack"]'); if (sel) sel.onchange = async () => { A.region_pack = sel.value; region = A.region_pack ? await api('GET', `/v1/trips/helper/regions/${A.region_pack}`).catch(() => null) : null; $('#wz-side').innerHTML = side(); const pl = wizPlace(); if (pl) App.photo(pl, $('#wiz-photo')); };
    const nm = panel.querySelector('input[name="name"]'); if (nm) nm.onchange = () => { A.name = nm.value; const pl = wizPlace(); if (pl) App.photo(pl, $('#wiz-photo')); };
    $('#wz-form').onsubmit = e => { e.preventDefault(); st.take(new FormData(e.target)); const bad = st.check && st.check(); if (bad) return toast(bad, 4000); if (step < STEPS.length - 1) { step++; draw(); } else finish(false); };
  };
  const close = () => { panel.classList.remove('on'); panel.innerHTML = ''; $('#hero').style.display = ''; document.querySelector('.sidebar').style.display = ''; if (location.hash === '#new') history.replaceState(null, '', location.pathname); showTab(S.tab || 'timeline'); };
  async function finish(partial) {
    try {
      const name = (A.name && A.name.trim()) || (A.date_flex === 'unsure' ? 'Somewhere, not sure yet' : 'New trip');
      const payload = { name, purpose: A.purpose, headcount: A.headcount, travelers: (A.travelers || '').split(',').map(x => x.trim()).filter(Boolean), purpose_note: A.purpose_note || null, handling: A.handling, may_contact: A.may_contact, date_flex: A.date_flex };
      if (A.region_pack) payload.region_pack = A.region_pack;
      if (A.start_date) payload.start_date = A.start_date; if (A.end_date) payload.end_date = A.end_date;
      if (A.budget_night) payload.budget_night_cents = Math.round(Number(A.budget_night) * 100);
      for (const k of Object.keys(payload)) if (payload[k] == null) delete payload[k];
      const r = await act('trips.create', payload);
      if (A.booked && A.booked.trim()) { await act('trips.add_note', { trip_id: r.id, body: 'Already booked (from setup):\n' + A.booked.trim() }); await act('trips.add_task', { trip_id: r.id, title: 'Enter the bookings you pasted at setup, so the checks can see them', kind: 'todo', due: new Date(Date.now() + 2 * 864e5).toISOString().slice(0, 10) }); }
      if (A.date_flex === 'unsure') await act('trips.add_task', { trip_id: r.id, title: 'Pick where: compare the same trip in a few places (Destinations → Compare), then set the dates', kind: 'todo' });
      if (partial) await act('trips.add_task', { trip_id: r.id, title: 'Finish the five setup questions (Trip settings)', kind: 'todo' });
      await act('trips.run_checks', { trip_id: r.id });
      S.id = r.id; try { localStorage.setItem('trips.id', S.id); } catch (x) {}
      toast(partial ? 'Saved. Finish the questions any time in Trip settings.' : (r.setup_missing && r.setup_missing.length ? 'Started. Still to set up: ' + r.setup_missing.join('; ') : 'Started.'), 6000);
      close(); await refresh(); showTab('timeline');
    } catch (x) { toast(x.message, 6000); }
  }
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('on')); panel.classList.add('on'); $('#hero').style.display = 'none'; document.querySelector('.sidebar').style.display = 'none';
  const q = new URLSearchParams(location.search); if (q.get('place')) A.name = q.get('place');
  draw(); window.scrollTo(0, 0);
}

// ---------- item form ---------------------------------------------------------------------
function itemForm(it, day, pre) {
  const d = words(), tz = S.plan.time_zone; pre = pre || {};
  const F = [
    { k: 'kind', l: 'Kind', t: 'select', o: S.opt.kind_list.map(k => [k, k]), v: it ? it.kind : (pre.kind || 'flight') },
    { k: 'status', l: 'Status', t: 'select', o: d.statuses, v: it ? it.status : 'to_book' },
    { k: 'title', l: 'Title', v: it ? it.title : '', wide: true, ph: 'Nok Air DD 130 DMK → KBV / Nomads Ao Nang / 4 Islands half-day tour' },
    { k: 'from_place', l: 'From (or the area)', v: it ? it.from_place : '' }, { k: 'to_place', l: 'To', v: it ? it.to_place : '' },
    { k: 'start_at', l: `Starts (local${tz ? ', ' + tz : ''}; stays: check-in day)`, t: 'datetime', v: it ? it.start_at : (day ? (pre.kind === 'stay' ? day + 'T15:00' : day + 'T09:00') : '') }, { k: 'end_at', l: 'Ends / arrives / check-out', t: 'datetime', v: it ? it.end_at : (pre.end ? pre.end + 'T11:00' : '') },
    { k: 'price', l: 'Price', t: 'number', v: it && it.price_cents != null ? it.price_cents / 100 : '' }, { k: 'currency', l: 'Currency', v: it ? it.currency : (S.plan.trip.local_currency || home()) },
    { k: 'basis', l: 'Per person or group? (always say which, G03)', t: 'select', o: [['', 'not said yet'], ['per_person', 'per person'], ['group', 'for the group']], v: it ? it.basis : '' },
    { k: 'headcount', l: 'On the booking (blank = everyone)', t: 'number', v: it ? it.headcount : '' },
    { k: 'paid_by', l: 'Who pays', t: 'select', o: d.paid_by, v: it ? it.paid_by : 'me' }, { k: 'tag', l: 'Work or personal', t: 'select', o: d.tags, v: it ? it.tag : (S.plan.trip.purpose === 'work' ? 'work' : 'personal') },
    { k: 'confirmation', l: 'Confirmation number', v: it ? it.confirmation : '' }, { k: 'operator', l: 'Operator (airline, hotel, company)', v: it ? it.operator : '' },
    { k: 'link', l: 'Booking link', v: it ? it.link : '', wide: true },
    { k: 'whatsapp', l: 'WhatsApp', v: it ? it.contact.whatsapp : '' }, { k: 'line', l: 'LINE', v: it ? it.contact.line : '' }, { k: 'phone', l: 'Phone', v: it ? it.contact.phone : '' }, { k: 'email', l: 'Email', v: it ? it.contact.email : '' },
    { k: 'last_departure', l: 'Last departure of the day (HH:MM)', v: it ? it.last_departure : '', ph: '15:30' }, { k: 'desk_hours', l: 'Front desk hours (stays)', v: it ? it.desk_hours : '', ph: '24h' },
    { k: 'lead_minutes', l: 'Minutes to get to the start point', t: 'number', v: it ? it.lead_minutes : '' }, { k: 'international', l: 'International flight (longer airport buffer)', t: 'check', v: it ? it.international : false },
    { k: 'notes', l: 'Notes', t: 'textarea', v: it ? it.notes : '', wide: true },
  ];
  if (it) F.push({ k: 'price_checked', l: 'I re-checked the price today (G05)', t: 'check', v: false });
  form(it ? 'Edit item' : 'Add to the plan', F, async out => {
    const contact = { whatsapp: out.whatsapp, line: out.line, phone: out.phone, email: out.email };
    for (const k of Object.keys(contact)) if (!contact[k]) delete contact[k];
    const payload = { ...out, contact, price_cents: out.price == null ? null : Math.round(out.price * 100) };
    for (const k of ['whatsapp', 'line', 'phone', 'email', 'price']) delete payload[k];
    if (payload.start_at) payload.start_at = payload.start_at.slice(0, 16);
    if (payload.end_at) payload.end_at = payload.end_at.slice(0, 16);
    if (it) {
      const clear = Object.keys(payload).filter(k => payload[k] == null && it[k] != null && !['kind', 'title', 'status', 'paid_by', 'tag'].includes(k));
      for (const k of Object.keys(payload)) if (payload[k] == null) delete payload[k];
      await act('trips.update_item', { id: it.id, clear, ...payload });
    } else {
      for (const k of Object.keys(payload)) if (payload[k] == null) delete payload[k];
      await act('trips.add_item', { trip_id: S.id, ...payload });
    }
    await act('trips.run_checks', { trip_id: S.id });
    toast('Saved and re-checked.'); await refresh();
  }, it ? `<div class="row" style="margin-bottom:6px"><button type="button" class="sbtn mini" id="del-item">Remove</button><button type="button" class="sbtn mini" id="ask-item">Confirm something with them…</button></div>` : '');
  if (it) {
    $('#del-item').onclick = async () => { if (!confirm('Remove this item? (undoable from history)')) return; await act('trips.delete_item', { id: it.id }); $('#form').close(); await act('trips.run_checks', { trip_id: S.id }); await refresh(); };
    $('#ask-item').onclick = () => { $('#form').close(); confirmForm(it); };
  }
}
function openItem(id) {
  const it = S.plan.items.find(x => x.id === id); if (!it) return;
  const price = it.group_cents != null ? `${amt(it.group_cents, it.currency)} for ${it.headcount_used}${it.per_person_cents != null && it.headcount_used > 1 ? ` · ${amt(it.per_person_cents, it.currency)} each` : ''}${it.home_cents != null && it.currency !== home() ? ` · ≈ ${money(it.home_cents)}` : ''}${it.basis ? '' : ' <span class="badge hand">per person or group?</span>'}` : 'no price yet';
  App.detail(esc(it.title), `<div class="links">${it.links.map(l => `<a href="${esc(l.url)}" target="_blank">${esc(l.label)} ↗</a>`).join('')}</div>
    <table class="t"><tr><td>Kind</td><td>${esc(it.kind)} ${statusTag(it.status)}</td></tr>
    <tr><td>When</td><td>${esc(dOf(it.start_at))} ${esc(tOf(it.start_at))}${it.end_at ? ' → ' + esc(dOf(it.end_at)) + ' ' + esc(tOf(it.end_at)) : ''}</td></tr>
    ${it.from_place || it.to_place ? `<tr><td>Where</td><td>${esc(it.from_place || '')}${it.to_place ? ' → ' + esc(it.to_place) : ''}</td></tr>` : ''}
    <tr><td>Price</td><td>${price}</td></tr><tr><td>Who pays</td><td>${esc(label(words().paid_by, it.paid_by))} · ${esc(label(words().tags, it.tag))}</td></tr>
    ${it.confirmation ? `<tr><td>Confirmation</td><td class="mono">${esc(it.confirmation)}</td></tr>` : ''}${it.operator ? `<tr><td>Operator</td><td>${esc(it.operator)} <span class="small">${esc(Object.entries(it.contact).map(([k, v]) => k + ' ' + v).join(' · '))}</span></td></tr>` : ''}
    ${it.leave ? `<tr><td>Timing</td><td class="leave">${esc(it.leave.words)}</td></tr>` : ''}${it.last_departure ? `<tr><td>Last one of the day</td><td>${esc(it.last_departure)}</td></tr>` : ''}
    ${it.notes ? `<tr><td>Notes</td><td>${esc(it.notes)}</td></tr>` : ''}</table>
    ${it.findings.length ? `<h3 style="margin:12px 0 6px">The checker says</h3>${it.findings.map(f => finding(f)).join('')}` : ''}
    ${it.confirmations.length ? `<h3 style="margin:12px 0 6px">Confirmations</h3>${it.confirmations.map(c => `<div class="small">${esc(c.status)} · ${esc(c.channel)} · ${esc(c.question)}${c.reply ? ' → ' + esc(c.reply) : ''}</div>`).join('')}` : ''}
    <div class="row" style="margin-top:12px"><button class="sbtn gold mini" id="edit-item">Edit</button><button class="sbtn mini" id="confirm-item">Confirm something with them…</button><button class="sbtn mini" id="expense-item">Log what was paid</button></div>`);
  $('#edit-item').onclick = () => { $('#detail').close(); itemForm(it); };
  $('#confirm-item').onclick = () => { $('#detail').close(); confirmForm(it); };
  $('#expense-item').onclick = () => { $('#detail').close(); expenseForm(it); };
}

// ---------- timeline -------------------------------------------------------------------------
function noTrip(sel) { if (!S.plan && S.trips.length === 0 && !$('#p-new').classList.contains('on')) { tripWizard(); return; } $(sel).innerHTML = `<div class="card"><h3>No trip yet</h3><div>Start one: five questions (who's going, where and when, the budget and what matters, what's already booked, how much to handle), then the checker watches the plan as you add to it.</div><div class="row" style="margin-top:10px"><button class="sbtn gold" id="first-trip">+ New trip</button></div></div>`; $('#first-trip').onclick = () => tripWizard(); }
function itemLine(it) {
  const parts = [];
  if (it.kind === 'flight') { if (it.start_at) parts.push(`Leaves ${tOf(it.start_at)}`); if (it.end_at) parts.push(`lands ${tOf(it.end_at) || dOf(it.end_at)}`); if (it.leave) parts.push(`be at ${esc((it.from_place || 'the airport').split(/[(,]/)[0].trim())} by ${tOf(it.leave.be_there_by)}`); }
  else if (it.is_stay) { const n = it.start_at && it.end_at ? Math.round((new Date(it.end_at.slice(0, 10)) - new Date(it.start_at.slice(0, 10))) / 864e5) : null; if (n) parts.push(`${n} night${n === 1 ? '' : 's'}`); if (it.end_at) parts.push(`check-out ${dOf(it.end_at)}`); if (it.desk_hours) parts.push(`front desk ${esc(it.desk_hours)}`); }
  else { if (it.start_at && it.start_at.length > 10) parts.push(`${tOf(it.start_at)}${it.end_at ? ' – ' + (tOf(it.end_at) || dOf(it.end_at)) : ''}`); if (it.leave && it.leave.lead_minutes) parts.push(`<span class="leave">leave by ${tOf(it.leave.leave_by)}</span>`); if (it.from_place || it.to_place) parts.push(esc(it.from_place || '') + (it.to_place ? ' → ' + esc(it.to_place) : '')); }
  if (it.confirmation) parts.push(`booking code ${esc(it.confirmation)}`);
  if (it.last_departure) parts.push(`last one of the day ${esc(it.last_departure)}`);
  const f = it.findings[0];
  if (f) parts.push(`<span class="${f.severity === 'blocker' ? 'bad' : 'muted'}">${esc(f.message.replace(it.title + ' ', '').replace(it.title + ': ', ''))}</span>${f.fix_action && f.fix_action.label ? ` · <span class="fixlink" data-fix="${f.id}">${esc(f.fix_action.label)}</span>` : ''}`);
  return parts.join(' · ');
}
function priceBlock(it) {
  if (it.price_cents === 0) return `<span class="small">free</span>`;
  if (it.group_cents == null) return it.status === 'cancelled' ? '' : `<span class="fixlink addprice" data-price="${it.id}">Add price</span>`;
  const main = it.basis === 'per_person' && it.per_person_cents != null ? cur(it.per_person_cents, it.currency) : cur(it.group_cents, it.currency);
  return `${esc(main)}<small>${it.basis === 'per_person' ? 'each' : it.headcount_used > 1 ? `for ${it.headcount_used === 2 ? 'both' : 'all ' + it.headcount_used}` : 'for you'} · ${paysWord(it.paid_by)}${it.home_cents != null && it.currency !== home() ? ` · ≈ ${money0(it.home_cents)}` : ''}</small>`;
}
function itemRow(it) {
  const flag = flagOf(it), stat = flag === 'blocker' ? '<span class="st fix">Fix now</span>' : statusTag(it.status);
  return `<div class="it flag-${flag} ${it.is_stay ? 'is-stay' : ''}" data-item="${it.id}"><div class="glyph">${glyph(it.kind, it.tag)}</div>
    <div><div class="ti">${esc(it.title)}${stat}${it.tag === 'work' ? '<span class="st work">Work</span>' : ''}</div><div class="su">${itemLine(it)}</div></div>
    <div class="pr">${priceBlock(it)}</div></div>`;
}
function spans(p) {
  /* Consecutive days under the same stay (or none) become one chapter. The last day, with no night, is its own. */
  const out = []; let cur = null;
  for (const d of p.days) {
    const key = d.night ? d.night.item_id : (d.date >= (p.trip.end_date || '') ? 'last' : 'none');
    if (!cur || cur.key !== key) { cur = { key, night: d.night, days: [] }; out.push(cur); }
    cur.days.push(d);
  }
  return out;
}
function chapters(p) {
  return spans(p).map(c => `<a href="#d-${c.days[0].date}" data-jump="d-${c.days[0].date}">${esc(c.key === 'last' ? 'Last day' : c.night ? c.night.title.split(/[,(]/)[0].trim() : 'No stay yet')} · ${esc(fmtD(c.days[0].date))}${c.days.length > 1 ? '–' + esc(fmtD(c.days[c.days.length - 1].date).split(' ')[1]) : ''}</a>`).join('');
}
function dayKind(items) { if (items.some(i => i.is_leg)) return 'travel'; if (items.some(i => i.tag === 'work')) return 'work'; if (!items.length) return 'free'; return items.length === 1 ? items[0].kind : 'busy'; }
function contRow(it) {
  return `<div class="it cont flag-${flagOf(it)}" data-item="${it.id}"><div class="glyph">${glyph(it.kind, it.tag)}</div><div><div class="ti">${esc(it.kind === 'flight' ? 'lands' : 'arrives')}: ${esc(it.title)}</div><div class="su">${it.end_at ? esc(tOf(it.end_at) || dOf(it.end_at)) : ''}${it.to_place ? ' · ' + esc(it.to_place) : ''} · started ${esc(dOf(it.start_at))}</div></div><div class="pr"></div></div>`;
}
function dayRows(c, p, byId) {
  const stayId = c.night ? c.night.item_id : null;
  const rows = [], dayNo = d => p.days.indexOf(d) + 1;
  let i = 0;
  while (i < c.days.length) {
    const d = c.days[i];
    const items = d.items.map(id => byId[id]).filter(it => it.id !== stayId);
    const arriving = p.items.filter(it => !it.is_stay && it.end_day && it.end_day === d.date && it.day && it.day !== d.date && it.status !== 'cancelled');
    if (!items.length && !arriving.length && d.date !== p.today) {
      let j = i; while (j + 1 < c.days.length && !c.days[j + 1].items.some(id => id !== stayId) && c.days[j + 1].date !== p.today && !p.items.some(it => !it.is_stay && it.end_day === c.days[j + 1].date && it.day !== c.days[j + 1].date)) j++;
      const n = j - i + 1, first = c.days[i], last = c.days[j];
      rows.push(`<div class="day free"><div class="d-lab">${esc(first.label.split(' ')[0])}${n > 1 ? '–' + esc(last.label.split(' ')[0]) : ''}<small>${esc(first.label.slice(4))}${n > 1 ? ' – ' + esc(last.label.slice(4)) : ''} · ${n > 1 ? 'days ' + dayNo(first) + '–' + dayNo(last) : 'day ' + dayNo(first)}</small></div><div class="d-items"><span>${n > 1 ? `${n} free days` : 'Nothing planned yet'}</span><span class="fixlink" data-add="${first.date}">Add something</span></div></div>`);
      i = j + 1; continue;
    }
    rows.push(`<div class="day ${d.date === p.today ? 'today' : ''}"><div class="d-lab">${esc(d.label.split(' ')[0])}<small>${esc(d.label.slice(4))} · day ${dayNo(d)} · ${dayKind(items)}${d.date === p.today ? ' · today' : ''}</small></div><div class="d-items">${arriving.map(contRow).join('')}${items.map(itemRow).join('') || (arriving.length ? '' : `<div class="it empty"><span>Nothing planned yet</span><span class="fixlink" data-add="${d.date}">Add something</span></div>`)}</div></div>`);
    i++;
  }
  return rows.join('');
}
function chapterBlock(c, p, byId) {
  const first = c.days[0], last = c.days[c.days.length - 1], n = c.days.length;
  const range = `${fmtD(first.date)}${n > 1 ? ' – ' + fmtD(last.date) : ''}`;
  let head;
  if (c.key === 'last') head = `<div class="ch-span">Last day · ${esc(range)}</div>`;
  else if (!c.night) head = `<div class="ch-span">No stay yet · ${esc(range)} · ${n} night${n === 1 ? '' : 's'}</div><div class="ch-head" style="cursor:default"><div></div><div><div class="ch-title">Nowhere to sleep ${n === 1 ? 'on ' + esc(fmtD(first.date)) : 'from ' + esc(fmtD(first.date)) + ' to ' + esc(fmtD(last.date))}</div><div class="ch-meta">Add the stay, or mark the night as covered (a night bus, a friend's place).</div></div><div><button class="sbtn mini gold" data-addstay="${first.date}" data-end="${last.date}">Add a stay</button></div></div>`;
  else {
    const it = byId[c.night.item_id];
    const nights = it.start_at && it.end_at ? Math.round((new Date(it.end_at.slice(0, 10)) - new Date(it.start_at.slice(0, 10))) / 864e5) : n;
    const meta = [`${nights} night${nights === 1 ? '' : 's'}`, it.start_at && it.start_at.length > 10 ? `check-in ${tOf(it.start_at)}` : '', it.end_at ? `check-out ${dOf(it.end_at)}` : '', it.desk_hours ? `front desk ${esc(it.desk_hours)}` : '', it.confirmation ? `booking code ${esc(it.confirmation)}` : '', it.operator && it.operator !== it.title ? esc(it.operator) : ''].filter(Boolean);
    const f = it.findings[0];
    if (f) meta.push(`<span class="${f.severity === 'blocker' ? 'bad' : 'muted'}">${esc(f.message.replace(it.title + ' ', '').replace(it.title + ': ', ''))}</span>${f.fix_action && f.fix_action.label ? ` · <span class="fixlink" data-fix="${f.id}">${esc(f.fix_action.label)}</span>` : ''}`);
    head = `<div class="ch-span">${esc(range)}</div><div class="ch-head" data-item="${it.id}"><div class="ph" data-photo="${esc((it.from_place || it.title).split(/[,(]/)[0].trim())}"></div>
      <div><div class="ch-title">${esc(it.title)}${flagOf(it) === 'blocker' ? '<span class="st fix">Fix now</span>' : statusTag(it.status)}</div><div class="ch-meta">${meta.join(' · ')}</div></div>
      <div class="pr">${priceBlock(it)}</div></div>`;
  }
  return `<section class="chapter ${c.key === 'none' ? 'nostay' : ''} ${c.key === 'last' ? 'last' : ''}" id="d-${first.date}">${head}<div class="ch-days">${dayRows(c, p, byId)}</div></section>`;
}
function stopBlock(d, p, byId, n) {
  const noStay = !d.night && d.date < (p.trip.end_date || '');
  return `<section class="stop ${d.date === p.today ? 'today' : ''} ${noStay ? 'nostay' : ''}" id="d-${d.date}"><i class="dot"></i>
    <header class="stop-head"><div class="dayname">${esc(d.label.split(' ')[0])} ${esc(d.label.slice(4))}<small>day ${n} · ${dayKind(d.items.map(id => byId[id]))}${d.date === p.today ? ' · today' : ''}</small></div><div class="night ${noStay ? 'warn' : ''}">${d.night ? 'night: ' + esc(d.night.title.split(/[,(]/)[0].trim()) : (noStay ? 'night: no stay yet' : 'last day')}</div></header>
    ${d.items.map(id => itemRow(byId[id])).join('') || `<div class="it empty"><span>Nothing planned yet</span><span class="fixlink" data-add="${d.date}">Add something</span></div>`}</section>`;
}
function findingCard(f, compact) {
  const [head, ...rest] = f.message.split(/(?<=\.)\s/);
  const fa = f.fix_action;
  const btn = fa && fa.label ? `<button class="sbtn mini gold" data-fix="${f.id}">${esc(fa.label)}</button>${fa.alt ? `<button class="sbtn mini" data-fixalt="${f.id}">${esc(fa.alt.label)}</button>` : ''}` : '';
  return `<div class="fd ${f.severity}"><h4>${esc(head)}</h4><div class="fx">${esc(rest.join(' '))}${f.fix ? (rest.length ? ' ' : '') + esc(f.fix) : ''}</div>
    <div class="acts">${btn}<button class="sbtn mini ghost" data-dismiss="${f.id}">Dismiss</button>${f.item_id && !compact ? `<button class="sbtn mini ghost" data-item="${f.item_id}">Open</button>` : ''}<span class="rl dev-only">${esc(f.rule)}</span></div></div>`;
}
async function quickFix(id, alt) {
  const f = S.plan.findings.find(x => x.id === id) || (await api('GET', `/v1/trips/${S.id}/findings?all=true`)).find(x => x.id === id);
  if (!f || !f.fix_action) return;
  const fa = alt ? f.fix_action.alt : f.fix_action;
  if (fa.action) { try { await act(fa.action, fa.payload); await act('trips.run_checks', { trip_id: S.id }); toast('Done.'); await refresh(); } catch (x) { toast(x.message, 5000); } return; }
  if (fa.ui === 'add_stay') { const it = null; itemForm(it, fa.start, { kind: 'stay', end: fa.end }); return; }
  if (fa.ui === 'trip_settings') { tripForm(S.plan.trip); return; }
  if (fa.ui === 'edit_item') { const it = S.plan.items.find(x => x.id === fa.item_id); if (it) itemForm(it); }
}
function wireFixes(root) {
  root.querySelectorAll('[data-fix]').forEach(b => b.onclick = e => { e.stopPropagation(); quickFix(b.dataset.fix, false); });
  root.querySelectorAll('[data-fixalt]').forEach(b => b.onclick = e => { e.stopPropagation(); quickFix(b.dataset.fixalt, true); });
  root.querySelectorAll('[data-dismiss]').forEach(b => b.onclick = async e => { e.stopPropagation(); await act('trips.dismiss_finding', { id: b.dataset.dismiss }); await refresh(); });
}
function costCard(c) {
  const work = c.by_paid_by.company || 0, me = c.by_paid_by.me || 0, split = c.by_paid_by.split || 0, tot = work + me + split || 1;
  return `<div class="costcard"><span class="k">What this trip costs</span><div class="two-nums"><div><b>${money0(c.planned_home_cents)}</b><small>planned${c.headcount > 1 ? `, for ${c.headcount === 2 ? 'both' : 'all ' + c.headcount} of you` : ''}</small></div><div><b>${money0(c.booked_home_cents)}</b><small>already booked</small></div></div>
    ${work || split ? `<div class="bar"><span class="seg" style="width:${work / tot * 100}%;background:var(--color-accent-2-500)"></span><span class="seg" style="width:${split / tot * 100}%;background:var(--color-accent-2-300)"></span><span class="seg" style="width:${me / tot * 100}%;background:var(--color-accent-400)"></span></div><div class="legend"><span><i style="background:var(--color-accent-2-500)"></i>work pays ${money0(work + split / 2)}</span><span><i style="background:var(--color-accent-400)"></i>you pay ${money0(me + split / 2)}</span></div>` : `<div class="small">${c.actual_home_cents ? money0(c.actual_home_cents) + ' spent so far' : 'you pay all of it'}</div>`}
    <div class="row" style="margin-top:10px"><a href="#costs" class="small" data-go="costs">Every line ›</a></div></div>`;
}
function renderTimeline() {
  if (!S.plan) return noTrip('#p-timeline');
  const p = S.plan, byId = Object.fromEntries(p.items.map(i => [i.id, i]));
  const top = p.findings.slice(0, 5);
  $('#p-timeline').innerHTML = `${p.days.length ? `<div class="chapters">${chapters(p)}</div>` : ''}
   <div class="tl"><div>
    ${spans(p).map(c => chapterBlock(c, p, byId)).join('')}
    ${p.unscheduled.length ? `<section class="chapter last"><div class="ch-span">No date yet</div>${p.unscheduled.map(id => itemRow(byId[id])).join('')}</section>` : ''}
    ${!p.days.length && !p.unscheduled.length ? '<div class="card"><div>Nothing in the plan yet. <b>Add something</b>: the first flight, the first stay.</div></div>' : ''}
    </div>
    <aside class="aside"><div class="ah"><h3>Checks</h3><span class="small">${p.findings.length ? 'checked just now' : 'all clear'}</span></div>
     <div class="sev">${p.finding_counts.blocker ? `<span class="b">${p.finding_counts.blocker} fix now</span>` : ''}${p.finding_counts.warn ? `<span class="w">${p.finding_counts.warn} worth a look</span>` : ''}${p.finding_counts.info ? `<span>${p.finding_counts.info} tidy up</span>` : ''}${!p.findings.length ? '<span>Nothing wrong that the checks can see</span>' : ''}</div>
     ${top.map(f => findingCard(f, true)).join('')}
     ${p.findings.length > top.length ? `<a href="#checks" class="small" data-go="checks" style="font-weight:600">See all ${p.findings.length}</a>` : ''}
     ${costCard(p.costs)}</aside></div>
    <div class="help dev-only">Every rule the checker uses is in <a href="/apps/system/web/settings.html#logic">Settings → Logic</a>.</div>`;
  const P = $('#p-timeline');
  P.querySelectorAll('[data-item]').forEach(el => el.onclick = e => { if (e.target.closest('[data-fix],[data-add],[data-addstay],[data-price]')) return; openItem(el.dataset.item); });
  P.querySelectorAll('[data-price]').forEach(a => a.onclick = e => { e.stopPropagation(); const it = S.plan.items.find(x => x.id === a.dataset.price); if (it) { itemForm(it); setTimeout(() => { const f = $('#form input[name="price"]'); if (f) { f.focus(); f.scrollIntoView({ block: "center" }); } }, 150); } });
  P.querySelectorAll('[data-photo]').forEach(el => App.photo(el.dataset.photo, el, 'circle'));
  P.querySelectorAll('[data-add]').forEach(a => a.onclick = e => { e.preventDefault(); e.stopPropagation(); itemForm(null, a.dataset.add); });
  P.querySelectorAll('[data-addstay]').forEach(a => a.onclick = e => { e.stopPropagation(); itemForm(null, a.dataset.addstay, { kind: 'stay', end: new Date(new Date(a.dataset.end + 'T00:00:00').getTime() + 864e5).toISOString().slice(0, 10) }); });
  P.querySelectorAll('[data-jump]').forEach(a => a.onclick = e => { e.preventDefault(); const el = document.getElementById(a.dataset.jump); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  P.querySelectorAll('[data-go]').forEach(a => a.onclick = e => { e.preventDefault(); showTab(a.dataset.go); });
  wireFixes(P);
}

// ---------- checks ----------------------------------------------------------------------------
function finding(f) { return findingCard(f, false); }
async function renderChecks() {
  if (!S.plan) return noTrip('#p-checks');
  const p = S.plan;
  const all = await api('GET', `/v1/trips/${S.id}/findings?all=true`);
  const closed = all.filter(f => f.status !== 'open');
  $('#p-checks').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 class="sec" style="margin:0">Checks</h2><button class="sbtn gold mini" id="recheck">Check the plan now</button></div>
    <div class="kpis"><div class="kpi ${p.finding_counts.blocker ? 'warn' : ''}"><div class="lab">Fix now</div><div class="val">${p.finding_counts.blocker}</div><div class="sub">would cost money or a missed ride</div></div><div class="kpi"><div class="lab">Worth a look</div><div class="val">${p.finding_counts.warn}</div><div class="sub">before you book</div></div><div class="kpi"><div class="lab">Tidy up</div><div class="val">${p.finding_counts.info}</div><div class="sub">small things</div></div></div>
    ${p.findings.map(finding).join('') || '<div class="card"><h3>Nothing wrong that the rules can see</h3><div class="small">Add items with times, places, prices and their basis, and the checker has more to work with.</div></div>'}
    ${closed.length ? `<details style="margin-top:12px"><summary class="small">${closed.length} resolved or dismissed</summary>${closed.map(f => `<div class="small" style="padding:4px 0;border-top:1px solid var(--line)">${esc(f.status)} · ${esc(f.message)} ${f.status === 'dismissed' ? `<button class="sbtn mini" data-undismiss="${f.id}">reopen</button>` : ''}</div>`).join('')}</details>` : ''}
    <div class="help">What it checks: pickups set before the ride they meet has arrived; prices that don't say per person or group; the passenger count against the group; nights with no stay, or two; overlaps; the airport buffer (${p.rules.airport_buffer_minutes.domestic} min domestic, ${p.rules.airport_buffer_minutes.international} international) and gaps under ${p.rules.min_connection_minutes} min between legs; the last departure of the day; late check-ins with no word on the desk; the budget caps; prices older than ${p.rules.price_recheck_days} days; unbooked flights inside ${p.rules.book_flights_weeks_out} weeks; bookings outside the trip dates; passport validity (${p.rules.passport_valid_months} months past the trip); deadlines (${p.rules.deadline_warn_days} days' warning); confirmations with no reply.<span class="dev-only"> The numbers live in Settings → Logic → Trips.</span></div>`;
  $('#recheck').onclick = async () => { const r = await act('trips.run_checks', { trip_id: S.id }); toast(`${r.counts.blocker} blockers, ${r.counts.warn} warnings, ${r.counts.info} notes`); await refresh(); };
  wireFixes($('#p-checks'));
  $('#p-checks').querySelectorAll('[data-undismiss]').forEach(b => b.onclick = async () => { await act('trips.dismiss_finding', { id: b.dataset.undismiss, undo: true }); await refresh(); });
  $('#p-checks').querySelectorAll('[data-item]').forEach(b => b.onclick = () => openItem(b.dataset.item));
}

// ---------- costs ---------------------------------------------------------------------------------
function expenseForm(it) {
  const d = words();
  form(it ? `Log what was paid: ${it.title}` : 'Log an expense', [
    { k: 'amount', l: 'Amount', t: 'number', v: it && it.group_cents != null ? it.group_cents / 100 : '' }, { k: 'currency', l: 'Currency', v: it ? it.currency : (S.plan.trip.local_currency || home()) },
    { k: 'basis', l: 'Per person or group', t: 'select', o: [['group', 'for the group'], ['per_person', 'per person']], v: 'group' }, { k: 'on_date', l: 'On', t: 'date', v: new Date().toISOString().slice(0, 10) },
    { k: 'paid_by', l: 'Who paid', t: 'select', o: d.paid_by, v: it ? it.paid_by : 'me' }, { k: 'tag', l: 'Work or personal', t: 'select', o: d.tags, v: it ? it.tag : 'personal' },
    { k: 'note', l: 'Note', v: '', wide: true },
  ], async out => { await act('trips.log_expense', { trip_id: S.id, item_id: it ? it.id : null, amount_cents: Math.round(out.amount * 100), currency: out.currency, basis: out.basis, on_date: out.on_date, paid_by: out.paid_by, tag: out.tag, note: out.note }); toast('Logged.'); await refresh(); });
}
function renderCosts() {
  if (!S.plan) return noTrip('#p-costs');
  const c = S.plan.costs, w = c.words, H = c.home_currency;
  const row = (l, v, sub) => `<div class="kpi"><div class="lab">${esc(l)}</div><div class="val">${v}</div>${sub ? `<div class="sub">${sub}</div>` : ''}</div>`;
  $('#p-costs').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 class="sec" style="margin:0">Costs <span class="small">in ${esc(H)}</span></h2><button class="sbtn gold mini" id="add-exp">+ Log an expense</button></div>
    <div class="kpis">${row('Planned, whole group', money0(c.planned_home_cents), `${money0(c.booked_home_cents)} booked · ${money0(c.to_book_home_cents)} still to book`)}${row('Each', money0(c.per_person_home_cents), `${c.headcount} going`)}${row('I pay', money0(c.i_pay_home_cents), `company pays ${money0(c.company_pays_home_cents)}`)}${row('Actually spent', money0(c.actual_home_cents), `${c.expenses} expense(s) logged`)}</div>
    <div class="two"><div class="card"><h3>By who pays</h3><table class="t">${Object.entries(c.by_paid_by).map(([k, v]) => `<tr><td>${esc(w.paid_by[k] || k)}</td><td class="num">${money0(v)}</td><td class="num small">spent ${money0(c.actual_by_paid_by[k] || 0)}</td></tr>`).join('')}</table></div>
    <div class="card"><h3>Work vs personal</h3><table class="t">${Object.entries(c.by_tag).map(([k, v]) => `<tr><td>${esc(w.tags[k] || k)}</td><td class="num">${money0(v)}</td><td class="num small">spent ${money0(c.actual_by_tag[k] || 0)}</td></tr>`).join('')}</table></div></div>
    <div class="two"><div class="card"><h3>By kind</h3><table class="t">${Object.entries(c.by_kind).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${money0(v)}</td></tr>`).join('') || '<tr><td class="small">nothing priced yet</td></tr>'}</table></div>
    <div class="card"><h3>By day</h3><table class="t">${Object.entries(c.by_day).sort().map(([k, v]) => `<tr><td>${esc(dOf(k))}</td><td class="num">${money0(v)}</td></tr>`).join('') || '<tr><td class="small">nothing dated and priced yet</td></tr>'}</table></div></div>
    <div class="card"><h3>Every priced line</h3><table class="t"><thead><tr><th>Item</th><th>Status</th><th class="num">Group</th><th class="num">Each</th><th class="num">≈ ${esc(H)}</th><th>Basis</th></tr></thead><tbody>${c.lines.map(l => `<tr><td>${esc(l.title)}</td><td class="small">${esc(l.status)}</td><td class="num">${esc(amt(l.group_cents, l.currency))}</td><td class="num">${esc(amt(l.per_person_cents, l.currency))}</td><td class="num">${l.home_cents != null ? money0(l.home_cents) : '<span class="badge hand">no rate</span>'}</td><td class="small">${l.basis ? esc(l.basis.replace('_', ' ')) : '<span class="badge hand">not said</span>'}</td></tr>`).join('') || '<tr><td class="small">nothing yet</td></tr>'}</tbody></table></div>
    ${S.plan.expenses.length ? `<div class="card"><h3>Logged expenses</h3><table class="t">${S.plan.expenses.map(e => `<tr><td>${esc(fmtD(e.on_date))}</td><td>${esc(e.note || (S.plan.items.find(i => i.id === e.item_id) || {}).title || '')}</td><td class="num">${esc(amt(e.amount_cents, e.currency))} ${e.basis === 'per_person' ? 'each' : ''}</td><td class="small">${esc(w.paid_by[e.paid_by])} · ${esc(w.tags[e.tag])}</td><td><button class="sbtn mini" data-delexp="${e.id}">remove</button></td></tr>`).join('')}</table></div>` : ''}
    <div class="help">${esc(c.card_rate_note)} Idea and cancelled items are left out. A price with no basis is counted as a group total until you say otherwise.</div>`;
  $('#add-exp').onclick = () => expenseForm(null);
  $('#p-costs').querySelectorAll('[data-delexp]').forEach(b => b.onclick = async () => { await act('trips.delete_expense', { id: b.dataset.delexp }); await refresh(); });
}

// ---------- prepare -----------------------------------------------------------------------------
function taskForm() {
  form('Add a task', [{ k: 'title', l: 'What', v: '', wide: true }, { k: 'kind', l: 'Kind', t: 'select', o: S.opt.task_kinds.map(k => [k, k.replace('_', ' ')]), v: 'todo' }, { k: 'due', l: 'Due', t: 'date', v: '' }, { k: 'notes', l: 'Notes', t: 'textarea', v: '', wide: true }],
    async out => { await act('trips.add_task', { trip_id: S.id, ...out }); await act('trips.run_checks', { trip_id: S.id }); toast('Added.'); await refresh(); });
}
function renderPrepare() {
  if (!S.plan) return noTrip('#p-prepare');
  const p = S.plan, open = p.tasks.filter(t => !t.done_at), done = p.tasks.filter(t => t.done_at);
  const task = t => `<div class="tk ${t.done_at ? 'done' : ''}"><input type="checkbox" data-task="${t.id}" ${t.done_at ? 'checked' : ''}><div><div>${esc(t.title)}</div><div class="small">${esc(t.kind.replace('_', ' '))}${t.notes ? ' · ' + esc(t.notes) : ''}</div></div><span class="due">${t.due ? (t.due < p.today && !t.done_at ? '<span style="color:#f08a86">overdue</span> ' : '') + esc(fmtD(t.due)) : ''}</span><button class="sbtn mini" data-deltask="${t.id}" title="remove">×</button></div>`;
  $('#p-prepare').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 class="sec" style="margin:0">Prepare</h2><div class="row"><button class="sbtn gold mini" id="byg">Build my before-you-go list</button><button class="sbtn mini" id="add-task">+ Task</button></div></div>
    <div class="card"><h3>To do <span class="small">${open.length}</span></h3>${open.map(task).join('') || '<div class="small">Nothing open. Build the before-you-go list, or add a task.</div>'}</div>
    ${done.length ? `<div class="card"><h3>Done <span class="small">${done.length}</span></h3>${done.map(task).join('')}</div>` : ''}
    <div class="card"><h3>Still to book</h3>${p.items.filter(i => ['to_book', 'idea', 'check_now'].includes(i.status)).map(itemRow).join('') || '<div class="small">Everything is booked.</div>'}</div>
    <div class="help">The before-you-go list covers entry rules, health, insurance, permits, phone and plug, safety and packing, each with a deadline before you leave, plus the country's arrival-card and visa rules.<span class="dev-only"> W25; the list and lead times are in Settings → Logic → Trips.</span> Deadlines go on the calendar too.</div>`;
  $('#byg').onclick = async () => { const r = await act('trips.before_you_go', { trip_id: S.id }); await act('trips.run_checks', { trip_id: S.id }); toast(r.count ? `${r.count} task(s) added` : 'The list is already there.'); await refresh(); };
  $('#add-task').onclick = taskForm;
  $('#p-prepare').querySelectorAll('[data-task]').forEach(cb => cb.onchange = async () => { await act('trips.complete_task', { id: cb.dataset.task, done: cb.checked }); await act('trips.run_checks', { trip_id: S.id }); await refresh(); });
  $('#p-prepare').querySelectorAll('[data-deltask]').forEach(b => b.onclick = async () => { await act('trips.delete_task', { id: b.dataset.deltask }); await refresh(); });
  $('#p-prepare').querySelectorAll('[data-item]').forEach(el => el.onclick = () => openItem(el.dataset.item));
}

// ---------- run ---------------------------------------------------------------------------------
function renderRun() {
  if (!S.plan) return noTrip('#p-run');
  const p = S.plan, today = p.today, now = new Date();
  const byId = Object.fromEntries(p.items.map(i => [i.id, i]));
  const upcoming = p.items.filter(i => i.start_at && i.status !== 'cancelled' && !i.is_stay && i.start_at.length > 10 && new Date(i.start_at) >= now).sort((a, b) => a.start_at < b.start_at ? -1 : 1);
  const nxt = upcoming[0];
  const days = p.days.filter(d => d.date >= today).slice(0, 2);
  $('#p-run').innerHTML = `${p.trip.stage !== 'run' ? `<div class="help">The trip is in the <b>${esc(label(words().stages, p.trip.stage))}</b> stage. Set it to Run in the header when you are away; this screen is built for those days.</div>` : ''}
    ${nxt ? `<div class="next"><div class="lab">Next move</div><h3>${esc(nxt.title)}</h3><div class="when">${esc(dOf(nxt.start_at))} · ${esc(tOf(nxt.start_at))}${nxt.end_at ? ' → ' + esc(tOf(nxt.end_at) || dOf(nxt.end_at)) : ''}${nxt.leave ? ' · <b>' + esc(nxt.leave.words) + '</b>' : ''}</div>
      <div class="when" style="margin-top:4px">${nxt.from_place || nxt.to_place ? esc(nxt.from_place || '') + (nxt.to_place ? ' → ' + esc(nxt.to_place) : '') : ''}${nxt.confirmation ? ` · <span class="code">${esc(nxt.confirmation)}</span>` : ''}${nxt.operator ? ' · ' + esc(nxt.operator) : ''}</div>
      <div class="links" style="margin-top:12px">${nxt.links.map(l => `<a href="${esc(l.url)}" target="_blank">${esc(l.label)} ↗</a>`).join('')}</div>
      ${nxt.findings.length ? `<div class="small" style="color:#fff;margin-top:4px">⚠ ${esc(nxt.findings[0].message)}</div>` : ''}</div>` : '<div class="card"><div class="small">Nothing timed ahead. Add times to the legs and this screen shows the next move, when to leave, and the confirmation code.</div></div>'}
    ${p.finding_counts.blocker ? `<div class="fd blocker"><b>${p.finding_counts.blocker} blocker(s) open.</b> <a href="#checks" data-go="checks">Fix them first ›</a></div>` : ''}
    <div class="journey">${days.map(d => `<section class="stop ${d.date === today ? 'today' : ''}"><i class="dot"></i><header class="stop-head"><div class="dayname">${esc(d.label.split(' ')[0])}<small>${esc(d.label.slice(4))}${d.date === today ? ' · today' : ''}</small></div><div class="night">${d.night ? '🛏 ' + esc(d.night.title) : ''}</div></header>${d.items.map(id => itemRow(byId[id])).join('') || '<div class="it empty">nothing planned</div>'}</section>`).join('') || '<div class="card"><div class="small">No days left in the plan from today.</div></div>'}</div>
    <div class="two"><div class="card"><h3>Waiting on people</h3>${p.confirmations.filter(c => ['draft', 'sent', 'call'].includes(c.status)).map(c => `<div class="small" style="padding:4px 0;border-top:1px solid var(--line)"><b>${esc(c.status)}</b> · ${esc((byId[c.item_id] || {}).title || '')} · ${esc(c.question)}</div>`).join('') || '<div class="small">Nothing pending.</div>'}</div>
    <div class="card"><h3>Money today</h3><div class="row"><button class="sbtn gold mini" id="run-exp">+ Log what you paid</button></div><div class="small" style="margin-top:8px">Spent so far: ${money0(p.costs.actual_home_cents)} of ${money0(p.costs.planned_home_cents)} planned.</div></div></div>
    <div class="help">Be-there-by allows ${p.rules.airport_buffer_minutes.domestic} min before a domestic flight and ${p.rules.airport_buffer_minutes.international} before an international one; add each leg's travel time (minutes to the start point) and you get a leave-by too. Live traffic is one tap away on Directions.</div>`;
  $('#p-run').querySelectorAll('[data-item]').forEach(el => el.onclick = () => openItem(el.dataset.item));
  const go = $('#p-run [data-go]'); if (go) go.onclick = e => { e.preventDefault(); showTab('checks'); };
  $('#run-exp').onclick = () => expenseForm(null);
}

// ---------- confirm ---------------------------------------------------------------------------
function confirmForm(it) {
  const items = S.plan.items.filter(i => i.status !== 'cancelled');
  form('Confirm something with the business (W27)', [
    { k: 'item_id', l: 'Booking', t: 'select', o: items.map(i => [i.id, i.title]), v: it ? it.id : (items[0] || {}).id, wide: true },
    { k: 'question', l: 'The exact question', t: 'textarea', v: '', wide: true, ph: 'Can you hold our bags from checkout at 11 AM until about 3 PM on Nov 20?' },
    { k: 'channel', l: 'Channel', t: 'select', o: [['', 'guess from their contact']].concat(S.opt.channels.map(c => [c, c])), v: '' },
    { k: 'traveler', l: 'Who is asking', v: S.plan.trip.travelers[0] || '' },
  ], async out => { const r = await act('trips.draft_confirmation', { trip_id: S.id, ...out }); toast(`Drafted (${r.channel}). Send it, then mark it sent.`); await refresh(); showTab('confirm'); });
}
function renderConfirm() {
  if (!S.plan) return noTrip('#p-confirm');
  const p = S.plan, byId = Object.fromEntries(p.items.map(i => [i.id, i]));
  const link = c => { const to = c.to_address, m = encodeURIComponent(c.message); if (!to) return ''; if (c.channel === 'whatsapp') return `https://wa.me/${to.replace(/\D/g, '')}?text=${m}`; if (c.channel === 'sms') return `sms:${to}&body=${m}`; if (c.channel === 'email') return `mailto:${to}?subject=Booking%20question&body=${m}`; if (c.channel === 'call') return `tel:${to}`; return ''; };
  $('#p-confirm').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 class="sec" style="margin:0">Confirm</h2><button class="sbtn gold mini" id="new-conf">+ Ask a business something</button></div>
    <div class="help">Message first (WhatsApp, LINE, text, email, or the booking app), then a call only if there is no reply in time; the call says up front that it's automated. The words are drafted for you and the thread is kept here; you send it.<span class="dev-only"> Hours and templates: Settings → Logic → Trips · confirming a booking.</span></div>
    ${p.confirmations.map(c => `<div class="card"><h3>${esc((byId[c.item_id] || {}).title || 'item')} <span class="st ${c.status === 'answered' ? 'confirmed' : c.status === 'call' ? 'check_now' : 'to_book'}">${esc(c.status)}</span> <span class="small">${esc(c.channel)}${c.to_address ? ' · ' + esc(c.to_address) : ''}</span></h3>
      <div class="small">Asked: ${esc(c.question)}</div><div class="msg" style="margin:6px 0">${esc(c.message)}</div>
      ${c.reply ? `<div><b>Reply:</b> ${esc(c.reply)} <span class="small">${esc(fmtWhen(c.replied_at))}</span></div>` : ''}
      <div class="row" style="margin-top:6px">${link(c) ? `<a class="sbtn mini" href="${esc(link(c))}" target="_blank">Open in ${esc(c.channel)} ↗</a>` : ''}<button class="sbtn mini" data-copy="${c.id}">Copy</button>
      ${c.status === 'draft' ? `<button class="sbtn gold mini" data-sent="${c.id}">Mark sent</button>` : ''}${['sent', 'call', 'draft'].includes(c.status) ? `<button class="sbtn mini" data-answer="${c.id}">Log the reply</button>` : ''}${c.status === 'sent' ? `<button class="sbtn mini" data-noreply="${c.id}">No reply → call</button>` : ''}
      ${c.sent_at ? `<span class="small">sent ${esc(fmtWhen(c.sent_at))}</span>` : ''}</div></div>`).join('') || '<div class="card"><div class="small">Nothing asked yet. Bag holds, late check-ins and pickup times are the usual ones.</div></div>'}`;
  $('#new-conf').onclick = () => confirmForm(null);
  const P = $('#p-confirm');
  P.querySelectorAll('[data-copy]').forEach(b => b.onclick = async () => { const c = p.confirmations.find(x => x.id === b.dataset.copy); try { await navigator.clipboard.writeText(c.message); toast('Copied.'); } catch (e) { toast('Select and copy the text.'); } });
  P.querySelectorAll('[data-sent]').forEach(b => b.onclick = async () => { await act('trips.update_confirmation', { id: b.dataset.sent, status: 'sent' }); await refresh(); });
  P.querySelectorAll('[data-noreply]').forEach(b => b.onclick = async () => { await act('trips.update_confirmation', { id: b.dataset.noreply, status: 'no_reply' }); await act('trips.run_checks', { trip_id: S.id }); await refresh(); });
  P.querySelectorAll('[data-answer]').forEach(b => b.onclick = () => form('Log the reply', [{ k: 'reply', l: 'What they said', t: 'textarea', v: '', wide: true }, { k: 'changed', l: 'This changes the plan (flag the booking Check now)', t: 'check', v: false }],
    async out => { await act('trips.update_confirmation', { id: b.dataset.answer, status: 'answered', reply: out.reply || '', changed: !!out.changed }); await act('trips.run_checks', { trip_id: S.id }); toast('Logged.'); await refresh(); }));
}

// ---------- helper -------------------------------------------------------------------------------
async function renderHelper() {
  if (!S.helper) S.helper = await api('GET', '/v1/trips/helper');
  const h = S.helper, runs = S.plan ? S.plan.workflow_runs : [];
  const byCode = {}; runs.forEach(r => (byCode[r.code] = byCode[r.code] || []).push(r));
  const secs = [['all', 'All']].concat(h.sections.map(s => [s.code, s.label])).concat([['workflows', 'Workflows'], ['guardrails', 'Guardrails'], ['methods', 'Methods'], ['about', 'About the app']]);
  const chips = `<div class="chips" style="margin-bottom:10px">${secs.map(([id, l]) => `<button class="chip ${S.hsec === id ? 'on' : ''}" data-hsec="${id}">${esc(l)}</button>`).join('')}</div>`;
  let body = '';
  if (S.hsec === 'all' || !['workflows', 'guardrails', 'methods', 'about'].includes(S.hsec)) {
    const qs = S.hsec === 'all' ? h.questions : h.questions.filter(q => q.section === S.hsec);
    body += `<div class="card"><h3>Questions <span class="small">${qs.length}, with codes</span></h3>${qs.map(q => `<div class="q"><code>${esc(q.code)}</code>${esc(q.text)}${q.new ? ' <span class="badge hand">NEW</span>' : ''}</div>`).join('')}</div>`;
  }
  if (S.hsec === 'all' || S.hsec === 'workflows') {
    body += `<h2 class="sec">Workflows <span class="small">${esc(h.methods.run_order ? h.methods.run_order[0].text : '')}</span></h2>` + h.workflows.map(w => `<div class="wf"><h4>${esc(w.code)} · ${esc(w.title)}${w.new ? ' <span class="badge hand">NEW</span>' : ''}</h4><div class="small">Runs when: ${esc(w.runs_when)}</div><ol>${w.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol>${w.gives ? `<div class="small">Gives: ${esc(w.gives)}</div>` : ''}<div class="tr">Track record: ${esc(w.track_record || 'not used yet')}${(byCode[w.code] || []).map(r => ` · <b>${esc(S.plan.trip.name)}: ${esc(r.outcome)}</b>${r.note ? ' (' + esc(r.note) + ')' : ''}`).join('')}</div>${S.plan ? `<div class="row" style="margin-top:6px"><button class="sbtn mini" data-log="${w.code}">Log how it went on this trip</button></div>` : ''}</div>`).join('');
  }
  if (S.hsec === 'all' || S.hsec === 'guardrails') body += `<div class="card"><h3>Guardrails</h3>${h.guardrails.map(g => `<div class="q"><code>${esc(g.code)}</code><b>${esc(g.rule)}</b><div class="small">Why: ${esc(g.why)}</div></div>`).join('')}</div>`;
  if (S.hsec === 'all' || S.hsec === 'methods') {
    const grp = (k, title) => h.methods[k] ? `<div class="card"><h3>${esc(title)}</h3>${h.methods[k].map(m => `<div class="q">${m.sub ? `<span class="small">${esc(m.sub)} · </span>` : ''}${m.name ? `<b>${esc(m.name)}:</b> ` : ''}${esc(m.text).replace(/\n/g, '<br>')}${m.new ? ' <span class="badge hand">NEW</span>' : ''}</div>`).join('')}</div>` : '';
    body += grp('setup', 'Set up every new trip (ask once)') + grp('defaults', 'Defaults for every answer') + grp('sources', 'Where the answers come from') + grp('checks', 'Checks') + grp('formats', 'Answer formats that worked') + grp('region_template', 'Region pack template') + grp('changelog', 'Change log');
  }
  if (S.hsec === 'about') body += h.brief.map(b => `<div class="card"><h3>${esc(b.heading)} <span class="small">${esc(b.part.replace(/_/g, ' '))}</span></h3>${b.lines.map(l => `<div class="q">${esc(l)}</div>`).join('')}</div>`).join('');
  $('#p-helper').innerHTML = `<h2 class="sec">The guide <span class="small">${esc(h.meta.title || '')} · ${h.questions.length} questions · ${h.workflows.length} workflows · ${h.guardrails.length} guardrails</span></h2>${chips}${body}
    <div class="help">This is the helper's playbook: the questions it can answer, how it works through each one, and the rules it holds itself to. After a trip, log how each one went, so the next trip goes better.<span class="dev-only"> Developer: the list is data (the pack <span class="mono">packs/helper.sqlite</span>, built from the brief). A Claude chat reaches it through the plug (helper_catalogue, helper_workflow, helper_region) and this trip's plan and checks (trip_plan, trip_checks). W26 turns mistakes into guardrails in the next brief.</span></div>`;
  $('#p-helper').querySelectorAll('[data-hsec]').forEach(b => b.onclick = () => { S.hsec = b.dataset.hsec; renderHelper(); });
  $('#p-helper').querySelectorAll('[data-log]').forEach(b => b.onclick = () => form(`${b.dataset.log}: how did it go?`, [{ k: 'outcome', l: 'Outcome', t: 'select', o: [['proven', 'Proven: booked or decided with it'], ['adopted', 'Adopted: went with it, nothing booked yet'], ['open', 'Open: hit a wall'], ['rejected', 'Rejected: turned it down']], v: 'proven' }, { k: 'note', l: 'Note', v: '', wide: true }],
    async out => { await act('trips.log_workflow', { trip_id: S.id, code: b.dataset.log, ...out }); toast('Logged.'); await loadPlan(); renderHelper(); }));
}

// ---------- region -----------------------------------------------------------------------------
async function renderRegion() {
  const rid = S.plan && S.plan.trip.region_pack;
  if (!rid) { $('#p-region').innerHTML = `<div class="card"><h3>No region pack on this trip</h3><div class="small">Packs so far: ${S.opt.regions.map(r => esc(r.name)).join(', ') || 'none'}. Set one in Trip settings; a new country starts from the template in the Helper → Methods.</div></div>`; return; }
  const r = await api('GET', `/v1/trips/helper/regions/${rid}`);
  $('#p-region').innerHTML = `<h2 class="sec">${esc(r.name)}: local tips <span class="small">${esc(r.currency || '')} · ${esc(r.time_zone || '')} · businesses answer on ${esc(r.channels.join(', '))}</span></h2>
    ${r.intro ? `<div class="help">${esc(r.intro)}</div>` : ''}
    <div class="card"><h3>Sites</h3><table class="t">${r.sites.map(s => `<tr><td><a href="${esc(s.url.includes('{') ? s.url.split('/{')[0] : s.url)}" target="_blank">${esc(s.name)} ↗</a></td><td class="small">${esc(s.means)}</td></tr>`).join('')}</table></div>
    ${Object.entries(r.sections).map(([k, lines]) => `<div class="card"><h3>${esc(k)}</h3>${lines.map(l => `<div class="q">${esc(l)}</div>`).join('')}</div>`).join('')}
    <div class="card"><h3>Worked examples <span class="small">question code → what it looked like here</span></h3>${r.worked_examples.map(e => `<div class="q"><code>${esc(e.code)}</code>${esc(e.text)}</div>`).join('')}</div>
    <div class="help">Local know-how gathered trip by trip: money, airports, the booking sites and their quirks, piers, getting around, how businesses like to be reached, storage, fees, seasons, scams, entry rules.<span class="dev-only"> Reference data from the brief's region pack; after the trip, W26 finishes it for the next version.</span></div>`;
}

App.onMode(() => { if (S.plan) { renderHero(); showTab(S.tab); } });
(async () => {
  try {
    S.opt = await api('GET', '/v1/trips/options');
    const want = new URLSearchParams(location.search).get('trip'); if (want) { S.id = want; try { localStorage.setItem('trips.id', want); } catch (x) {} }
    await loadTrips(); await loadPlan();
    const t = location.hash.slice(1);
    if (t === 'new' || (!S.trips.length && !S.plan)) { showTab('timeline'); tripWizard(); return; }
    showTab(['timeline', 'checks', 'costs', 'prepare', 'run', 'confirm', 'helper', 'region'].includes(t) ? t : 'timeline');
  } catch (e) { App.down('#p-timeline'); }
})();
