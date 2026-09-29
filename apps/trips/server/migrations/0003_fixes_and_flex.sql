-- A finding can carry the one-tap fix the page offers ("Move it to 7:15 PM"),
-- and a trip remembers how fixed its dates are (the second onboarding question).
ALTER TABLE trip_findings ADD COLUMN fix_action TEXT;                          -- JSON: {label, action, payload} or {label, ui, ...}
ALTER TABLE trips ADD COLUMN date_flex TEXT NOT NULL DEFAULT 'fixed';          -- fixed | flexible | unsure
