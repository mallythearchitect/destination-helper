# 0011 · Its own look and layout, not the MindScape's

**Date:** 2026-09-28

**What we chose.** Malachi: "this app needs to have a completely different
design from the mindscape version" and "the UI/UX needs a full revamp." So
the Destination Helper has its own visual system and its own layout:

- **Look.** Light and warm: a sand ground, white cards, ink text, coral for
  the one action that matters, sea for links, sun for warnings. Fraunces
  (a serif with an optical axis) for display and numbers, Plus Jakarta Sans
  for reading. Rounded surfaces, soft shadows. Dark mode follows the system.
  The MindScape is dark, gold and Barlow, with square edges.
- **Layout.** No sidebar. A sticky header with pill navigation, and the
  page's own controls as horizontal rails under it, on every width. The
  markup kept the old class names (`.side-layout`, `.sidebar`, `.sidenav`,
  `.opts`) so every page rendered on day one; the CSS gives them the new
  shape.
- **Trips, redesigned from the brief.** A trip hero with the stage stepper
  and a health score; New trip as the five onboarding questions (v5); the
  timeline as a journey line with a stop per day, the night's stay on each,
  mode glyphs, chapter chips, and the checker's flags as coloured edges (v6);
  a travel-day Run screen that shows only the next move (v7); item details
  as a bottom sheet on a phone.
- **Home.** The next trip as a hero with the countdown; health dots per trip.
- **Destinations.** A light map (OpenFreeMap Positron) with coral pins.

**Why.** It is a product for other people, and it should not look like a
personal dashboard. The brief's own UI notes (journey, not a grid; phone
first; the next move on travel days) asked for this shape.

**What is still the brief's, not built.** The photo bubbles and time-scaled
journey line, day/night shading, the season strip, "you are here" during the
trip, the shareable recap, the map linked to the timeline.
