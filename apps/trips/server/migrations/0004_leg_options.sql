-- Ways to do one leg (W02, "Every way from A to B"). Each option is a mode with
-- a time, or a distance and a speed the minutes are worked out from
-- (distance / speed x 60). An option belongs to a leg already in the plan
-- (item_id), or to a leg still being decided (day + from + to). Choosing one
-- writes it onto the leg, or makes the leg.
CREATE TABLE trip_options (
  id             TEXT PRIMARY KEY,
  trip_id        TEXT NOT NULL REFERENCES trips(id),
  item_id        TEXT REFERENCES trip_items(id),
  day            TEXT,                         -- YYYY-MM-DD, for a leg not in the plan yet
  mode           TEXT NOT NULL,                -- a transport kind: flight, train, bus, van, ferry, taxi, transfer, drive
  label          TEXT,                         -- e.g. "Ferry via Ko Yao", "Nok Air 5:20 PM"
  from_place     TEXT,
  to_place       TEXT,
  distance_miles REAL,                         -- NULL = estimate it from the two places
  speed_mph      REAL,                         -- NULL = the mode's usual speed (Settings → Logic)
  minutes        INTEGER,                      -- ride time when known; beats distance and speed
  depart_at      TEXT,                         -- local YYYY-MM-DDTHH:MM
  price_cents    INTEGER,
  currency       TEXT,
  basis          TEXT,                         -- per_person | group
  last_departure TEXT,                         -- HH:MM, the last one of the day on this route
  link           TEXT,
  notes          TEXT,
  chosen_at      TEXT,
  version        INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  deleted_at     TEXT
) STRICT;
CREATE INDEX trip_options_trip ON trip_options(trip_id, item_id);
