# 0012 · The look and the screens come from the mockup board

**Date:** 2026-09-29

**What we chose.** Malachi had Claude Design produce a mockup board
("Destination-helper UI mockups": Home 2a, New trip 1c, Inside a trip 1b,
Compare 3a) on the **Organic** design system: a sand ground, terracotta for
the one action, sage for "fine" and the trust layer (prices, dates,
bookings), Caprasimo display over Figtree, over-rounded shapes, pill buttons,
washed photographs. The app now follows those screens, and Organic's
stylesheet is vendored as `ui-kit/organic.css` with `ui-kit/tokens.css`
mapping the names every page uses onto its variables.

**The screens.**
- **Home** is a list of trips: a days-to-go circle, a washed photo, the
  name, one line of facts, chips for what needs doing, the stage and the
  health; "coming up" under it; past trips with what they cost.
- **New trip** is a page, not a dialog: the five questions in a rail on the
  left, one question at a time in the middle, a photo and the season and
  entry notes for the place on the right (from the local-tips pack).
- **Inside a trip**: a hero with the photo, the stage stepper, the health
  ring, "Add something / Check my plan / Add to calendar / Settings"; the
  journey line on the left with a stop per day and each item's facts in one
  sentence; the checks alongside with a **one-tap fix** on each ("Move it to
  7:15 PM", "It's per person", "Add a stay", "Done") and what the trip costs.
- **Compare** is "Same trip, cheaper place": up to four places side by side
  with a photo, your pick against the rest, fit, a day here, the whole trip
  for your dates and people, safety, day-to-day life, getting there, and the
  live look-ups.
- **The helper chat**: a floating "h" on Home and Trips. It answers from the
  plan, the checks and the local tips through the switchboard ("answer"
  job), follows the playbook's workflow and names it, and never changes the
  trip. Needs a model and key in Settings → AI.

**Photos.** Every photo is pulled live from Wikipedia's page summary for
the place, washed, with the source under it; a dashed placeholder with the
name when there is none. No photo is stored.

**Left out on purpose.** Weather for your dates and what travellers say
(no data source yet; the season notes come from the local-tips pack), the
time-scaled journey line and day/night shading from the brief's own mockup,
the sea colorway tweak (sage is the second voice for now).
