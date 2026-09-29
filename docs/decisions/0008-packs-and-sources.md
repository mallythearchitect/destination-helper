# 8. Reference data lives in read-only packs; every figure keeps its source (2026-09-28)

**Chose:** reference data (cities, indexes, costs, coordinates) is built
into read-only SQLite files in `packs/`, attached to the vault connection
at open. The vault holds only what the person adds: a place they mark or
note becomes a record carrying the pack's id. Each pack row names its
dataset; each dataset carries origin, method and a confidence; each
index-derived score names the index and edition, with links. A source
registry in the vault lists every outside link and a checker re-fetches
them.

**Why:** the plan's rule: "reference data sits in separate read-only
files, so updating it never wipes your notes", and "every number keeps its
source and date". Packs are also what a public demo ships with: nothing
personal is in them, so `packs/destinations.sqlite` is committed.

**Cost:** two places data can be (pack or vault). The rule is simple: if
the world made it, pack; if you made it, vault.
