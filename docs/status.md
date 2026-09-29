# Status

## 2026-09-29 — the Organic look and the four screens from the mockup board

Malachi had Claude Design mock up Home, New trip, Inside a trip and Compare
on the Organic system and handed the board over ("the design upgrades are on
desktop"). Built from it (decision 0012):
- `ui-kit/organic.css` vendored; tokens, shell and app CSS re-mapped onto it
  (Caprasimo + Figtree, sand + terracotta + sage, pills, 28-px radii).
- Home = your trips as cards with days-to-go, photo, chips, stage, health;
  coming up; past trips. New trip = a three-column page with the five
  questions and a season panel from the local-tips pack. Trip = hero +
  journey with the checks and costs alongside; findings carry a one-tap
  `fix_action` (migration 0003; "Move it to 7:15 PM", "It's per person",
  "Add a stay", "Done"). Compare = "Same trip, cheaper place" for your
  dates and people. `date_flex` on the trip (fixed / flexible / unsure).
- The helper chat (`ui-kit/helper.js`, `trips.ask` through the switchboard,
  the `trips.ask` prompt, `/v1/trips/briefing/{id}`): answers, suggests,
  never changes the trip. Photos live from Wikipedia with the source shown.
- 49 tests. Checked headless at 1280 and 390 px: no console errors.

## 2026-09-28, late — User and Developer modes; reframed for travellers

Malachi: the AI inbox and Browse don't belong in front of a user; "what the
engine did today" is for the engine, not a standalone app; the wording read
like a developer's; "put a switch for now to switch between user and
developer." Done:
- A **User / Developer switch** in every header (`App.isDev()`, class
  `dev-only`, remembered per browser; user mode is the default). User mode is
  the app as a traveller sees it. Developer mode adds Home → Tracking and
  Workflows, the AI inbox, Browse, the engine pill, rule codes and first-seen
  times on findings, the Record button, Settings → Data / AI / Backup / Logic /
  Backups / History, and every "Settings → Logic" pointer.
- Home for users: the next trip, things to fix, still to book, your trips,
  and **Coming up** (deadlines, timed plans and blockers across every trip
  for the next two weeks) in place of the engine's run log.
- **Browse is History** for users: every trip, place and note kept, searchable.
- Wording: "Fix now / Worth a look / Tidy up" instead of blocker / warning /
  note; "Guide" and "Local tips" instead of Helper and Region; "Add to
  calendar"; no W-codes or pack names outside Developer mode.
- Destinations: a search toolbar, place cards with a fit ring, tier and tag
  chips, a taller map. Theme now follows the system by default.

## 2026-09-28, late — its own look and a UI/UX revamp

Malachi: "completely different design from the mindscape version"; "the
UI/UX needs a full revamp." Decision 0011. Done:
- A new design system in `ui-kit/` (tokens, shell, app): light and warm,
  coral + sea, Fraunces + Plus Jakarta Sans, rounded, dark mode by system.
  The sidebar pattern is gone; pill navigation and rails instead.
- Trips: a hero with the stage stepper and a **health score** (100 minus the
  open findings; weights in Settings → Logic → Trips · defaults), **New trip as
  the five onboarding questions** (v5; the fifth question's answers are new
  trip fields, `handling` and `may_contact`, migration 0002), the **journey
  timeline** (a stop per day, chapter chips, mode glyphs, check flags as
  coloured edges), and a **travel-day Run screen** with the next move first.
- Home: next-trip hero with the countdown; health per trip.
- Destinations: light map, coral pins. Browse, Settings and the AI inbox
  take the new look through the shared CSS.
- Checked headless at 1440 and 390 px on every page: no console errors, no
  horizontal scroll. 47 tests.

## 2026-09-28 — the repo is born

The Destination Helper became its own repo today, split out of
`mindscape-app` as a full standalone copy (decision 0010) a few hours after
the Trips app was first built there (decision 0009). Brief version at the
split: v7.

What it holds, working:
- **Trips** (`apps/trips`): trips as records; items (legs, stays, activities,
  pickups) with local times, per-person or group prices, who pays, work /
  personal; the checker (`checks.py`, about twenty rules, every threshold a
  `logic.trips.*` setting) with findings that persist; costs in two
  currencies split company vs me and work vs personal; W25 before-you-go
  list; W27 confirmations (message first, call if no reply, the call says it
  is automated; the engine drafts, the person sends); the calendar file; the
  helper catalogue and the Thailand region pack from `packs/helper.sqlite`;
  track records per workflow (W26).
- **Destinations** (`apps/destinations`): the atlas on the destinations pack
  (374 scored places + 34,000 GeoNames cities), goals and fit, cost per day,
  trip cost, ways to get there, the person's list, the source registry.
- **The engine**: vault, settings (7 sections, 23 logic settings), history
  and undo, records, packs, sources, tracking, analytics, prediction (series
  only; the cash projection stayed with Money), autonomous workflows
  (`trips.check_all` 06:00, `track.snapshot` 00:05, `predict.forecasts`
  00:10, `backup.nightly` 02:30, `sources.check` weekly), the AI switchboard,
  inbox and MCP plug (`destination-helper`).
- **The brief as data**: `scripts/extract_helper_doc.py` reads the docx;
  `packs/build_helper.py` builds the pack (10 sections, 93 questions, 29
  workflows, 12 guardrails, the Thailand pack, v7's Part A and B). All brief
  versions (v1 capabilities, v2 universal, v3, v7) sit in `docs/brief/` with
  a one-page Markdown of the whole thing.
- Tests: 50-odd, `scripts/check.sh` clean, page driven headlessly at desktop
  and phone width.
- `scripts/import_thailand_trip.py` seeded the first test trip (run
  2026-09-28). Two guesses in it: the Bangkok hotel Nov 22–28 and Phuket →
  Bangkok on Nov 22. Booked stays have no prices yet.

What v7 asks for that is not built yet (its "further and next"):
- The five onboarding questions as the New-trip flow (today the form asks
  them; v7 wants them as five steps, with "not sure yet" opening a
  same-trip-cheaper-place comparison and a season check).
- The planning layout: data on one side (places, stays, activities, routes,
  price history, businesses with reliability), filters on the other, the
  plan in the middle; a season / weather layer with flags in the plan.
- The visual timeline as a journey line (mockup in the brief), zoom from
  trip to hour, linked to the map, "you are here" during the trip, the recap
  after.
- The phone app: installable web app first, forwarded-email import, push
  notices; then texting businesses (Twilio / WhatsApp Business), live flight
  status, AI calls last. Target for Nov 13: trip setup, the vertical timeline,
  forwarded-email import and the checks, tested on the Thailand trip.
- Same trip, cheaper place; know-the-place-before-you-go; the reliability
  badge; trip health score; group mode; receipt capture.

Not built on purpose here: sending messages or calls, live traffic / flight
watching, Gmail sync (decision 0009).

Needs Malachi: open Trips (:8772), fix the two guessed dates, add the prices
from the confirmations, mark what is already confirmed; a name (v7: "First
Officer" looked clean, run a real trademark search); talk to 5–10 trip
organizers.

On GitHub since 2026-09-28: private repo `mallythearchitect/destination-helper`, branch `main`; CI runs ruff, the secrets scan, pytest and gitleaks on every push.
