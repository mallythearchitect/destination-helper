# How the Destination Helper works, in plain English

For anyone, coder or not, who wants to know what this thing is and what
happens when you click Save. The product brief behind it is
`docs/brief/destination-helper.md` (one page, every version folded in).

## The idea in one paragraph

A trip co-pilot. It **plans** the trip (routes, timing, costs), **checks the
plan** for the mistakes that cost money (a taxi booked before you land, a
price that is per person not total, the last ferry gone, a night with no
bed), helps you **prepare** (confirmations, the before-you-go list,
deadlines), and **runs** the trip (leave-by times, live links, what is
waiting on people). Work and personal on one trip, any size. Under it sits
one engine: one vault on this computer, records that connect, nothing ever
lost, a source on every number, every rule as data, and AI as hands that
only press buttons the apps already have.

## Two ways to look at it: User and Developer

The switch in every page's header. **User** is the app as a traveller sees
it: Home, Trips, Destinations, History (every trip, place and note you have
kept) and a short Settings. **Developer** shows the engine behind it: what
ran overnight and the numbers it tracks (Home → Tracking, Workflows), the AI
inbox, Browse (every record), the rule behind each finding, and Settings →
Data, AI, Backup, Logic and History. The choice is remembered in your
browser; nothing about the data changes.

## The apps

- **Trips**: the co-pilot itself, described below.
- **Destinations**: the atlas of places, scored with sources, with cost per
  day and the ways to get there.
- **AI inbox**: suggestions from AI workflows waiting for your OK, the
  models per job, the spend against the cap, test scores.
- **Browse**: every record the engine holds.
- **Settings**: profile, keys, display, AI, backups, and every rule as data.
- **Home**: your trips at a glance, what the engine tracked and did, the apps.

## The engine's own jobs

**Tracking.** A metric says what is measured in what unit; an observation is
one value of it, for one subject (a trip), as of one date, with where it
came from. Every night at 00:05 the engine writes, per trip: planned cost,
booked, still to book, open blockers, open warnings, tasks open, spent. So
Home can show how a plan firmed up over the weeks. Anything else can be
tracked with the `track.observe` action.

**Analytics.** Any tracked series rolled up by day, week or month, with its
trend, moving average and anomalies. The windows are Logic settings.

**Prediction.** A straight-line forecast with a band for every tracked
level, written nightly as "predicted" and scored against what happens.

**Autonomous workflows.** Five run on their own: the plan checker on every
trip at 06:00 (so new deadlines, stale prices and unanswered messages show
by morning), the tracking snapshot at 00:05, forecasts at 00:10, the backup
at 02:30, the source check weekly. Each is an ordinary action; each run is
recorded; a run missed while the Mac slept happens as soon as the engine is
up. The schedule is a Logic setting; any of them can be run now from Home.

## The pieces

**The vault.** One file on this computer, `vault/vault.db`, holds the data:
trips, items, tasks, findings, confirmations, records, settings, history,
observations. Git never sees it.

**Settings.** Seven sections: Profile, Maps, Display, Data, AI, Backup,
Logic. Every setting has a default, so a fresh vault already works. A change
saves as you make it and can be undone. Two windows saving the same thing:
the second is refused and shown both versions.

**History and undo.** Every change is written down: what it was, what it
became, when, and which app did it. Nothing is quietly overwritten. Undo
puts it back, and an undo is itself a change.

**Records.** Every thing the engine knows about is a record with a type, a
name, details, outside ids and a source; records link to each other, take
tags, notes and files, and are searchable. A trip is a record; a place you
mark in Destinations is a record. Browse shows them all.

**Actions.** Every write an app can do is a named, typed action described in
plain words, at `POST /v1/actions/<app>.<verb>`. It happens completely or
not at all and lands in history. The same list is what the AI plug offers a
Claude chat as buttons; one that deletes is marked dangerous and waits for
your OK.

**Packs and sources.** Reference data (places and their scores, the helper's
capability list, the region packs) lives in read-only files next to the
vault, so it can be rebuilt without touching anything you wrote. Every
outside link is in a source registry with a checker.

**Keys.** Google Maps, Mapillary, Claude: keys live in `.env`, never in the
vault, never in git. Pages only learn "set" or "not set".

**Backups.** Back up now, a nightly copy, pruning, and a restore test that
opens the newest copy and compares it with the live vault.

