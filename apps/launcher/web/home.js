/* Home: your trips at a glance, what the engine tracked and did, the apps. */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const S = { trips: [], wf: null, metrics: [] };
const APPS = () => App.isDev() ? [
  ['Trips', 'The co-pilot: plan, check the plan, prepare, run it live; the helper\'s capability list and region packs', '/apps/trips/web/', 'live'],
  ['Destinations', 'Cities and places scored with sources, your shortlist, trip cost, ways to get there', '/apps/destinations/web/', 'live'],
  ['AI inbox', 'Suggestions waiting for your OK, models per job, spend against the cap, test scores', '/apps/ai/web/', 'live'],
  ['Browse', 'Every record: find, link, tag, note, attach, undo', '/apps/system/web/browse.html', 'live'],
  ['Settings', 'Profile, keys, display, AI, backups, and every rule as data (Logic)', '/apps/system/web/settings.html', 'live'],
] : [
  ['Trips', 'Plan a trip, catch the mistakes before they cost money, get ready, then run it day by day', '/apps/trips/web/', 'open'],
  ['Destinations', 'Places to go, scored and priced, with the ways to get there and your shortlist', '/apps/destinations/web/', 'open'],
  ['History', 'Every trip, place and note you have kept, searchable', '/apps/system/web/browse.html', 'open'],
  ['Settings', 'Home city, time zone, appearance, keys', '/apps/system/web/settings.html', 'open'],
];
function spark(points, key = 'value', color = '#17788A') {
  if (!points || points.length < 2) return '<div class="small">not enough history yet</div>';
  const vs = points.map(p => p[key]), min = Math.min(...vs), max = Math.max(...vs), w = 300, h = 44, span = max - min || 1;
  const d = vs.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (vs.length - 1) * w).toFixed(1)},${(h - 4 - (v - min) / span * (h - 8)).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.6"/></svg>`;
}
const showTab = App.tabs({ render: { today: renderToday, tracking: renderTracking, workflows: renderWorkflows, apps: renderApps } });

