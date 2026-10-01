-- Road distances instead of straight lines. When a way is saved, its places are
-- looked up (OpenStreetMap Nominatim, else GeoNames) and road legs get a real
-- road route (OSRM, on OpenStreetMap data). The result is stored on the way, so
-- reading a plan never waits on the network, and both lookups are cached.
ALTER TABLE trip_options ADD COLUMN est_distance_miles REAL;
ALTER TABLE trip_options ADD COLUMN est_minutes REAL;        -- road travel time, when a road route gave one
ALTER TABLE trip_options ADD COLUMN est_source TEXT;
ALTER TABLE trip_options ADD COLUMN est_at TEXT;

CREATE TABLE trip_geocache (
  query      TEXT PRIMARY KEY,                 -- the place as typed, lower-case
  lat        REAL,                             -- NULL = looked up, nothing found
  lon        REAL,
  label      TEXT,
  source     TEXT NOT NULL,                    -- nominatim | geonames
  fetched_at TEXT NOT NULL
) STRICT;

CREATE TABLE trip_route_cache (
  key        TEXT PRIMARY KEY,                 -- profile + both ends rounded to ~100 m
  miles      REAL,
  minutes    REAL,
  source     TEXT NOT NULL,
  fetched_at TEXT NOT NULL
) STRICT;
