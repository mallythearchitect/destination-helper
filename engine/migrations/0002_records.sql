-- Phase 1, weeks 2–3: one record per thing, links between things, tags,
-- notes, files, and full-text search. Deletes are soft (deleted_at), so
-- every one of them can be undone from history.
CREATE TABLE entities (
  id           TEXT PRIMARY KEY,               -- UUIDv7
  type         TEXT NOT NULL,                  -- person | company | place | bill | ...
  name         TEXT NOT NULL,
  data         TEXT NOT NULL DEFAULT '{}',     -- JSON: the app's details for this thing
  external_ids TEXT NOT NULL DEFAULT '{}',     -- JSON: ids the world already uses (SEC CIK, ISO code, GEOID, Wikidata)
  source       TEXT,                           -- where it came from: a URL or an app name
  version      INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  updated_by   TEXT NOT NULL,
  deleted_at   TEXT
) STRICT;
CREATE INDEX entities_type_name ON entities(type, name);
CREATE INDEX entities_updated ON entities(updated_at);

CREATE TABLE links (
  id         TEXT PRIMARY KEY,
  from_id    TEXT NOT NULL REFERENCES entities(id),
  to_id      TEXT NOT NULL REFERENCES entities(id),
  rel        TEXT NOT NULL,                    -- about | for | part_of | related | ...
  note       TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  deleted_at TEXT
) STRICT;
CREATE INDEX links_from ON links(from_id);
CREATE INDEX links_to ON links(to_id);

CREATE TABLE tags (
  entity_id TEXT NOT NULL REFERENCES entities(id),
  tag       TEXT NOT NULL,
  PRIMARY KEY (entity_id, tag)
) STRICT;

CREATE TABLE notes (
  id         TEXT PRIMARY KEY,
  entity_id  TEXT NOT NULL REFERENCES entities(id),
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  deleted_at TEXT
) STRICT;
CREATE INDEX notes_entity ON notes(entity_id);

CREATE TABLE files (
  id         TEXT PRIMARY KEY,
  entity_id  TEXT REFERENCES entities(id),
  name       TEXT NOT NULL,
  media_type TEXT NOT NULL,
  bytes      INTEGER NOT NULL,
  sha256     TEXT NOT NULL,                    -- the bytes live in vault/files/<sha256>
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  deleted_at TEXT
) STRICT;
CREATE INDEX files_entity ON files(entity_id);

-- Full-text search over name, details, tags and notes. Rebuilt per record
-- after every change (engine/records.py: reindex).
CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, type UNINDEXED, name, text, tokenize='unicode61');