async function load() {
  [S.trips, S.wf, S.metrics] = await Promise.all([api('GET', '/v1/trips'), api('GET', '/v1/workflows'), api('GET', '/v1/track/metrics')]);
  const p = $('#health'); p.className = 'pill ok dev-only'; p.innerHTML = `engine <b>ok</b> · ${S.trips.length} trip${S.trips.length === 1 ? '' : 's'}`;
}
async function comingUp(live) {
  const plans = await Promise.all(live.slice(0, 6).map(t => api('GET', `/v1/trips/${t.id}`).catch(() => null)));
  const today = new Date().toISOString().slice(0, 10), horizon = new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 10), out = [];
  for (const p of plans.filter(Boolean)) {
    for (const t of p.tasks) if (!t.done_at && t.due && t.due <= horizon) out.push({ when: t.due, sort: t.due, what: t.title, trip: p.trip.name, kind: t.due < today ? 'overdue' : 'deadline' });
    for (const i of p.items) if (i.start_at && i.status !== 'cancelled' && i.start_at.slice(0, 10) >= today && i.start_at.slice(0, 10) <= horizon) out.push({ when: i.start_at, sort: i.start_at, what: i.title, trip: p.trip.name, kind: i.kind });
    for (const f of p.findings) if (f.severity === 'blocker') out.push({ when: today, sort: '0', what: f.message, trip: p.trip.name, kind: 'blocker' });
  }
  return out.sort((a, b) => a.sort < b.sort ? -1 : 1).slice(0, 10);
}
function renderToday() {
  const live = S.trips.filter(t => t.stage !== 'done'), blockers = live.reduce((a, t) => a + (t.findings.blocker || 0), 0), warns = live.reduce((a, t) => a + (t.findings.warn || 0), 0);
  const toBook = live.reduce((a, t) => a + t.to_book, 0), tasks = live.reduce((a, t) => a + t.tasks_open, 0);
  const next = live.filter(t => t.start_date).sort((a, b) => a.start_date < b.start_date ? -1 : 1)[0];
  const runsToday = S.wf.runs.filter(r => r.started_at.slice(0, 10) === new Date().toISOString().slice(0, 10));
  const days = next ? Math.ceil((new Date(next.start_date + 'T00:00:00') - Date.now()) / 864e5) : null;
  const hc = h => h >= 80 ? 'var(--ok)' : h >= 50 ? 'var(--sun)' : 'var(--bad)';
  $('#p-today').innerHTML = `${next ? `<a class="next-trip" href="/apps/trips/web/"><div><div class="lab">Next trip</div><h2>${esc(next.name)}</h2><div class="meta">${esc(fmtD(next.start_date))}${next.end_date ? ' → ' + esc(fmtD(next.end_date)) : ''} · ${next.headcount} going · ${next.items} items · ${next.to_book ? next.to_book + ' to book' : 'all booked'}${next.findings.blocker ? ` · <b style="color:#F08A5D">${next.findings.blocker} blocker${next.findings.blocker === 1 ? '' : 's'}</b>` : ''}</div></div><div class="big">${days > 0 ? days : days === 0 ? 'today' : 'now'}<small>${days > 0 ? 'days to go' : 'under way'}</small></div></a>` : `<div class="card"><h3>No trip yet</h3><div>Start one in Trips: five questions, then the checker watches the plan as you add to it.</div><div class="row" style="margin-top:10px"><a class="sbtn gold" href="/apps/trips/web/">Open Trips</a></div></div>`}
   <div class="kpis">
    <a class="kpi ${blockers ? 'warn' : ''}" href="/apps/trips/web/#checks"><div class="lab">Things to fix</div><div class="val">${blockers}</div><div class="sub">${blockers === 1 ? 'would cost money' : 'would cost money'} · ${warns} worth a look</div></a>
    <a class="kpi" href="/apps/trips/web/#prepare"><div class="lab">Still to book</div><div class="val">${toBook}</div><div class="sub">${tasks} task${tasks === 1 ? '' : 's'} open</div></a>
    <a class="kpi" href="/apps/trips/web/"><div class="lab">Trips</div><div class="val">${live.length}</div><div class="sub">${S.trips.length - live.length} done</div></a>
   </div>
   <div class="two">
    <div class="card" id="trips-now"><h3>Your trips</h3>${S.trips.length ? S.trips.map(t => `<a class="trip" href="/apps/trips/web/"><div><b><i class="hp" style="background:${hc(t.health)}" title="health ${t.health}"></i>${esc(t.name)}</b><div class="sub">${esc(t.stage)} · ${t.start_date ? esc(fmtD(t.start_date)) + (t.end_date ? ' → ' + esc(fmtD(t.end_date)) : '') : 'no dates'} · ${t.headcount} going · ${t.items} items</div></div><div class="sub">health ${t.health}${t.to_book ? ' · ' + t.to_book + ' to book' : ''}</div></a>`).join('') : '<div class="small">No trips yet. <a href="/apps/trips/web/">Start one</a>.</div>'}</div>
    <div class="card" id="coming-up"><h3>Coming up <span class="small">next two weeks</span></h3><div class="small">Looking…</div></div>
    <div class="card dev-only"><h3>What the engine did today</h3>${runsToday.length ? runsToday.map(r => `<div class="run"><span>${esc(r.name)} <span class="small">${esc(r.trigger)} · ${fmtWhen(r.started_at)}</span></span><span class="${r.ok ? 'ok' : 'bad'}">${r.ok ? 'ok' : 'failed'}</span></div>`).join('') : '<div class="small">Nothing yet today. It re-checks every trip at 6 AM and writes the day\'s numbers after midnight (Workflows tab).</div>'}</div>
   </div>
   <h2 class="sec" style="margin-top:8px">Apps</h2>${appsGrid()}`;
  comingUp(live).then(list => { const el = $('#coming-up'); if (!el) return; el.innerHTML = `<h3>Coming up <span class="small">next two weeks</span></h3>${list.length ? list.map(x => `<div class="run"><span>${x.kind === 'blocker' ? '⛔ ' : x.kind === 'overdue' ? '⏰ ' : x.kind === 'deadline' ? '📌 ' : ''}${esc(x.what)} <span class="small">${esc(x.trip)}</span></span><span class="small">${x.kind === 'blocker' ? 'fix now' : x.kind === 'overdue' ? 'overdue' : esc(x.when.length > 10 ? new Date(x.when).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : fmtD(x.when))}</span></div>`).join('') : '<div class="small">Nothing due in the next two weeks.</div>'}`; });
}
async function renderTracking() {
  const ms = S.metrics.filter(m => m.observations);
  $('#p-tracking').innerHTML = `<h2 class="sec">Tracking <span class="small">${ms.length} metrics with data · ${S.metrics.length} defined</span></h2>
   <div class="help">Every number the engine watches, per trip, as a line over time: planned cost, booked, still to book, open blockers, tasks open, spent. Written nightly; anything else can be tracked with the <span class="mono">track.observe</span> action.</div>
   <div class="two" id="tk"></div>`;
  const byTrip = Object.fromEntries(S.trips.map(t => [t.id, t.name]));
  const cards = await Promise.all(ms.map(async m => {
    const s = await api('GET', `/v1/track/series?metric=${m.id}`).catch(() => null);
    const subs = s ? s.subjects : [];
    const parts = await Promise.all(subs.map(async sub => { const a = await api('GET', `/v1/analytics/summary?metric=${m.id}&subject=${encodeURIComponent(sub)}`).catch(() => null); return a && a.points.length ? { sub, a } : null; }));
    const fmt = v => m.unit === 'cents' ? money0(v) : v.toLocaleString();
    return `<div class="card"><h3>${esc(m.label)} <span class="small">${esc(m.id)}</span></h3>${parts.filter(Boolean).map(({ sub, a }) => `<div class="small"><b>${esc(byTrip[sub] || sub)}</b> · latest ${fmt(a.latest.value)} · ${a.trend.direction}</div>${spark(a.points)}`).join('') || '<div class="small">no points yet</div>'}<div class="small">${esc(m.meaning)}</div></div>`;
  }));
  $('#tk').innerHTML = cards.join('') || '<div class="small">Nothing tracked yet. Run track.snapshot from the Workflows tab.</div>';
}
function renderWorkflows() {
  const w = S.wf;
  $('#p-workflows').innerHTML = `<h2 class="sec">Workflows <span class="small">what the engine does on its own</span></h2>
   <div class="help">Each runs on its schedule (Settings → Logic → Workflows), records its run, and puts its result where it belongs. A run missed while the Mac slept happens as soon as the engine is up. Run any of them now.</div>
   <table class="t"><thead><tr><th>Workflow</th><th>When</th><th>Last run</th><th>Next</th><th></th></tr></thead><tbody>${w.workflows.map(x => `<tr><td><b>${esc(x.name)}</b><div class="small">${esc(x.description)}</div></td><td class="small">${x.schedule.enabled ? `every ${esc(x.schedule.every)} at ${esc(x.schedule.at)}` : 'off'}${x.ready ? '' : ` <span class="tag">needs ${esc(x.needs)}</span>`}</td><td class="small">${x.last_run ? `${fmtWhen(x.last_run.started_at)} <span class="${x.last_run.ok ? 'ok' : 'bad'}">${x.last_run.ok ? 'ok' : 'failed'}</span>` : 'never'}</td><td class="small">${x.next_run ? fmtWhen(x.next_run) : '—'}</td><td><button class="sbtn mini" data-run="${x.name}" ${x.ready ? '' : 'disabled'}>Run now</button></td></tr>`).join('')}</tbody></table>
   <div class="card" style="margin-top:14px"><h3>Recent runs</h3>${w.runs.length ? w.runs.slice(0, 15).map(r => `<div class="run"><span>${esc(r.name)} <span class="small">${esc(r.trigger)} · ${fmtWhen(r.started_at)}${r.error ? ` · ${esc(r.error.slice(0, 80))}` : ''}</span></span><span class="${r.ok ? 'ok' : 'bad'}">${r.ok ? 'ok' : r.ok === 0 ? 'failed' : 'running'}</span></div>`).join('') : '<div class="small">No runs yet.</div>'}</div>`;
  $('#p-workflows').querySelectorAll('[data-run]').forEach(b => b.onclick = async () => { b.disabled = true; toast('Running ' + b.dataset.run + '…', 6000); try { const r = await api('POST', `/v1/workflows/${b.dataset.run}/run`); toast(r.ok ? `${r.name}: done` : `${r.name} failed: ${r.error}`, 5000); await load(); renderWorkflows(); } catch (e) { toast(e.message, 5000); b.disabled = false; } });
}
function appsGrid() {
  return `<div class="grid">${APPS().map(([n, b, h, s]) => `<a class="app" href="${h}"><h2>${esc(n)}</h2><p>${esc(b)}</p><span class="st">${esc(s)}</span></a>`).join('')}</div>`;
}
function renderApps() {
  $('#p-apps').innerHTML = `<h2 class="sec">Apps</h2><p class="lead">Each app is a view on one engine: one vault, one history, one set of rules.</p>${appsGrid()}`;
}
App.onMode(() => { const t = location.hash.slice(1); showTab(App.isDev() || !['tracking', 'workflows'].includes(t) ? t : 'today'); });
(async () => {
  try { await load(); const t = location.hash.slice(1); showTab(['today', 'tracking', 'workflows', 'apps'].includes(t) && (App.isDev() || !['tracking', 'workflows'].includes(t)) ? t : 'today'); }
  catch (e) { const p = $('#health'); p.className = 'pill bad'; p.innerHTML = 'engine <b>down</b>'; App.down('#p-today'); }
})();
