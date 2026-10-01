# Changelog: everything done, in order

Every change to the Destination Helper since the first line was written,
oldest first, with the commit it landed in. What is still open is at the end.
The why behind the big choices is in `docs/decisions/`; where things stand
week to week is in `docs/status.md`.

## 2026-09-28 · Built inside the MindScape engine

**The brief.** Three Word briefs on the Desktop: v1 "capabilities" (from the
three Thailand planning chats), v2 "universal" (made to work anywhere, with
codes, fill-ins and region packs) and v3 (one file for the app: the product
brief, the market scan, and the capability list). v3 was the spec.

**Trips on the engine** (mindscape-app `c4473d2`, decision 0009)
- The brief as data: `scripts/extract_helper_doc.py` reads the docx into JSON;
  `packs/build_helper.py` builds `packs/helper.sqlite`: 93 question codes in
  10 sections, 29 workflows with steps, 12 guardrails with why each exists,
  104 method lines, the Thailand region pack with 73 worked examples, and the
  booking sites for the source registry.
- Tables: trips (each also a record), items, expenses, tasks, findings,
  confirmations, workflow track records.
- The checker, about twenty plain rules with a fix on each: a pickup set
  before the ride it meets has landed (the Thailand taxi: 12:00 PM against a
  6:45 PM landing), a price with no per-person or group basis, the passenger
  count, nights with no stay or two, overlaps, tight connections, the airport
  buffer, the last departure of the day, late check-ins, budget caps, stale
  prices, budget flights left late, bookings outside the trip dates, passport
  validity, the exchange rate, deadlines, confirmations with no reply. Every
  threshold is a Settings → Logic setting.
- Costs per person and for the group, in two currencies, company pays against
  I pay, work against personal; the before-you-go list (W25); confirmations,
  message first and a call only if there is no reply, the call saying it is
  automated (W27); the calendar file; track records per workflow (W26).
- The page, the plug (MCP tools for the plan, the checks and the helper's
  playbook), and `scripts/import_thailand_trip.py`, which seeded the first
  test trip (Thailand, Nov 13–28, 2026).

**Its own repo** (`1857e24`; mindscape-app `9854d73`; decision 0010)
- Malachi: "this app should be in its own repo"; "the data might have to be
  duplicated." A full standalone copy: its own engine, ui-kit, Destinations,
  Trips, packs, vault and port (8772). Money and everything about the
  Mally's month came out. The engine's tracking, prediction and nightly runs
  now point at trips: per-trip numbers after midnight, the checker on every
  trip at 6 AM, forecasts, the backup, the weekly source check.
- The brief moved to v7 (adds who it is for, onboarding, the planning layout,
  the timeline concept, the phone-app build plan). All four versions sit in
  `docs/brief/` with a one-page Markdown of the whole thing.

**Its own look** (`83d20ef`; decision 0011)
- "Completely different design from the MindScape version" and "the UI/UX
  needs a full revamp": a light, warm design system, pill navigation instead
  of the sidebar, a trip hero with the stage stepper and a health score, New
  trip as the five onboarding questions, the timeline as a journey, a
  travel-day Run screen.

**User and Developer modes** (`2b83435`)
- A switch in every header. User mode is the app as a traveller sees it;
  Developer mode adds the engine: workflows, tracking, the AI inbox, Browse,
  rule codes, the Logic settings. Home leads with "coming up" instead of the
  engine's run log; Browse reads as History; findings say fix now, worth a
  look, tidy up.

**On GitHub** (`46957f8`): `mallythearchitect/destination-helper`, made
private, later set public by Malachi so Claude Design could read it.

## 2026-09-29 · The mockup board

**The Organic look and four screens** (`7ed8eb0`, `4c283a3`; decision 0012)
- From Malachi's Claude Design board: Organic's sand, terracotta and sage,
  Caprasimo over Figtree, rounded shapes, washed photos with their source
  (pulled live from Wikipedia). Home as a list of trips; New trip as a page;
  the trip as a hero plus the journey with the checks and costs alongside;
  Compare as "same trip, cheaper place".
