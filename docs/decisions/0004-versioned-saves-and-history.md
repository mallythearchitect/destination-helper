# 4. Every save carries a version, and every change is kept (2026-09-27)

**Chose:** each setting row has a version counter. A save sends the version
the page last saw; if the vault has moved on, the engine answers 409 with
both values and the page shows them side by side. Every write also appends a
history row (before, after, action, app, time), and undo replays "before" as
a new change.

**Why:** the plan's own test is "saved data never overwritten". Two windows
editing the same setting was the concrete failure in the old pages. Keeping
history makes undo trivial and makes AI actions (phase 3) safe: anything the
AI does lands in history and can be reversed.

**Cost:** one extra table and a version field in every write. Cheap.
