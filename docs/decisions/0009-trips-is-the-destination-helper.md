# 0009 · Trips is the Destination Helper, built on the engine, with the capability list as a pack

**Date:** 2026-09-28

**What we chose.** The trip co-pilot from the Destination Helper brief (v3) is
an app on the engine, `apps/trips`, beside Destinations, not a page in the old
workspace and not a separate product. Its brain, the capability list (93
question codes, 29 workflows with steps, 12 guardrails, the methods, the
region packs), is reference data: `packs/helper.sqlite`, built from a JSON
extracted from the brief by `scripts/extract_helper_doc.py`. Per-trip data
(the plan, prices, confirmations, the track record) lives in the vault.

**Why.**
- The brief's three stages (plan, prepare, run) all need the same engine
  parts: saving, undo, history, records, settings, sources, the AI plug. Building
  them again elsewhere would be building the engine twice.
- The centre of the app is the checker ("it catches mistakes before they cost
  money"). Every threshold it uses is a `logic.trips.*` setting, per the rule
  that rules live in Settings → Logic, so the whole checker is editable without
  code.
- The capability list changes after every trip (W26). Keeping it as data means
  a new brief version is a re-extract and a rebuild, and the plug can hand a
  Claude chat the exact steps of a workflow.
- Destinations already knows places, costs per day and ways to get there; Trips
  reuses the same ideas (live links per leg, home city, sources) and links to
  it rather than copying.

**What we did not do.**
- Sending messages or calling businesses. The engine drafts the message (W27)
  and the call opening (which says it is automated), keeps the thread, and the
  checker says when to escalate; the person sends. Sends and calls need a
  provider, consent rules per country, and the person's OK every time.
- Live traffic and flight watching (W28). The Run tab gives leave-by times from
  the buffers and live links; watching needs keys and a background job (phase 7,
  outside data).
- Gmail and Calendar sync (W18, W19). The calendar file covers "add it to my
  calendar"; email sweeps wait for the outside-data phase.
