/* The helper chat: a floating "h" that opens a panel. Ask about your trips; it answers
   from the plan, the checks and the local tips, and suggests. Nothing is added to a trip
   until you say so (it has no buttons that change data). Loaded by Home and Trips. */
(function () {
  'use strict';
  const { $, esc, api } = App;
  const st = { open: false, log: [], busy: false, tripId: null };
  const css = `
  #helper-fab{position:fixed;right:22px;bottom:22px;width:56px;height:56px;border-radius:50%;border:0;background:var(--color-accent);color:var(--color-bg);font-family:var(--font-heading);font-size:26px;cursor:pointer;box-shadow:var(--shadow-lg);z-index:800;line-height:1}
  #helper-fab:hover{background:var(--color-accent-600)}
  #helper{position:fixed;right:22px;bottom:90px;width:min(360px,calc(100vw - 32px));max-height:min(70vh,620px);display:none;flex-direction:column;background:var(--color-neutral-100);border-radius:var(--radius);box-shadow:var(--shadow-lg);z-index:800;overflow:hidden}
  #helper.open{display:flex}
  #helper .hd{display:flex;align-items:center;gap:10px;padding:14px 16px;background:var(--color-surface)}
  #helper .hd .h{width:32px;height:32px;border-radius:50%;background:var(--color-accent);color:var(--color-bg);display:grid;place-items:center;font-family:var(--font-heading);font-size:17px;flex:none}
  #helper .hd b{display:block;font-size:14px}#helper .hd small{color:var(--mut);font-size:12px}
  #helper .hd button{margin-left:auto;font:inherit;font-size:12.5px;background:transparent;border:0;color:var(--mut);cursor:pointer}
  #helper .log{flex:1;overflow:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px;font-size:13.5px}
  #helper .me{align-self:flex-end;background:var(--color-accent-2-800);color:var(--color-bg);padding:10px 14px;border-radius:16px 16px 4px 16px;max-width:88%}
  #helper .it{align-self:flex-start;background:var(--color-surface);padding:10px 14px;border-radius:16px 16px 16px 4px;max-width:92%;white-space:pre-wrap}
  #helper .it.err{background:var(--color-accent-100);color:var(--color-accent-800)}
  #helper .note{font-size:11.5px;color:var(--mut);padding:0 16px 8px}
  #helper form{display:flex;gap:8px;padding:0 16px 16px}
  #helper input{flex:1;background:var(--color-surface)}
  @media (max-width:760px){#helper{right:8px;left:8px;bottom:80px;width:auto}#helper-fab{right:14px;bottom:14px}}`;
  function mount() {
    const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
    const fab = document.createElement('button'); fab.id = 'helper-fab'; fab.title = 'Ask me anything about your trips'; fab.textContent = 'h';
    const box = document.createElement('div'); box.id = 'helper';
    box.innerHTML = `<div class="hd"><span class="h">h</span><div><b>Ask me anything about your trips</b><small>I suggest, you decide</small></div><button id="helper-close">Close</button></div>
      <div class="log" id="helper-log"><div class="it">Ask about a trip in your own words: "compare every way from Krabi to Phuket", "what's still to book?", "is the taxi booked before I land?". I answer from your plan, the checks and the local tips.</div></div>
      <div class="note">Nothing is added to your trip until you say so.</div>
      <form id="helper-form"><input type="text" id="helper-q" placeholder="Ask about your trip…" autocomplete="off"><button class="sbtn gold mini" type="submit">Ask</button></form>`;
    document.body.append(fab, box);
    fab.onclick = () => { st.open = !st.open; box.classList.toggle('open', st.open); if (st.open) $('#helper-q').focus(); };
    $('#helper-close').onclick = () => { st.open = false; box.classList.remove('open'); };
    $('#helper-form').onsubmit = async e => {
      e.preventDefault(); const q = $('#helper-q').value.trim(); if (!q || st.busy) return;
      $('#helper-q').value = ''; add('me', q); st.busy = true; const wait = add('it', '…');
      try {
        const r = await api('POST', '/v1/actions/trips.ask', { question: q, trip_id: st.tripId || undefined, app: 'helper' });
        wait.textContent = r.answer;
      } catch (x) {
        wait.className = 'it err';
        wait.textContent = /cap|model|key|allowed/i.test(x.message) ? x.message + ' (Developer mode → Settings → AI.)' : x.message;
      }
      st.busy = false; $('#helper-log').scrollTop = 1e6;
    };
  }
  function add(cls, text) { const d = document.createElement('div'); d.className = cls; d.textContent = text; $('#helper-log').appendChild(d); $('#helper-log').scrollTop = 1e6; return d; }
  window.Helper = { setTrip: id => { st.tripId = id; }, open: () => { st.open = true; $('#helper').classList.add('open'); $('#helper-q').focus(); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