**One look, built once.** Every page loads the same files from `ui-kit/`
and adds only what is unique to it. The look is the Organic design system
from the mockup board (decision 0012): a sand ground, terracotta for the one
action that matters, sage for "fine", Caprasimo over Figtree, rounded shapes
and pill buttons, washed photos with their source. Every page has a tour, a
Go-to menu and the helper chat.

**The checks before a commit.** Tidy code, no leaked keys, tests pass. The
same three run on GitHub on every push.

## The rules, as data: Settings → Logic

Every feature that decides something by a number or a rule reads it from
Settings → Logic, not from the code. Each entry says what it does, which
feature reads it, and where its default came from; edit the JSON and the
whole engine follows, and the change is in history like any other. The
first eight:

| Setting | What it decides |
|---|---|
| Destinations · what cost per day covers | the lodging / food / transport / other shares; "no housing" removes lodging |
| Destinations · guessing a flight | dollars per mile each way and the floor |
| Destinations · goals and their weights | add a goal by adding a key; the list re-ranks |
| Destinations · scores computed from indexes | safety, affordability, quality of life as `value × multiply + add` from Numbeo |
| AI · prompt overrides | replace a workflow's prompt; logged as version "custom" |
| Trips · the checker's thresholds | airport buffers, the smallest gap between legs, pickup wait after landing, stale prices, passport months, deadline warning, late check-in hour, book-flights weeks |
| Trips · kinds of item | which kinds are legs, pickups, stays; the buffer before a non-flight leg |
| Trips · confirming a booking | the message template, hours to wait for a reply, channel order, what a call says first |
| Trips · the before-you-go checklist | the W25 tasks and how many days before departure each is due |
| Trips · comparing ways to do a leg | each mode's usual speed, time at the terminal, the road factor for straight-line distances, road routing on or off, the road-time factor per mode, how long lookups are kept, rank by fastest / cheapest / balanced, how much faster before the checker mentions it, the most ways per leg |
| Trips · defaults and words | what a new trip starts as, the card-rate markup, the calendar alarm, the words for stages, statuses, who pays, tags |
| Destinations · defaults and limits | the opening view, the population defaults and steps, how many Compare holds |
| Destinations · what a search looks at | the fields a search matches |
| AI · what each model costs | dollars per million tokens, in and out |
| AI · the inbox | the "sure" line for approve-all |
| AI · kinds of data a model may see | the scopes behind "what each model may see" |
| Records · kinds of record | the types Browse offers |
| Records · how two records can relate | the relationship words and how they read from each side |
| Sources · the link checker | the timeout and which codes mean dead |
| Backups · keeping copies | never remove more than leaves this many |
| Engine · size limits | the largest attachment and the largest CSV |

Thirty-odd in all (Workflows, Prediction and Analytics have theirs too). The Settings page groups them by app, and each shows
"Read by: ..." so you know what changes when you edit it.

The AI plug exposes them too (`logic_settings`, `settings_set`), so a
Claude chat can read or change a rule with your OK.


## Destinations, reference data and sources

**Packs.** Reference data, the kind the world already has (cities, their
scores from published indexes, costs, coordinates), lives in read-only
files called packs, next to the vault, not in it. The engine attaches
every pack in `packs/` when it opens. Your notes about a place live in
the vault as records, so a pack can be rebuilt or replaced without touching
anything you wrote. `packs/build_destinations.py` builds the first pack
from the data the old Destinations page carried.

**A source on every figure.** Each row in a pack says which dataset it came
from; each dataset says its origin and method and carries a confidence:
*hand-set* (someone's judgment), *index-derived* (computed from a published
index by a written formula), *estimate*, or *verified*. Index-derived
scores name the index (Kearney GCI, GFCI, StartupBlink, Startup Genome,
Numbeo, EIU) and its edition, with the link. The badges on the page show
this everywhere a number appears.

**The source registry.** Every outside link the packs use is registered
(Settings has no page for it yet; the Destinations Sources tab shows it).
"Check every link now" re-fetches each one and marks it ok, changed (the
page differs from last time), dead (gone) or error. A source added by
hand goes through the same check.

**Destinations.** Sidebar: what to show (US business cities, international
business cities, leisure destinations, all) and which goal to rank for
(growth, entrepreneurship, tech, network, lifestyle). *Atlas* is the map
and the list, with search, tier and budget filters and a sort; click a
place for the detail: description, cost per day, distance from your home
city (Settings → Profile), scores as bars with their confidence, index
values with links, where it comes from, and your status. *Compare* puts up
to four side by side. *Trip cost* shows days × people × cost per day plus
flights, guessed from distance unless you type your own. *My list* is
every place you marked (shortlist, want to go, base candidate, visited) or
noted; each one is a record you can open in Browse. *Sources* is the
provenance page described above.

