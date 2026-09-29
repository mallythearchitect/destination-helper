-- Trips: the Destination Helper. A trip is also a record in `entities`
-- (type = trip) for notes, tags, files, links, search and undo; this table
-- holds the trip details. Times are the destination's local time
-- (YYYY-MM-DDTHH:MM) with a zone name beside them. Money is integer cents in
-- the currency named on the row.
CREATE TABLE trips (
  id                 TEXT PRIMARY KEY,
  entity_id          TEXT NOT NULL REFERENCES entities(id),
  name               TEXT NOT NULL,
  purpose            TEXT NOT NULL DEFAULT 'personal',   -- personal | work | mixed
  stage              TEXT NOT NULL DEFAULT 'plan',       -- plan | prepare | run | done
  start_date         TEXT,                               -- YYYY-MM-DD
  end_date           TEXT,
  headcount          INTEGER NOT NULL DEFAULT 1,
  travelers          TEXT NOT NULL DEFAULT '[]',         -- names
  home_currency      TEXT NOT NULL DEFAULT 'USD',
  local_currency     TEXT,
  fx_rate            REAL,                               -- local units per 1 home unit, the day it was checked
  fx_date            TEXT,
  passport_country   TEXT,
  passport_expiry    TEXT,                               -- YYYY-MM-DD
  budget_night_cents INTEGER,                            -- caps in home currency, for the group
  budget_leg_cents   INTEGER,
  budget_day_cents   INTEGER,
  region_pack        TEXT,                               -- pack_helper.region_packs.id
  time_zone          TEXT,                               -- the destination's zone, default for items
  purpose_note       TEXT,                               -- what the trip is for
  version            INTEGER NOT NULL DEFAULT 1,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  deleted_at         TEXT
) STRICT;

CREATE TABLE trip_items (
  id               TEXT PRIMARY KEY,
  trip_id          TEXT NOT NULL REFERENCES trips(id),
  kind             TEXT NOT NULL,                        -- flight | train | bus | van | ferry | taxi | transfer | drive | stay | activity | storage | meal | other
  title            TEXT NOT NULL,
  from_place       TEXT,
  to_place         TEXT,
  start_at         TEXT,                                 -- local: YYYY-MM-DDTHH:MM, or YYYY-MM-DD for a stay's check-in day
  end_at           TEXT,
  time_zone        TEXT,
  status           TEXT NOT NULL DEFAULT 'idea',         -- idea | to_book | booked | confirmed | check_now | cancelled | done
  price_cents      INTEGER,
  currency         TEXT,
  basis            TEXT,                                 -- per_person | group  (NULL = not said yet: the checker flags it)
  headcount        INTEGER,                              -- on the booking; NULL = the trip's
  paid_by          TEXT NOT NULL DEFAULT 'me',           -- me | company | split
  tag              TEXT NOT NULL DEFAULT 'personal',     -- personal | work
  international    INTEGER NOT NULL DEFAULT 0,           -- flights: crosses a border (longer airport buffer)
  confirmation     TEXT,
  link             TEXT,
  operator         TEXT,
  contact          TEXT NOT NULL DEFAULT '{}',           -- {phone, whatsapp, line, email, app}
  last_departure   TEXT,                                 -- HH:MM: the last one of the day on this route, when it matters
  desk_hours       TEXT,                                 -- stays: front desk hours, e.g. 24h or 08:00-22:00
  lead_minutes     INTEGER,                              -- travel time to this item's start point
  price_checked_at TEXT,
  notes            TEXT,
  version          INTEGER NOT NULL DEFAULT 1,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  deleted_at       TEXT
) STRICT;
CREATE INDEX trip_items_trip ON trip_items(trip_id, start_at);

CREATE TABLE trip_expenses (
  id           TEXT PRIMARY KEY,
  trip_id      TEXT NOT NULL REFERENCES trips(id),
  item_id      TEXT REFERENCES trip_items(id),
  on_date      TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency     TEXT NOT NULL,
  basis        TEXT NOT NULL DEFAULT 'group',
  paid_by      TEXT NOT NULL DEFAULT 'me',
  tag          TEXT NOT NULL DEFAULT 'personal',
  note         TEXT,
  created_at   TEXT NOT NULL,
  deleted_at   TEXT
) STRICT;

CREATE TABLE trip_tasks (
  id         TEXT PRIMARY KEY,
  trip_id    TEXT NOT NULL REFERENCES trips(id),
  item_id    TEXT REFERENCES trip_items(id),
  title      TEXT NOT NULL,
  kind       TEXT NOT NULL DEFAULT 'todo',               -- entry | health | insurance | permit | phone | safety | pack | confirm | follow_up | todo
  due        TEXT,                                       -- YYYY-MM-DD
  done_at    TEXT,
  notes      TEXT,
  version    INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
) STRICT;

-- What the checker found. Recomputed on every run; a dismissed finding stays dismissed.
CREATE TABLE trip_findings (
  id         TEXT PRIMARY KEY,
  trip_id    TEXT NOT NULL REFERENCES trips(id),
  item_id    TEXT,
  rule       TEXT NOT NULL,
  key        TEXT NOT NULL,                              -- rule + what it is about: the same problem keeps one row
  severity   TEXT NOT NULL,                              -- blocker | warn | info
  message    TEXT NOT NULL,
  fix        TEXT,
  status     TEXT NOT NULL DEFAULT 'open',               -- open | dismissed | resolved
  first_seen TEXT NOT NULL,
  last_seen  TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(trip_id, key)
) STRICT;

CREATE TABLE trip_confirmations (
  id         TEXT PRIMARY KEY,
  trip_id    TEXT NOT NULL REFERENCES trips(id),
  item_id    TEXT NOT NULL REFERENCES trip_items(id),
  question   TEXT NOT NULL,
  channel    TEXT NOT NULL,                              -- whatsapp | line | sms | email | app | call
  to_address TEXT,
  message    TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'draft',              -- draft | sent | answered | no_reply | call
  sent_at    TEXT,
  reply      TEXT,
  replied_at TEXT,
  version    INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
) STRICT;

CREATE TABLE trip_workflow_runs (
  id         TEXT PRIMARY KEY,
  trip_id    TEXT NOT NULL REFERENCES trips(id),
  code       TEXT NOT NULL,                              -- W01..: pack_helper.workflows
  outcome    TEXT NOT NULL,                              -- proven | adopted | open | rejected
  note       TEXT,
  created_at TEXT NOT NULL,
  deleted_at TEXT
) STRICT;
