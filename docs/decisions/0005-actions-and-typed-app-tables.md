# 5. Apps write through named actions; each app has its own typed tables (2026-09-27)

**Chose:** every write an app can do is an action with a name
(`money.add_bill`), a typed input (a Pydantic model), a one-line
description, and a `dangerous` flag. Actions run inside one transaction and
record history like everything else. The engine exposes them all at
`POST /v1/actions/<name>` and lists them at `GET /v1/actions`.

Each app keeps its details in its own STRICT tables under
`apps/<app>/server/migrations`, keyed to the shared `entities` table where
the thing is a record (a bill is; a transaction isn't).

**Why:** the plan's rule is "apps never touch the data directly, they ask
the engine", and "each button is described clearly enough for an AI to
press it". One list of actions serves the pages today and the MCP plug in
phase 3 with no second description to keep in sync. Typed tables let the
database refuse bad data; a bill's amount is an integer of cents or NULL,
never "about $20".

**Cost:** a little ceremony per write. Reads stay plain GET endpoints.