**Ways to get there.** The first thing in a place's popup, before the
information: buttons that open live sites for the trip from your home
city: Directions (Google Maps), Flights (Google Flights, live fares), All
ways (Rome2Rio: plane, train, bus, ferry, drive with live times and
prices), and Train (Amtrak, US places). They are live sites, not stored
data, so they are always current; they are listed in the source registry
like everything else.

**The whole world, not just the major stuff.** Besides the 184 scored
places, the pack holds every city of 15,000 people or more from GeoNames
(34,000 of them, CC BY 4.0): name, country, coordinates, population, time
zone. They show as small grey dots, sized by population; a population
filter keeps the map readable, and a search looks at all of them. They
have no scores until a source scores them (phase 7, outside data).

**Topics beyond tech.** Eight domains now: career, entrepreneurship,
tech, network, lifestyle, plus safety, affordability and quality of life,
the last three computed from Numbeo's indexes where a city is covered and
marked index-derived. Goals to rank for: growth, entrepreneurship, tech,
network, lifestyle, affordable, safe & calm, balanced.

**What the words mean.** The Sources tab says, in plain words, what a
business city is, what a leisure destination is, how each tier is set,
and what cost per day covers: one person's typical day, split into
lodging 45%, food 30%, transport 10%, other 15%. Trip cost has an "I need
a place to stay" box; untick it and lodging drops out.

Not carried over from the old page (yet): the Path Planner and the Street
& 3D view (which needs the Google key).


## Trips: the Destination Helper

**What it is.** A trip co-pilot: it plans the trip, then helps you run it.
Work and leisure, any size, from two weeks abroad to a Saturday outing. The
brief behind it is `destination-helper-v3.docx` (Sep 28, 2026), and the app
is built around the three things a normal planner doesn't do: it **checks the
plan**, it **handles work and personal on one trip**, and it **runs the trip**.

**A trip.** New trip is the brief's five questions (W24, v5): who's going and
is it work, personal or both; where and when, or not sure yet; the budget
and what matters most; what's already booked; how much the app should
handle (plan it for me, check my plan, just remind me) and whether it may
message, then call, businesses for you. Everything else (passport, exchange
rate, caps per leg and per day) sits in Trip settings and is asked only when
a step needs it. The answer says what is still missing; the helper's first
two guardrails (G01 ask the headcount, G02 ask the budget) are built in.
The trip's header shows its stage as a stepper you click along, and a
**health score**: 100 minus a weight per open finding, never under 0. A trip is also a record, so notes, tags, files
and links come from the engine, and Browse finds it.

**Items.** Everything in the plan is an item: a leg (flight, train, bus, van,
ferry, taxi, transfer, drive), a stay, an activity, bag storage, a meal. Each
has a local time, where it starts and ends, a status (idea, to book, booked,
confirmed, check now, cancelled, done), a price with its currency and
**whether it is per person or for the group** (G03; a price that doesn't say is
flagged), who pays (I pay, company pays, split) and a work / personal tag, the
confirmation number, the operator and how to reach them, and, when it matters,
the last departure of the day and the front desk hours.

**Timeline.** A journey line: a stop per day, the night's stay on each (a
day with no stay says so in amber), chapter chips at the top to jump between
places, and every leg, stay and activity as a card with its mode glyph. A
red edge means the checker has a blocker on that item, amber a warning. Click an item for the live links first (directions,
flights, all ways on Rome2Rio, the region's booking site with the date and
headcount filled in, flight status), then the details, the checker's findings
on it, and its confirmations. Legs show "be there by" from the buffers and
"leave by" once you give the leg its travel time.

