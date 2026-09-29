-- Tracking: numbers over time. A metric says what is measured; an
-- observation is one value of it, for one subject, as of one date, with
-- where it came from. Everything analytics and prediction use starts here.
CREATE TABLE metrics (
  id       TEXT PRIMARY KEY,          -- dotted: trips.planned_cost, trips.open_blockers, destinations.fit ...
  label    TEXT NOT NULL,
  unit     TEXT NOT NULL,             -- cents | count | score | percent | miles | text
  kind     TEXT NOT NULL,             -- level (a balance, a score) | flow (spend per period) | event
  app      TEXT NOT NULL,
  meaning  TEXT NOT NULL,             -- plain words
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE observations (
  id         TEXT PRIMARY KEY,
  metric_id  TEXT NOT NULL REFERENCES metrics(id),
  subject    TEXT NOT NULL,           -- what it is about: an account id, a category, a place id, 'all'
  as_of      TEXT NOT NULL,           -- YYYY-MM-DD the value is for
  value      REAL NOT NULL,
  source     TEXT NOT NULL,           -- where it came from: 'track.snapshot', 'import', a URL, 'you'
  confidence TEXT NOT NULL DEFAULT 'verified',   -- verified | estimate | predicted
  run_id     TEXT,                    -- the workflow run that wrote it, if any
  created_at TEXT NOT NULL,
  UNIQUE(metric_id, subject, as_of, source)
) STRICT;
CREATE INDEX observations_lookup ON observations(metric_id, subject, as_of);

CREATE TABLE workflow_runs (
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  trigger    TEXT NOT NULL,           -- schedule | startup | you | mcp
  started_at TEXT NOT NULL,
  finished_at TEXT,
  ok         INTEGER,
  result     TEXT,                    -- JSON
  error      TEXT
) STRICT;
CREATE INDEX workflow_runs_name ON workflow_runs(name, started_at);
