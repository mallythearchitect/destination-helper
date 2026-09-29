-- Phase 1, week 1: settings, history (every change kept), backup log.
CREATE TABLE settings (
  key        TEXT PRIMARY KEY,               -- dotted: section.name
  value      TEXT NOT NULL,                  -- JSON
  version    INTEGER NOT NULL DEFAULT 1,     -- optimistic concurrency
  updated_at TEXT NOT NULL,                  -- UTC ISO-8601
  updated_by TEXT NOT NULL DEFAULT 'system'  -- which app changed it
) STRICT;

CREATE TABLE history (
  id        TEXT PRIMARY KEY,   -- UUIDv7, sorts by time
  ts        TEXT NOT NULL,
  app       TEXT NOT NULL,
  action    TEXT NOT NULL,      -- settings.set, settings.reset, history.undo ...
  tbl       TEXT NOT NULL,
  row_key   TEXT NOT NULL,
  before    TEXT,               -- JSON, NULL when the row did not exist
  after     TEXT,               -- JSON, NULL when the row was removed
  undone_by TEXT                -- id of the history row that reversed this one
) STRICT;
CREATE INDEX history_row ON history(tbl, row_key, ts);

CREATE TABLE backup_log (
  id     TEXT PRIMARY KEY,
  ts     TEXT NOT NULL,
  kind   TEXT NOT NULL,         -- backup | restore_test | restore
  file   TEXT,
  ok     INTEGER NOT NULL,
  detail TEXT
) STRICT;
