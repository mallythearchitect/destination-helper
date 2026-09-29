/* AI inbox: suggestions wait here for your OK. Approving runs an ordinary
   action (it lands in history, it can be undone). */
'use strict';
const { $, esc, toast, api, money, money0, fmtD, fmtWhen } = App;
const act = App.act('ai');
const S = { status: null, inbox: [], tab: 'inbox', opts: null };

const showTab = App.tabs({ render: { inbox: renderInbox, workflows: renderWorkflows, log: renderLog, tests: renderTests }, onShow: t => { S.tab = t; } });
async function reload() {
  [S.status, S.inbox] = await Promise.all([api('GET', '/v1/ai/status'), api('GET', '/v1/ai/inbox')]);
  const s = S.status;
  $('#pill').innerHTML = `<b>${s.pending}</b> waiting · <b>${money(s.month_spend_cents)}</b> of ${money(s.monthly_cap_cents)} this month`;
  $('#models').innerHTML = Object.entries(s.jobs).map(([j, c]) => `<button class="sub" data-go="settings" title="change in Settings → AI">${esc(j)}<span class="n">${esc(c.model.replace('claude-', ''))}</span></button>`).join('') +
    `<button class="${s.claude_key_set ? '' : ''}" data-go="settings">${s.claude_key_set ? '<span class="ok">●</span> Claude key set' : '<span class="bad">○</span> no Claude key yet'}</button>`;
}
$('#models').addEventListener('click', e => { if (e.target.closest('[data-go]')) location.href = '/apps/system/web/settings.html#ai'; });

function renderInbox() {
  const s = S.status, list = S.inbox;
  const thr = s.sure_threshold || 0.85;
  const conf = c => c == null ? '' : `<span class="conf ${c >= thr ? 'hi' : c < 0.6 ? 'lo' : ''}">${Math.round(c * 100)}% sure</span>`;
  $('#p-inbox').innerHTML = `
   <h2 class="sec">Waiting for your OK <span class="small">${list.length}</span></h2>
   <div class="kpis">
    <div class="kpi ${s.cap_reached ? 'warn' : ''}"><div class="lab">AI spend this month</div><div class="val">${money(s.month_spend_cents)}</div><div class="sub">cap ${money(s.monthly_cap_cents)} · <a href="/apps/system/web/settings.html#ai">change</a></div></div>
    <div class="kpi ${s.claude_key_set ? '' : 'warn'}"><div class="lab">Claude</div><div class="val" style="font-size:18px">${s.claude_key_set ? 'ready' : 'no key'}</div><div class="sub">${s.claude_key_set ? 'drafting uses ' + esc(s.jobs.draft.model) : '<a href="/apps/system/web/settings.html#ai">paste the key in Settings → AI</a>'}</div></div>
   </div>
   <div class="row" style="margin-bottom:10px">${list.length ? `<button class="sbtn" id="approve-hi">Approve all ${Math.round((s.sure_threshold || 0.85) * 100)}%+ sure</button><button class="sbtn" id="approve-all">Approve all</button>` : ''}
    <span class="small">AI workflows file suggestions here and stop. Nothing changes until you approve.</span></div>
   <div class="card" id="suglist">${list.length ? list.map(x => `<div class="sug" data-id="${x.id}">
     <div><div class="sum">${esc(x.summary)}${conf(x.confidence)}</div><div class="why">${esc(x.why || '')}</div>
      <div class="meta">${esc(x.workflow)} · ${fmtWhen(x.ts)}</div></div>
     <div class="row"><button class="sbtn mini gold" data-approve="${x.id}">Approve</button><button class="sbtn mini" data-reject="${x.id}">No</button></div></div>`).join('')
    : '<div class="small">Nothing waiting. The first Trips workflow (drafting confirmations with the model) will file its suggestions here.</div>'}</div>`;
  const bulk = async (min) => { try { const r = await api('POST', `/v1/ai/inbox/approve-all?min_confidence=${min}`); toast(`Approved ${r.approved}${r.failed.length ? `, ${r.failed.length} failed` : ''}`); await reload(); renderInbox(); } catch (e) { toast(e.message, 5000); } };
  const hi = $('#approve-hi'); if (hi) hi.onclick = () => bulk(s.sure_threshold || 0.85);
  const all = $('#approve-all'); if (all) all.onclick = () => bulk(0);
}
$('#p-inbox').addEventListener('click', async e => {
  const a = e.target.closest('[data-approve]'), r = e.target.closest('[data-reject]');
  if (!a && !r) return;
  const id = (a || r).dataset.approve || (a || r).dataset.reject;
  try {
    if (a) { const body = undefined; await api('POST', `/v1/ai/inbox/${id}/approve`, body); toast(body ? 'Approved with your correction (it learns from that)' : 'Approved'); }
    else { await api('POST', `/v1/ai/inbox/${id}/reject`); toast('Rejected'); }
    await reload(); renderInbox();
  } catch (x) { toast(x.message, 5000); }
});