- Every finding can carry a one-tap fix ("Move it to 7:15 PM", "It's per
  person", "Add a stay", "Done"). The dates question's answer is kept.
- The helper chat: a floating "h" that answers from the plan, the checks and
  the local tips, follows the playbook, and never changes the trip.

**The timeline as chapters** (`5efc935`)
- "If something spans multiple days, let that show": each stay is one block
  over its nights with the days inside, empty days folded into one line, a
  dashed block for nights with no stay, arrivals shown on the day they land,
  everything in date and time order. "Add price" wherever a price is missing.

## 2026-10-01 · Compare ways

**The route optimizer inside the trip's sequence** (`3acb9ea`)
- From Malachi's MIS-310 Travel Route Optimization script, the idea and not
  the code: minutes = distance ÷ speed × 60, a zero or negative distance or
  speed is skipped, the fastest wins.
- Up to ten ways per leg, or a leg compared before it exists ("Deciding" on
  its day). A typed time wins; usual speeds and estimated distances fill the
  gaps, labelled; time at the terminal makes it door to door; prices per
  person and for the group in both currencies; flags for the last departure
  and the per-leg budget; ranked fastest, cheapest or balanced. "Use this
  one" writes the leg. The checker notes undecided legs and a clearly faster
  way, each with a one-tap fix.

**Road distances, not straight lines** (the commit after `3acb9ea`)
- The limit it fixes: a straight line undercounts roads that go around water.
  Krabi → Phuket by van estimated 1 h 05; the road is 111 miles, 2 h 48.
- When a way is saved, its two places are found with OpenStreetMap's
  Nominatim (a plainer second try for names it doesn't know, like "Phuket
  Town"), falling back to the GeoNames cities. Car, taxi, transfer, van and bus
  legs then get a real road route from OSRM on OpenStreetMap data: the road
  distance and the driving time, times a factor per mode (a bus 1.15).
  Ferries go straight across the water; flights take the great circle; trains
  keep the straight line × 1.3.
- The order of precedence: a time you type wins; then your distance and
  speed through the formula; then the road time; then the mode's usual speed.
  Every figure says where it came from.
- Network only when a way is saved, never when a page reads a plan.
  Answers are cached 90 days; a failed lookup is not remembered, so it is
  tried again. Nominatim is held to one request a second and both requests
  name the app. Two switches: Settings → Data (Nominatim, OSRM) and Settings →
  Logic → Trips · comparing ways to do a leg (road routing, factors, cache).
- "Re-estimate" in the comparison sheet looks everything up again
  (`trips.refresh_ways`). Migration 0005. Tests never touch the network.
- Checked live on a scratch copy of the vault: van 111.4 mi, 2 h 48 (2 h 58
  door to door); speedboat 28.9 mi across the bay, 2 h 06 door to door, so it
  ranks fastest; the minivan stays cheapest.

## Still open

- **Your data in the app.** The Thailand trip's two guessed dates (the
  Bangkok hotel Nov 22–28 and Phuket → Bangkok on Nov 22), the prices of the
  eight unpriced items, which bookings are confirmed.
- **The public repo** shows the Thailand dates, the hostels by name and the
  default home city. Scrub them, or make the repo private again.
- **The Claude key** (Developer mode → Settings → AI) so the helper chat
  answers.
- **Your real ways.** No ways are saved on the Thailand trip yet; the ones above
  were checked on a copy. Add the real options for Krabi → Phuket and Phuket →
  Bangkok, with the times and prices you've seen.
- **Not ported from mindscape-app:** "every city ranks for business and
  leisure" (`6b7a86b`, built there after the split).
- **The brief's next asks, not built:** weather and travellers' reviews for
  your dates, the time-scaled journey line with day and night shading, "you
  are here" during the trip, the shareable recap, the phone app with
  forwarded-email import (the Nov 13 target), texting businesses, live
  flight and traffic watching, the reliability badge, group mode.
- **Business questions from the brief:** the name (First Officer needs a real
  trademark search), how it makes money, talking to 5–10 trip organizers.
