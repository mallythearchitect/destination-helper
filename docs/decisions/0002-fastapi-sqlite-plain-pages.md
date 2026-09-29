# 2. FastAPI + SQLite for the engine; plain HTML pages for now (2026-09-27)

**Chose:** Python with FastAPI for the engine and SQLite (WAL mode, STRICT
tables, foreign keys on) for the vault, as the plan says. Pages are plain
HTML + JavaScript for now, loading the shared `ui-kit` stylesheets.

**Why:** FastAPI gives typed request checking and a free API reference page
(`/v1/docs`). SQLite is one file, needs no server, and the Route Map already
uses it. The plan calls for TypeScript + Lit + Vite pages, but node is not
installed on this machine yet, and the Settings page is small; the move to
TypeScript can happen when the shared look is pulled out in phase 4, with no
change to the API.

**Not chosen:** the standard-library-only server the first skeleton hinted
at; the plan's tool table picks FastAPI and the typing pays for itself.
