# 0010 · The Destination Helper is its own repo, a full standalone copy

**Date:** 2026-09-28

**What we chose.** Malachi: "this app should be in its own repo." Of the
three shapes offered (engine as a dependency, full standalone copy, or an
empty repo with a plan), he chose the **full copy**: this repo carries its
own copy of the engine, the ui-kit, the Destinations app and the Trips app,
and runs with no link to `mindscape-app`. Data is duplicated on purpose (his
words: "the data might have to be duplicated"): its own vault, its own
packs, its own seeded Thailand trip.

**Why.**
- The brief's Part A is about the Helper as a product for other people.
  A product that needs another private repo to run cannot be handed to
  anyone.
- Simplest to reason about: one folder, one venv, one port (8772), one
  vault. A stranger can start it from the README alone.

**The cost, accepted.** Two copies of the engine to keep in step. When a
fix lands in one engine and matters to the other, it is ported by hand and
noted in status.

**What was cut from the copy.** Everything Money: the Money app, its
settings and logic, the cash projection, the bank-row AI workflow, the
Mally's month. The engine's tracking, analytics, prediction and workflow
runner stay and point at Trips (per-trip numbers nightly, the checker on
every trip at 06:00). Trips was removed from `mindscape-app` the same day.
