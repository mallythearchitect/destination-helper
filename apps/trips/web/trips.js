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
}
async function refresh() { await loadTrips(); await loadPlan(); showTab(S.tab); }
function renderSide() {
  $('#trips').innerHTML = S.trips.map(t => `<button class="${t.id === S.id ? 'on' : ''}" data-trip="${t.id}">${esc(t.name)}<span class="n">${t.findings.blocker ? '⛔ ' + t.findings.blocker : ''}${t.to_book ? ' · ' + t.to_book + ' to book' : ''}</span></button>`).join('') || '<div class="small" style="padding:0 10px">No trips yet.</div>';
  const st = S.plan ? S.plan.trip.stage : null;
  $('#stages').innerHTML = S.opt.defaults.stages.map(([id, l]) => `<button class="${st === id ? 'on' : ''}" data-stage="${id}" ${S.id ? '' : 'disabled'}>${esc(l)}</button>`).join('');
}
$('#trips').addEventListener('click', async e => { const b = e.target.closest('[data-trip]'); if (!b) return; S.id = b.dataset.trip; try { localStorage.setItem('trips.id', S.id); } catch (x) {} await loadPlan(); renderSide(); showTab(S.tab); });
$('#stages').addEventListener('click', async e => { const b = e.target.closest('[data-stage]'); if (!b || !S.id) return; try { await act('trips.set_stage', { id: S.id, stage: b.dataset.stage }); toast(`Stage: ${label(words().stages, b.dataset.stage)}`); await refresh(); } catch (x) { toast(x.message, 5000); } });
$('#new-trip').onclick = () => tripForm();

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
    { k: 'region_pack', l: 'Region pack', t: 'select', o: [['', '—']].concat(S.opt.regions.map(r => [r.id, r.name])), v: t ? t.region_pack : '' },
    { k: 'time_zone', l: 'Destination time zone', v: t ? t.time_zone : '', ph: 'Asia/Bangkok' },
    { k: 'home_currency', l: 'Home currency', v: t ? t.home_currency : d.home_currency }, { k: 'local_currency', l: 'Local currency', v: t ? t.local_currency : '' },
    { k: 'fx_rate', l: 'Rate: local per 1 home', t: 'number', v: t ? t.fx_rate : '' }, { k: 'fx_date', l: 'Rate checked on', t: 'date', v: t ? t.fx_date : '' },
    { k: 'passport_country', l: 'Passport country', v: t ? t.passport_country : d.passport_country }, { k: 'passport_expiry', l: 'Passport expires', t: 'date', v: t ? t.passport_expiry : '' },
    cents({ k: 'budget_night_cents', l: `Cap per night (${t ? t.home_currency : d.home_currency}, group) — ask before suggesting places (G02)`, v: t ? t.budget_night_cents : null }),
    cents({ k: 'budget_leg_cents', l: 'Cap per leg (group)', v: t ? t.budget_leg_cents : null }), cents({ k: 'budget_day_cents', l: 'Cap per day (group)', v: t ? t.budget_day_cents : null }),
  ].map(f => f.t === 'cents' ? { ...f, t: 'number', _cents: true } : f);
  form(t ? 'Trip settings' : 'New trip (W24: the setup questions)', F, async out => {
    for (const f of F) if (f._cents && out[f.k] != null) out[f.k] = Math.round(out[f.k] * 100);
    out.travelers = out.travelers ? out.travelers.split(',').map(s => s.trim()).filter(Boolean) : [];
    const clear = t ? Object.keys(out).filter(k => out[k] == null && t[k] != null && !['name', 'purpose', 'headcount', 'home_currency', 'travelers'].includes(k)) : [];
    for (const k of Object.keys(out)) if (out[k] == null) delete out[k];
    const r = t ? await act('trips.update', { id: t.id, clear, ...out }) : await act('trips.create', out);
    if (!t) { S.id = r.id; try { localStorage.setItem('trips.id', S.id); } catch (x) {} }
    toast(r.setup_missing && r.setup_missing.length ? 'Saved. Still to set up: ' + r.setup_missing.join('; ') : 'Saved.', 6000);
    await refresh();
  });
}

