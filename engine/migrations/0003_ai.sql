-- Phase 3: the AI part. Every AI step is logged; suggestions wait in an
-- inbox for the person's OK; test sets score each model on each job.
CREATE TABLE ai_calls (
  id            TEXT PRIMARY KEY,
  ts            TEXT NOT NULL,
  job           TEXT NOT NULL,        -- sort | read | draft | answer
  workflow      TEXT NOT NULL,        -- e.g. trips.draft_message
  model         TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_chars   INTEGER NOT NULL,
  output_chars  INTEGER NOT NULL,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  cost_cents    REAL NOT NULL DEFAULT 0,
  ms            INTEGER NOT NULL,
  ok            INTEGER NOT NULL,
  error         TEXT,
  input_preview TEXT,                 -- first 400 characters of what the model saw
  output_preview TEXT
) STRICT;
CREATE INDEX ai_calls_ts ON ai_calls(ts);

CREATE TABLE ai_suggestions (
  id          TEXT PRIMARY KEY,
  ts          TEXT NOT NULL,
  workflow    TEXT NOT NULL,
  call_id     TEXT REFERENCES ai_calls(id),
  subject     TEXT NOT NULL,          -- what it is about, e.g. a transaction id
  summary     TEXT NOT NULL,          -- one line for the inbox
  action      TEXT NOT NULL,          -- the action to run on approval, e.g. trips.update_item
  payload     TEXT NOT NULL,          -- JSON input for that action
  confidence  REAL,
  why         TEXT,
  status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | superseded
  decided_at  TEXT,
  decided_by  TEXT,
  result      TEXT                    -- JSON result of the action, when approved
) STRICT;
CREATE INDEX ai_suggestions_status ON ai_suggestions(status, ts);

CREATE TABLE ai_examples (
  id        TEXT PRIMARY KEY,
  ts        TEXT NOT NULL,
  test_set  TEXT NOT NULL,            -- e.g. trips.draft_message
  input     TEXT NOT NULL,            -- JSON
  expected  TEXT NOT NULL,            -- JSON: what a correct answer looks like
  source    TEXT NOT NULL             -- approved | corrected | hand
) STRICT;

CREATE TABLE ai_test_runs (
  id        TEXT PRIMARY KEY,
  ts        TEXT NOT NULL,
  test_set  TEXT NOT NULL,
  model     TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  examples  INTEGER NOT NULL,
  correct   INTEGER NOT NULL,
  score     REAL NOT NULL,
  cost_cents REAL NOT NULL DEFAULT 0,
  detail    TEXT
) STRICT;