**Compare ways (W02, every way from A to B).** Any leg can hold up to ten
ways of doing it, and a leg you haven't settled yet can be compared before
it exists ("Compare ways" in the trip's header; it shows on its day as a
"Deciding" card). Each way is a mode with a time, or a distance and a speed,
and then the minutes are worked out the way Malachi's MIS-310 route
optimizer did it: **distance ÷ speed × 60**, a distance or speed of zero or
less is skipped as invalid, and the fastest wins. Around that rule: a time
you type always beats the arithmetic, and your own distance and speed come
next. Leave them empty and the app works it out when you save the way: it
finds the two places on OpenStreetMap (or in the GeoNames cities), then car,
taxi, transfer, van and bus legs take a real road route from OSRM, with the
road distance and the driving time (a bus gets 15% longer). Ferries go
straight across the water, flights take the great circle, trains the straight
line times 1.3, each at the mode's usual speed. Those lookups happen only
when a way is saved, are cached for 90 days, and can be switched off in
Settings → Data; "Re-estimate" looks them up again. Time at the airport,
pier or station is added for a door-to-door figure; the price
shows per person and for the group in both currencies. The ways are ranked
fastest, cheapest or balanced, with the fastest, the cheapest and the best fit
named, and a way that leaves after the last departure of the day or breaks
the per-leg budget is flagged and never called the best. "Use this one"
writes the mode, times, price and last departure onto the leg (or makes the
leg); the other ways stay for comparison. The checker then notes a leg still
being decided, and a way at least 15 minutes faster door to door than the one
you picked, with a one-tap "Use it". Every number is in Settings → Logic →
Trips · comparing ways to do a leg.

**Checks.** The centre of the app. Plain rules over the plan, run after every
change (and on demand), each with a fix:
- a pickup set before the ride it meets has arrived (the Thailand taxi: 12:00 PM
  against a 6:45 PM landing);
- a price with no per-person / group basis; a passenger count that isn't the
  group's;
- nights with no stay, or two stays on one night (G07);
- two timed things that overlap; legs too close together; not enough time at the
  airport (2 h domestic, 3 h international);