// ---------- item form ---------------------------------------------------------------------
function itemForm(it) {
  const d = words(), tz = S.plan.time_zone;
  const F = [
    { k: 'kind', l: 'Kind', t: 'select', o: S.opt.kind_list.map(k => [k, k]), v: it ? it.kind : 'flight' },
    { k: 'status', l: 'Status', t: 'select', o: d.statuses, v: it ? it.status : 'to_book' },
    { k: 'title', l: 'Title', v: it ? it.title : '', wide: true, ph: 'Nok Air DD 130 DMK → KBV / Nomads Ao Nang / 4 Islands half-day tour' },
    { k: 'from_place', l: 'From (or the area)', v: it ? it.from_place : '' }, { k: 'to_place', l: 'To', v: it ? it.to_place : '' },
    { k: 'start_at', l: `Starts (local${tz ? ', ' + tz : ''}; stays: check-in day)`, t: 'datetime', v: it ? it.start_at : '' }, { k: 'end_at', l: 'Ends / arrives / check-out', t: 'datetime', v: it ? it.end_at : '' },
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
function noTrip(sel) { $(sel).innerHTML = `<div class="card"><h3>No trip yet</h3><div>Start one: it asks who's going and how many, the dates, the budget caps, what the trip is for and the passport, then the checker watches the plan as you add to it.</div><div class="row" style="margin-top:10px"><button class="sbtn gold" id="first-trip">+ New trip</button></div></div>`; $('#first-trip').onclick = () => tripForm(); }
function itemRow(it) {
  return `<div class="it" data-item="${it.id}"><div class="tm">${it.is_stay ? '<small>stay</small>' + (tOf(it.start_at) || 'check-in') : (tOf(it.start_at) || '—')}${it.end_at && !it.is_stay ? `<small>→ ${esc(tOf(it.end_at) || dOf(it.end_at))}</small>` : ''}${it.is_stay && it.end_at ? `<small>→ ${esc(dOf(it.end_at))}</small>` : ''}</div>
    <div><div class="ti">${esc(it.title)}${statusTag(it.status)}${it.findings.some(f => f.severity === 'blocker') ? ' <span class="st" style="border-color:#d9534f;color:#f08a86">check</span>' : ''}</div>
    <div class="su">${esc(it.kind)}${it.from_place || it.to_place ? ' · ' + esc(it.from_place || '') + (it.to_place ? ' → ' + esc(it.to_place) : '') : ''}${it.confirmation ? ' · #' + esc(it.confirmation) : ''}${it.tag === 'work' ? ' · work' : ''}${it.paid_by === 'company' ? ' · company pays' : ''}${it.leave && it.leave.lead_minutes ? ` · <span class="leave">leave by ${esc(tOf(it.leave.leave_by))}</span>` : ''}</div></div>
    <div class="pr">${it.group_cents != null ? esc(amt(it.group_cents, it.currency)) : ''}<small>${it.group_cents != null ? (it.headcount_used > 1 ? `${esc(amt(it.per_person_cents, it.currency))} each` : 'group') + (it.home_cents != null && it.currency !== home() ? ` · ≈ ${money0(it.home_cents)}` : '') : ''}</small></div></div>`;
}
function renderTimeline() {
  if (!S.plan) return noTrip('#p-timeline');
  const p = S.plan, t = p.trip, byId = Object.fromEntries(p.items.map(i => [i.id, i]));
  $('#p-timeline').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><div><h2 class="sec" style="margin:0">${esc(t.name)}</h2><div class="small">${esc(fmtD(t.start_date))}${t.end_date ? ' → ' + esc(fmtD(t.end_date)) : ''} · ${t.headcount} going${t.travelers.length ? ' (' + esc(t.travelers.join(', ')) + ')' : ''} · ${esc(label(words().purposes, t.purpose))}${p.region ? ' · ' + esc(p.region.name) + ' pack' : ''}${t.purpose_note ? ' · ' + esc(t.purpose_note) : ''}</div></div>
    <div class="row"><button class="sbtn gold mini" id="add-item">+ Add to the plan</button><button class="sbtn mini" id="trip-settings">Trip settings</button><a class="sbtn mini" href="/v1/trips/${t.id}/calendar.ics">Calendar file</a><a class="sbtn mini" href="/apps/system/web/browse.html#${t.entity_id}">Record ›</a></div></div>
    ${p.finding_counts.blocker || p.finding_counts.warn ? `<div class="help" style="border-left:3px solid ${p.finding_counts.blocker ? '#d9534f' : 'var(--gold)'};padding-left:10px">The checker has <b>${p.finding_counts.blocker}</b> blocker(s) and <b>${p.finding_counts.warn}</b> warning(s). <a href="#checks" data-go="checks">See them ›</a></div>` : ''}
    ${p.days.map(d => `<div class="day"><div class="dh"><span>${esc(d.label)}${d.date === p.today ? ' <span class="badge verified">today</span>' : ''}</span><span class="night">${d.night ? 'night: ' + esc(d.night.title) : (d.date < (t.end_date || '') ? '<span style="color:var(--gold)">no stay booked</span>' : '')}${d.tasks.length ? ' · ' + d.tasks.length + ' deadline(s)' : ''}</span></div>
      ${d.items.map(id => itemRow(byId[id])).join('') || '<div class="it" style="cursor:default"><div class="tm"></div><div class="su">nothing planned</div></div>'}</div>`).join('')}
    ${p.unscheduled.length ? `<div class="day"><div class="dh"><span>No date yet</span></div>${p.unscheduled.map(id => itemRow(byId[id])).join('')}</div>` : ''}
    <div class="help">Prices show for the group and each; a price with no per-person/group basis is flagged. Times are local to the destination (${esc(p.time_zone || 'no zone set')}). Every rule the checker uses is in <a href="/apps/system/web/settings.html#logic">Settings → Logic</a>.</div>`;
  $('#add-item').onclick = () => itemForm(); $('#trip-settings').onclick = () => tripForm(t);
  $('#p-timeline').querySelectorAll('[data-item]').forEach(el => el.onclick = () => openItem(el.dataset.item));
  const go = $('#p-timeline [data-go]'); if (go) go.onclick = e => { e.preventDefault(); showTab('checks'); };
}

// ---------- checks ----------------------------------------------------------------------------
function finding(f) {
  return `<div class="fd ${f.severity}"><div><b>${esc(f.severity === 'blocker' ? 'Blocker' : f.severity === 'warn' ? 'Warning' : 'Note')}</b> · ${esc(f.message)}</div>${f.fix ? `<div class="fx">Fix: ${esc(f.fix)}</div>` : ''}<div class="row" style="margin-top:4px"><span class="rl">${esc(f.rule)} · first seen ${esc(fmtWhen(f.first_seen))}</span><button class="sbtn mini" data-dismiss="${f.id}">Dismiss</button>${f.item_id ? `<button class="sbtn mini" data-item="${f.item_id}">Open item</button>` : ''}</div></div>`;
}
async function renderChecks() {
  if (!S.plan) return noTrip('#p-checks');
  const p = S.plan;
  const all = await api('GET', `/v1/trips/${S.id}/findings?all=true`);
  const closed = all.filter(f => f.status !== 'open');
  $('#p-checks').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 class="sec" style="margin:0">Checks</h2><button class="sbtn gold mini" id="recheck">Check the plan now</button></div>
    <div class="kpis"><div class="kpi ${p.finding_counts.blocker ? 'warn' : ''}"><div class="lab">Blockers</div><div class="val">${p.finding_counts.blocker}</div><div class="sub">would cost money or a missed ride</div></div><div class="kpi"><div class="lab">Warnings</div><div class="val">${p.finding_counts.warn}</div><div class="sub">worth a look before booking</div></div><div class="kpi"><div class="lab">Notes</div><div class="val">${p.finding_counts.info}</div><div class="sub">housekeeping</div></div></div>
    ${p.findings.map(finding).join('') || '<div class="card"><h3>Nothing wrong that the rules can see</h3><div class="small">Add items with times, places, prices and their basis, and the checker has more to work with.</div></div>'}
    ${closed.length ? `<details style="margin-top:12px"><summary class="small">${closed.length} resolved or dismissed</summary>${closed.map(f => `<div class="small" style="padding:4px 0;border-top:1px solid var(--line)">${esc(f.status)} · ${esc(f.message)} ${f.status === 'dismissed' ? `<button class="sbtn mini" data-undismiss="${f.id}">reopen</button>` : ''}</div>`).join('')}</details>` : ''}
    <div class="help">What it checks: pickups set before the ride they meet has arrived; prices that don't say per person or group; the passenger count against the group; nights with no stay, or two; overlaps; the airport buffer (${p.rules.airport_buffer_minutes.domestic} min domestic, ${p.rules.airport_buffer_minutes.international} international) and gaps under ${p.rules.min_connection_minutes} min between legs; the last departure of the day; late check-ins with no word on the desk; the budget caps; prices older than ${p.rules.price_recheck_days} days; unbooked flights inside ${p.rules.book_flights_weeks_out} weeks; bookings outside the trip dates; passport validity (${p.rules.passport_valid_months} months past the trip); deadlines (${p.rules.deadline_warn_days} days' warning); confirmations with no reply. The numbers live in Settings → Logic → Trips.</div>`;
  $('#recheck').onclick = async () => { const r = await act('trips.run_checks', { trip_id: S.id }); toast(`${r.counts.blocker} blockers, ${r.counts.warn} warnings, ${r.counts.info} notes`); await refresh(); };
  $('#p-checks').querySelectorAll('[data-dismiss]').forEach(b => b.onclick = async () => { await act('trips.dismiss_finding', { id: b.dataset.dismiss }); await refresh(); });
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
  $('#p-prepare').innerHTML = `<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 class="sec" style="margin:0">Prepare</h2><div class="row"><button class="sbtn gold mini" id="byg">Build the before-you-go list (W25)</button><button class="sbtn mini" id="add-task">+ Task</button></div></div>
    <div class="card"><h3>To do <span class="small">${open.length}</span></h3>${open.map(task).join('') || '<div class="small">Nothing open. Build the before-you-go list, or add a task.</div>'}</div>
    ${done.length ? `<div class="card"><h3>Done <span class="small">${done.length}</span></h3>${done.map(task).join('')}</div>` : ''}
    <div class="card"><h3>Still to book</h3>${p.items.filter(i => ['to_book', 'idea', 'check_now'].includes(i.status)).map(itemRow).join('') || '<div class="small">Everything is booked.</div>'}</div>
    <div class="help">W25 creates entry rules, health, insurance, permits, phone, safety and packing tasks with deadlines before departure (the list and lead times are in Settings → Logic → Trips · the before-you-go checklist), plus the region pack's arrival-card and visa lines. Deadlines go on the calendar file too.</div>`;
  $('#byg').onclick = async () => { const r = await act('trips.before_you_go', { trip_id: S.id }); await act('trips.run_checks', { trip_id: S.id }); toast(r.count ? `${r.count} task(s) added` : 'The list is already there.'); await refresh(); };
  $('#add-task').onclick = taskForm;
  $('#p-prepare').querySelectorAll('[data-task]').forEach(cb => cb.onchange = async () => { await act('trips.complete_task', { id: cb.dataset.task, done: cb.checked }); await act('trips.run_checks', { trip_id: S.id }); await refresh(); });
  $('#p-prepare').querySelectorAll('[data-deltask]').forEach(b => b.onclick = async () => { await act('trips.delete_task', { id: b.dataset.deltask }); await refresh(); });
  $('#p-prepare').querySelectorAll('[data-item]').forEach(el => el.onclick = () => openItem(el.dataset.item));
}

// ---------- run ---------------------------------------------------------------------------------
function renderRun() {
  if (!S.plan) return noTrip('#p-run');
  const p = S.plan, today = p.today;
  const days = p.days.filter(d => d.date >= today).slice(0, 2);
  const byId = Object.fromEntries(p.items.map(i => [i.id, i]));
  const legs = days.flatMap(d => d.items.map(id => byId[id])).filter(i => i.is_leg && i.leave);
  $('#p-run').innerHTML = `<h2 class="sec">Run <span class="small">today and tomorrow, live links per leg</span></h2>
    ${p.trip.stage !== 'run' ? `<div class="help">The trip is in the <b>${esc(label(words().stages, p.trip.stage))}</b> stage. Set it to Run on the left when you are away; this tab is built for those days.</div>` : ''}
    ${p.finding_counts.blocker ? `<div class="fd blocker"><b>${p.finding_counts.blocker} blocker(s) open.</b> <a href="#checks" data-go="checks">Fix them first ›</a></div>` : ''}
    ${days.map(d => `<div class="day"><div class="dh"><span>${esc(d.label)}${d.date === today ? ' <span class="badge verified">today</span>' : ''}</span><span class="night">${d.night ? 'sleeping at ' + esc(d.night.title) : ''}</span></div>${d.items.map(id => itemRow(byId[id])).join('') || '<div class="it" style="cursor:default"><div class="tm"></div><div class="su">nothing planned</div></div>'}</div>`).join('') || '<div class="card"><div class="small">No days left in the plan from today.</div></div>'}
    ${legs.length ? `<div class="card"><h3>When to leave</h3><table class="t">${legs.map(i => `<tr><td>${esc(i.title)}</td><td>${esc(i.leave.words)}</td><td class="links">${i.links.filter(l => ['directions', 'status'].includes(l.key)).map(l => `<a href="${esc(l.url)}" target="_blank">${esc(l.label)} ↗</a>`).join('')}</td></tr>`).join('')}</table><div class="small">Buffers: ${p.rules.airport_buffer_minutes.domestic} min before a domestic flight, ${p.rules.airport_buffer_minutes.international} international; add each leg's travel time (minutes to the start point) for a leave-by. Live traffic is the Directions link; the engine does not watch it by itself yet (that is W28's next step and needs a maps key).</div></div>` : ''}
    <div class="card"><h3>Waiting on people</h3>${p.confirmations.filter(c => ['draft', 'sent', 'call'].includes(c.status)).map(c => `<div class="small" style="padding:4px 0;border-top:1px solid var(--line)"><b>${esc(c.status)}</b> · ${esc((byId[c.item_id] || {}).title || '')} · ${esc(c.question)}</div>`).join('') || '<div class="small">Nothing pending.</div>'}</div>
    <div class="card"><h3>Log what you paid</h3><div class="row"><button class="sbtn gold mini" id="run-exp">+ Expense</button><span class="small">Spent so far: ${money0(p.costs.actual_home_cents)} of ${money0(p.costs.planned_home_cents)} planned.</span></div></div>`;
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
    <div class="help">Message first (WhatsApp, LINE, text, email, or the booking app), then a call only if there is no reply within the set hours (Settings → Logic → Trips · confirming a booking); the call says up front that it's automated. The engine drafts the words and keeps the thread; you send it.</div>
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
  $('#p-helper').innerHTML = `<h2 class="sec">The helper <span class="small">${esc(h.meta.title || '')} · ${h.questions.length} questions · ${h.workflows.length} workflows · ${h.guardrails.length} guardrails</span></h2>${chips}${body}
    <div class="help">This is the capability list as data (the pack <span class="mono">packs/helper.sqlite</span>, built from the brief). A Claude chat reaches the same list through the plug (helper_catalogue, helper_workflow, helper_region) and this trip's plan and checks (trip_plan, trip_checks), so asking "compare every way from Krabi to Phuket" runs W02 against the real plan. After a trip, W26: log how each workflow did, and turn mistakes into guardrails in the next version of the brief.</div>`;
  $('#p-helper').querySelectorAll('[data-hsec]').forEach(b => b.onclick = () => { S.hsec = b.dataset.hsec; renderHelper(); });
  $('#p-helper').querySelectorAll('[data-log]').forEach(b => b.onclick = () => form(`${b.dataset.log}: how did it go?`, [{ k: 'outcome', l: 'Outcome', t: 'select', o: [['proven', 'Proven: booked or decided with it'], ['adopted', 'Adopted: went with it, nothing booked yet'], ['open', 'Open: hit a wall'], ['rejected', 'Rejected: turned it down']], v: 'proven' }, { k: 'note', l: 'Note', v: '', wide: true }],
    async out => { await act('trips.log_workflow', { trip_id: S.id, code: b.dataset.log, ...out }); toast('Logged.'); await loadPlan(); renderHelper(); }));
}

// ---------- region -----------------------------------------------------------------------------
async function renderRegion() {
  const rid = S.plan && S.plan.trip.region_pack;
  if (!rid) { $('#p-region').innerHTML = `<div class="card"><h3>No region pack on this trip</h3><div class="small">Packs so far: ${S.opt.regions.map(r => esc(r.name)).join(', ') || 'none'}. Set one in Trip settings; a new country starts from the template in the Helper → Methods.</div></div>`; return; }
  const r = await api('GET', `/v1/trips/helper/regions/${rid}`);
  $('#p-region').innerHTML = `<h2 class="sec">${esc(r.name)} pack <span class="small">${esc(r.currency || '')} · ${esc(r.time_zone || '')} · businesses answer on ${esc(r.channels.join(', '))}</span></h2>
    ${r.intro ? `<div class="help">${esc(r.intro)}</div>` : ''}
    <div class="card"><h3>Sites</h3><table class="t">${r.sites.map(s => `<tr><td><a href="${esc(s.url.includes('{') ? s.url.split('/{')[0] : s.url)}" target="_blank">${esc(s.name)} ↗</a></td><td class="small">${esc(s.means)}</td></tr>`).join('')}</table></div>
    ${Object.entries(r.sections).map(([k, lines]) => `<div class="card"><h3>${esc(k)}</h3>${lines.map(l => `<div class="q">${esc(l)}</div>`).join('')}</div>`).join('')}
    <div class="card"><h3>Worked examples <span class="small">question code → what it looked like here</span></h3>${r.worked_examples.map(e => `<div class="q"><code>${esc(e.code)}</code>${esc(e.text)}</div>`).join('')}</div>
    <div class="help">Reference data from the brief; your own notes about this trip go on the trip's record (Timeline → Record). After the trip, W26 finishes the pack for the next version.</div>`;
}

(async () => {
  try {
    S.opt = await api('GET', '/v1/trips/options');
    await loadTrips(); await loadPlan();
    const t = location.hash.slice(1);
    showTab(['timeline', 'checks', 'costs', 'prepare', 'run', 'confirm', 'helper', 'region'].includes(t) ? t : 'timeline');
  } catch (e) { App.down('#p-timeline'); }
})();
