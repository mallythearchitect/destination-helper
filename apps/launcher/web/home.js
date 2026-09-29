/* Home: your trips at a glance, what the engine tracked and did, the apps. */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const S = { trips: [], wf: null, metrics: [] };
const APPS = [
  ['Trips', 'The co-pilot: plan, check the plan, prepare, run it live; the helper\'s capability list and region packs', '/apps/trips/web/', 'live'],
  ['Destinations', 'Cities and places scored with sources, your shortlist, trip cost, ways to get there', '/apps/destinations/web/', 'live'],
  ['AI inbox', 'Suggestions waiting for your OK, models per job, spend against the cap, test scores', '/apps/ai/web/', 'live'],
  ['Browse', 'Every record: find, link, tag, note, attach, undo', '/apps/system/web/browse.html', 'live'],
  ['Settings', 'Profile, keys, display, AI, backups, and every rule as data (Logic)', '/apps/system/web/settings.html', 'live'],
];
function spark(points, key = 'value', color = '#D9A93C') {
  if (!points || points.length < 2) return '<div class="small">not enough history yet</div>';
  const vs = points.map(p => p[key]), min = Math.min(...vs), max = Math.max(...vs), w = 300, h = 44, span = max - min || 1;
  const d = vs.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i / (vs.length - 1) * w).toFixed(1)},${(h - 4 - (v - min) / span * (h - 8)).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.6"/></svg>`;
}
const showTab = App.tabs({ render: { today: renderToday, tracking: renderTracking, workflows: renderWorkflows, apps: renderApps } });

async function load() {
  [S.trips, S.wf, S.metrics] = await Promise.all([api('GET', '/v1/trips'), api('GET', '/v1/workflows'), api('GET', '/v1/track/metrics')]);
  const p = $('#health'); p.className = 'pill ok'; p.innerHTML = `engine <b>ok</b> · ${S.trips.length} trip${S.trips.length === 1 ? '' : 's'}`;
}
function renderToday() {
  const live = S.trips.filter(t => t.stage !== 'done'), blockers = live.reduce((a, t) => a + (t.findings.blocker || 0), 0), warns = live.reduce((a, t) => a + (t.findings.warn || 0), 0);
  const toBook = live.reduce((a, t) => a + t.to_book, 0), tasks = live.reduce((a, t) => a + t.tasks_open, 0);
  const next = live.filter(t => t.start_date).sort((a, b) => a.start_date < b.start_date ? -1 : 1)[0];
  const runsToday = S.wf.runs.filter(r => r.started_at.slice(0, 10) === new Date().toISOString().slice(0, 10));
  const days = next ? Math.ceil((new Date(next.start_date + 'T00:00:00') - Date.now()) / 864e5) : null;
  $('#p-today').innerHTML = `<h2 class="sec">Today <span class="small">${new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}</span></h2>
   <div class="kpis">
    <a class="kpi" href="/apps/trips/web/" style="text-decoration:none;color:inherit"><div class="lab">Next trip</div><div class="val" style="font-size:18px">${next ? esc(next.name.slice(0, 26)) : 'none planned'}</div><div class="sub">${next ? (days > 0 ? `in ${days} days · ${next.headcount} going` : days === 0 ? 'today' : 'under way') : '<a href="/apps/trips/web/">start one</a>'}</div></a>
    <a class="kpi ${blockers ? 'warn' : ''}" href="/apps/trips/web/#checks" style="text-decoration:none;color:inherit"><div class="lab">The checker</div><div class="val">${blockers}</div><div class="sub">blocker${blockers === 1 ? '' : 's'} · ${warns} warning${warns === 1 ? '' : 's'}</div></a>
    <a class="kpi" href="/apps/trips/web/#prepare" style="text-decoration:none;color:inherit"><div class="lab">Still to book</div><div class="val">${toBook}</div><div class="sub">${tasks} task${tasks === 1 ? '' : 's'} open</div></a>
   </div>
   <div class="two">
    <div class="card" id="trips-now"><h3>Your trips</h3>${S.trips.length ? S.trips.map(t => `<a class="trip" href="/apps/trips/web/"><div><b>${esc(t.name)}</b><div class="sub">${esc(t.stage)} · ${t.start_date ? esc(fmtD(t.start_date)) + (t.end_date ? ' → ' + esc(fmtD(t.end_date)) : '') : 'no dates'} · ${t.headcount} going · ${t.items} items</div></div><div class="sub">${t.findings.blocker ? '⛔ ' + t.findings.blocker + ' ' : ''}${t.to_book ? t.to_book + ' to book' : 'all booked'}</div></a>`).join('') : '<div class="small">No trips yet. <a href="/apps/trips/web/">Start one</a>: it asks who\'s going, the dates, the budget caps and what the trip is for.</div>'}</div>
    <div class="card"><h3>What the engine did today</h3>${runsToday.length ? runsToday.map(r => `<div class="run"><span>${esc(r.name)} <span class="small">${esc(r.trigger)} · ${fmtWhen(r.started_at)}</span></span><span class="${r.ok ? 'ok' : 'bad'}">${r.ok ? 'ok' : 'failed'}</span></div>`).join('') : '<div class="small">Nothing yet today. It re-checks every trip at 6 AM and writes the day\'s numbers after midnight (Workflows tab).</div>'}</div>
   </div>
   <h2 class="sec" style="margin-top:8px">Apps</h2>${appsGrid()}`;
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
  return `<div class="grid">${APPS.map(([n, b, h, s]) => `<a class="app" href="${h}"><h2>${esc(n)}</h2><p>${esc(b)}</p><span class="st">${esc(s)}</span></a>`).join('')}</div>`;
}
function renderApps() {
  $('#p-apps').innerHTML = `<h2 class="sec">Apps</h2><p class="lead">Each app is a view on one engine: one vault, one history, one set of rules.</p>${appsGrid()}`;
}
(async () => {
  try { await load(); showTab(['today', 'tracking', 'workflows', 'apps'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'today'); }
  catch (e) { const p = $('#health'); p.className = 'pill bad'; p.innerHTML = 'engine <b>down</b>'; App.down('#p-today'); }
})();
