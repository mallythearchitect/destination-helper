-- The source registry: every outside place a figure comes from, and a
-- checker that re-fetches links and flags changes.
CREATE TABLE sources (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  url          TEXT NOT NULL UNIQUE,
  kind         TEXT NOT NULL,            -- index | service | dataset | page | api
  license      TEXT,
  used_for     TEXT,
  first_seen   TEXT NOT NULL,
  last_checked TEXT,
  status       TEXT NOT NULL DEFAULT 'unchecked',   -- unchecked | ok | changed | dead | error
  http_status  INTEGER,
  fingerprint  TEXT,                     -- sha256 of the body last time it was ok
  note         TEXT
) STRICT;