- a departure after the last one of the day, or an arrival too late to catch it;
- a late check-in with nothing known about the front desk;
- a stay, leg or day over its budget cap (G02);
- a price last checked more than a week ago (G05); a budget flight left unbooked
  inside six weeks; a booked thing outside the trip dates ("booked for the old
  plan"); a booked thing with no price;
- a passport that runs out less than six months after the trip; local prices
  with no exchange rate;
- a deadline within three days, or missed; a confirmation with no reply.

Findings are kept: a fixed one is marked resolved, a dismissed one stays
dismissed on later runs, and every threshold is a setting (Settings → Logic →
Trips · the checker's thresholds).

**Costs.** Per person and for the group, in the local currency and yours at
the rate on the trip (with a note that a card's rate is usually about 2%
worse), planned against booked, **I pay against company pays**, work against
personal, by kind and by day; what was actually spent, logged from the Run
tab or from any item. A price in a third currency is listed as unconverted
rather than guessed.

**Prepare.** W25 builds the before-you-go list with deadlines before departure
(entry rules, health, insurance, permits, phone and plug, safety, packing) from
the setting that lists them, plus the region pack's arrival-card and visa lines
(Thailand: the online arrival card, filed no more than 72 hours before
landing). Tasks show on the Timeline's day, block the checker when missed, and
go on the calendar file.

**Run.** The travel-day screen: the next move first (what it is, when, be
there by and leave by, the confirmation code, the live links), then today
and tomorrow, what is waiting on people, and quick expense logging. The engine does not watch
traffic or flights by itself yet; that is the next step for W28 and needs keys
and a background job.

**Confirm (W27).** Pick the booking and the exact yes/no you need ("can you
hold our bags from 11 to 3?"). The engine drafts the message from a template
in Settings, picks the channel the way the region's businesses answer (Thailand:
WhatsApp or LINE first) and the operator's contact, and gives you a one-tap
link (WhatsApp, text, email). You send it and mark it sent. No reply within the
set hours and the checker says to call; the call opening says up front that it
is automated. Log the reply; if it changes the plan, the booking is flagged
Check now.

**Helper.** The capability list itself as data: 93 question codes by section
(GO, READY, GET, TIME, STAY, DO, MONEY, BOOK, ADMIN, TALK), 29 workflows with
when they run and their steps, 12 guardrails with why each exists, the
methods (setup, the defaults for every answer, where answers come from, the
checks, answer formats), the region pack template, the brief and the market
scan. Log how a workflow did on this trip (proven, adopted, open, rejected):
that is W26, wrapping up a trip. It lives in `packs/helper.sqlite`, built from
the brief by `scripts/extract_helper_doc.py` and `packs/build_helper.py`, so a
new version of the brief is a re-extract and a rebuild.

**Region.** The region pack for the trip's country: money, airports and
airlines (which budget airlines the big sites miss), the ground-transport site
and its quirks, piers and stations with the last departures, getting around,
how businesses prefer to be messaged, luggage storage, fees, seasons, scams,
entry rules, confusing names, stays, booking forms, and worked examples per
question code. The sites are in the source registry like everything else.

**The plug.** A Claude chat can read the same list and the real plan:
`helper_catalogue`, `helper_workflow`, `helper_region`, `trips_list`,
`trip_plan`, `trip_checks`, `trip_costs`, and every `trips_*` action. "Compare
every way from Krabi to Phuket" is W02 run against the plan; the steps come
from the pack.


## The AI part

The models are the brain; the engine is the hands. Nothing here builds a
second AI. It builds the plug that lets AI use the apps, a switchboard that
picks which model does each job, and a few safety rails.

**Jobs, not providers.** A workflow asks the engine for a job: sort, read,
draft or answer. Settings → AI says which model does each job and which
backup takes over if the first fails. Claude is the default; a model on
this machine (through Ollama, once installed) can be the backup or take a
job on its own. Switching is a settings change, not a rewrite.

**What each model may see.** Settings → AI has a line per kind of data:
trip data (bookings, prices, operator contacts) and records. "cloud" means
any model, "local" means only one on this machine, "none" means no model.
The switchboard refuses a call that breaks that.

**The cap and the log.** A monthly spending cap across every AI service;
when it is reached, background jobs stop. Every call is logged: which model,
for which job, what it saw (the first 400 characters), what it said, what it
cost, how long it took, whether it worked. The Log tab of the AI inbox shows
it all.

**The AI inbox.** A workflow never changes anything itself. It files
suggestions, and each waits for your OK. Approve runs the ordinary action
(so it lands in history and can be undone). Change the category first and
it learns from the correction. "No" rejects it. "Approve all 85%+ sure"
takes the confident ones in one go.

**The first workflow: sorting bank rows.** Press "Sort new bank rows now"
on the AI inbox after an import. The engine gathers recent rows with no bill
or category, the list of your bills with their statement words, and the
categories; the model answers with a category, a bill or income for the
rows that pay one, a confidence, and a few words of why. The engine checks
the answer (money out can only pay a bill, money in can only be income, only
known categories) and files one suggestion per row. It then stops. The rule
from phase 2 still runs first at import time; the AI handles what the rule
could not.

**Test scores.** Every suggestion you approve or correct becomes a labelled
example. The Test scores tab scores any model against them: examples given,
how many it got right, what it cost. Before moving a job to another model or
changing a prompt, score it; same or better means switch.

**The plug (MCP).** `scripts/install_mcp.sh` registers the engine with
Claude Code as "destination-helper". After that a Claude chat has the engine's
buttons: ask "what's due this week?" and it reads the due list; say "mark
Rent paid" and it presses the same action the page does. Anything that
removes or pays is marked dangerous and the chat asks you first. Every
press lands in history like everything else. For Claude Desktop, add the
same command to its config file: the script prints it.

**Rules.** Workflows before agents: fixed steps, AI on the fuzzy part only.
AI can only press buttons the apps already have. Anything that sends, pays
or deletes waits for you. Keep a workflow only if it saves real time.


## Where the data is

One file: `vault/vault.db` in this repo's folder. Attached files sit next to
it in `vault/files/`, backups in `vault/backups/`. Git ignores the whole
folder. The first trip, Thailand (Nov 13–28, 2026), was seeded from the
brief by `scripts/import_thailand_trip.py`; the script can be run again and
does nothing if the trip is there.

## What happens when you click Save

1. The page sends the field to the engine with the version it last saw.
2. The engine checks the value makes sense.
3. Inside one all-or-nothing transaction it compares versions, writes the
   new value with version + 1, and adds a history row with before and after.
4. The page shows "saved".

## Where things are

    destination-helper/
      engine/        the engine (Python): store, records, history, settings, sources, packs, tracking, workflows, the AI part
      apps/          trips (the co-pilot), destinations, ai (the inbox), system (Settings, Browse), launcher (Home)
      packs/         the reference data and the scripts that build it
      ui-kit/        the shared look
      scripts/       start, check, back up, extract the brief, seed the Thailand trip
      tests/         proof that it works; run with scripts/check.sh
      docs/          this file, status, decisions, the brief (docs/brief)
      vault/         your data, backups and logs (never in git)
      .env           your keys (never in git)

## Words you will see

- **API**: the engine's front door. Pages talk to it at addresses starting
  with `/v1/`. Apps never open the vault directly.
- **Version**: a counter on each setting that goes up by one per save. It is
  how the engine notices two windows disagreeing.
- **Migration**: a numbered file that adds a table to the vault. Applied once,
  in order, so an old vault upgrades itself.
- **Transaction**: a group of writes that either all happen or none do.