function renderWorkflows() {
  const w = S.status.workflows, on = [];
  $('#p-workflows').innerHTML = `<h2 class="sec">Workflows</h2>
   <div class="help">Fixed steps, with the AI doing only the fuzzy part. Each one suggests; you decide. More arrive as the apps grow; the list of which are on lives in Settings → AI.</div>
   ${w.map(x => `<div class="card"><h3>${esc(x.name)}</h3><div>${esc(x.description)}</div><div class="small" style="margin-top:6px">Inputs: ${esc(Object.keys(x.input.properties || {}).join(', ') || 'none')}</div></div>`).join('')}
   <div class="card"><h3>The plug (MCP)</h3><div>A Claude chat can press these same buttons: ask "check my trip" or "compare every way from Krabi to Phuket" (W02). Register it once with <span class="mono">scripts/install_mcp.sh</span>. Anything that removes or pays says so, and the chat asks you first.</div></div>`;
}
async function renderLog() {
  const calls = await api('GET', '/v1/ai/calls?limit=100');
  $('#p-log').innerHTML = `<h2 class="sec">Every AI call</h2><div class="help">Which model, for which job, what it cost, whether it worked. The first 400 characters of what it saw and said.</div>
   <div class="scroll"><table class="t"><thead><tr><th>When</th><th>Job</th><th>Model</th><th>Prompt</th><th class="num">Tokens in / out</th><th class="num">Cost</th><th class="num">ms</th><th>Result</th></tr></thead><tbody>
   ${calls.map(c => `<tr><td class="small" style="white-space:nowrap">${fmtWhen(c.ts)}</td><td>${esc(c.workflow)}</td><td>${esc(c.model)}</td><td class="small">${esc(c.prompt_version)}</td><td class="num small">${c.input_tokens ?? '—'} / ${c.output_tokens ?? '—'}</td><td class="num">${money(c.cost_cents)}</td><td class="num small">${c.ms}</td><td>${c.ok ? '<span class="ok">ok</span>' : `<span class="bad">failed</span> <span class="small">${esc(c.error || '')}</span>`}<details><summary class="small">what it saw / said</summary><pre class="small" style="white-space:pre-wrap">${esc(c.input_preview)}\n---\n${esc(c.output_preview)}</pre></details></td></tr>`).join('') || '<tr><td colspan="8" class="small">No calls yet.</td></tr>'}
   </tbody></table></div>`;
}
async function renderTests() {
  const t = await api('GET', '/v1/ai/tests?test_set=trips');
  const models = Object.values(S.status.jobs).flatMap(c => [c.model, c.fallback]).filter(m => m && m !== 'none');
  $('#p-tests').innerHTML = `<h2 class="sec">Test scores</h2>
   <div class="help">Every suggestion you approve or correct becomes a labelled example (${t.examples} so far). Score a model against them before switching the job to it in Settings → AI. Same score or better: switch.</div>
   <div class="row" style="margin-bottom:12px"><select id="test-model">${[...new Set([...models, 'claude-opus-5', 'claude-sonnet-5', 'claude-haiku-4-5'])].map(m => `<option>${esc(m)}</option>`).join('')}</select><button class="sbtn gold" id="run-test" ${t.examples ? '' : 'disabled'}>Score this model</button></div>
   <table class="t"><thead><tr><th>When</th><th>Model</th><th>Prompt</th><th class="num">Examples</th><th class="num">Right</th><th class="num">Score</th><th class="num">Cost</th></tr></thead><tbody>
   ${t.runs.map(r => `<tr><td class="small">${fmtWhen(r.ts)}</td><td>${esc(r.model)}</td><td class="small">${esc(r.prompt_version)}</td><td class="num">${r.examples}</td><td class="num">${r.correct}</td><td class="num"><b>${Math.round(r.score * 100)}%</b></td><td class="num">${money(r.cost_cents)}</td></tr>`).join('') || '<tr><td colspan="7" class="small">No runs yet.</td></tr>'}
   </tbody></table>`;
  $('#run-test').onclick = async () => { $('#run-test').disabled = true; toast('Scoring…', 8000); try { const r = await api('POST', '/v1/actions/ai.score_model', { model: $('#test-model').value }); toast(r.examples ? `${r.model}: ${r.correct} of ${r.examples} right (${Math.round(r.score * 100)}%)` : r.note, 6000); renderTests(); } catch (e) { toast(e.message, 7000); $('#run-test').disabled = false; } };
}
(async () => {
  try { await reload(); showTab(['inbox', 'workflows', 'log', 'tests'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'inbox'); }
  catch (e) { $('#p-inbox').innerHTML = `<p>The engine isn't running. Start it with <span class="mono">scripts/dev.sh</span> and reload.</p>`; }
})();
