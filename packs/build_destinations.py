#!/usr/bin/env python3
"""Build packs/destinations.sqlite, the read-only reference pack for the
Destinations app, from the data the old page carried (packs/source/*.json).

Every figure keeps where it came from: a dataset (with origin and method),
and for index-derived scores, which published index and edition. Hand-set
scores are marked hand-set. Rebuild any time; the vault never holds this.

    .venv/bin/python packs/build_destinations.py
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from datetime import UTC, datetime

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "source" / "destinations-old-page-2026-09-28.json"
OUT = HERE / "destinations.sqlite"

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE datasets(id TEXT PRIMARY KEY, name TEXT NOT NULL, what TEXT, origin TEXT, method TEXT, trust TEXT, confidence TEXT NOT NULL);
CREATE TABLE indexes(id TEXT PRIMARY KEY, name TEXT NOT NULL, edition TEXT, used_for TEXT, urls TEXT NOT NULL);
CREATE TABLE services(name TEXT PRIMARY KEY, used_for TEXT, url TEXT);
CREATE TABLE places(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, region TEXT, country TEXT, country_code TEXT, group_name TEXT,
  lat REAL, lon REAL, hub TEXT, tier TEXT, cost_per_day INTEGER, description TEXT, tags TEXT NOT NULL DEFAULT '[]',
  corridor INTEGER, road INTEGER, rating REAL, rating_count INTEGER, dataset_id TEXT NOT NULL REFERENCES datasets(id),
  population INTEGER, timezone TEXT, feature TEXT);
CREATE INDEX places_pop ON places(population);
CREATE INDEX places_name ON places(name);
CREATE INDEX places_kind ON places(kind);
CREATE TABLE scores(place_id TEXT NOT NULL REFERENCES places(id), domain TEXT NOT NULL, value REAL NOT NULL,
  confidence TEXT NOT NULL, from_indexes TEXT NOT NULL DEFAULT '[]', PRIMARY KEY(place_id, domain));
CREATE TABLE index_values(place_id TEXT NOT NULL REFERENCES places(id), index_id TEXT NOT NULL, value REAL, PRIMARY KEY(place_id, index_id));
CREATE TABLE method(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE goal_weights(goal TEXT NOT NULL, domain TEXT NOT NULL, weight REAL NOT NULL, PRIMARY KEY(goal, domain));
"""

INDEX_IDS = {"Kearney Global Cities Index (GCI)": "gci", "Kearney Global Cities Outlook (GCO)": "gco",
             "Global Financial Centres Index (GFCI)": "gfci", "Startup Genome GSER": "gser", "StartupBlink": "blink",
             "Numbeo Quality of Life": "qol", "EIU Global Liveability": "eiu"}


def slug(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main() -> int:
    d = json.loads(SRC.read_text())
    if OUT.exists():
        OUT.unlink()
    con = sqlite3.connect(OUT)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES('built_at', ?)", (datetime.now(UTC).isoformat(timespec="seconds"),))
    con.execute("INSERT INTO meta VALUES('source_file', ?)", (SRC.name,))
    con.execute("INSERT INTO meta VALUES('name', 'destinations')")
    # What the words mean, in plain language: shown on the Sources tab.
    con.execute("INSERT INTO method VALUES('classification', ?)", (json.dumps({
        "business_city": "A place scored for working and building: the job market, starting a company, the tech sector, the network, and life there. Five domain scores 0–100. US ones were set by hand; international ones are computed from published indexes.",
        "leisure": "A place for time off. Scored only for value for money: a tier from S (outstanding value) to D, and a typical daily cost. Both hand-set.",
        "world_city": "Every city of 15,000 people or more, from GeoNames (CC BY 4.0). Name, country, coordinates, population, time zone. No scores unless it is also a business city; here so the map is the whole world, not just the major stuff.",
        "us_place": "US towns and cities with coordinates, kept for distances and the map; no scores.",
        "tier_business": "core = a place already central to the plan; expansion = a strong next step; watch = worth tracking.",
        "tier_leisure": "S, A, B, C, D by value for money at the luxury end: what 5-star stays, private tours and top dining cost there against what they cost at home.",
        "extra_domains": "Safety, Affordability and Quality of life are computed from Numbeo indexes where a city is covered (index-derived); blank otherwise.",
    }),))
    con.execute("INSERT INTO method VALUES('cost_per_day', ?)", (json.dumps({
        "means": "A typical day for one person, in US dollars: somewhere modest to stay, three meals, getting around locally, and a little extra. It is a single hand-set figure per place.",
        "split": [["lodging", 0.45, "a modest room or apartment, per night, one person"], ["food", 0.30, "three meals, mostly local"],
                  ["transport", 0.10, "getting around locally"], ["other", 0.15, "entry fees, a drink, small purchases"]],
        "split_note": "The split is an estimate applied to every place the same way, so 'no housing needed' takes off 45%. Correct a place's split when you know it.",
    }),))
    con.execute("INSERT INTO datasets VALUES('geonames-cities15000', 'World cities, 15,000+ people (GeoNames)', 'Name, country, region, coordinates, population, time zone for every city of 15,000+ people', "
                "'GeoNames cities15000 dump, downloaded 2026-09-28 (https://download.geonames.org/export/dump/), CC BY 4.0', "
                "'As published; only cities with a population figure are kept.', 'GeoNames data is crowd-edited; populations can lag a census by years.', 'verified')")
    con.execute("INSERT INTO meta VALUES('description', 'US and international business cities, leisure destinations, US places: scores, costs, coordinates, and where each figure came from.')")

    trust = {"US business cities (30)": "hand-set", "US business cities: cost/day": "estimate", "International business cities (35)": "index-derived",
             "Leisure destinations (119)": "hand-set", "Leisure hub cities": "verified", "US places (190)": "verified", "Your saved list": "you"}
    ds_ids = {}
    for x in d["DATASETS"]:
        if x["name"] == "Your saved list":
            continue     # personal: lives in the vault as records, not in a pack
        did = slug(x["name"])
        ds_ids[x["name"]] = did
        con.execute("INSERT INTO datasets VALUES(?,?,?,?,?,?,?)", (did, x["name"], x.get("what"), x.get("origin"), x.get("method"), x.get("trust"), trust.get(x["name"], "hand-set")))
    for x in d["INDEX_META"]:
        iid = next((v for k, v in INDEX_IDS.items() if k.split(" (")[0].lower() in x["name"].lower() or v in x["name"].lower()), slug(x["name"])[:12])
        con.execute("INSERT INTO indexes VALUES(?,?,?,?,?)", (iid, x["name"], x.get("edition"), x.get("used"), json.dumps(x.get("urls", []))))
    for name, used, url in d["SERVICES"]:
        con.execute("INSERT INTO services VALUES(?,?,?)", (name, used, url))
    for k, v in d["METHOD"].items():
        con.execute("INSERT INTO method VALUES(?,?)", (k, json.dumps(v)))
    for goal, w in d["GOAL_WEIGHTS"].items():
        for dom, wt in w.items():
            con.execute("INSERT INTO goal_weights VALUES(?,?,?)", (goal, dom, wt))

    coords = {(p[0], p[1]): (p[2], p[3]) for p in d["PLACES_RAW"]}
    ALIAS = {"New York City": "New York"}     # the cities list and the places list spell a few names differently
    n = 0
    for c in d["CITIES"]:
        pid = "us-" + slug(f"{c['name']}-{c['state']}")
        lat, lon = coords.get((ALIAS.get(c["name"], c["name"]), c["state"]), (None, None))
        con.execute("INSERT INTO places VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                    (pid, "us_city", c["name"], c["state"], "United States", "US", c.get("region"), lat, lon, None, c.get("tier"),
                     c.get("cost"), c.get("description"), json.dumps(c.get("tags", [])), int(bool(c.get("corridor"))), None,
                     c.get("rating"), c.get("rating_count"), ds_ids["US business cities (30)"]))
        for dom, val in (c.get("scores") or {}).items():
            con.execute("INSERT INTO scores VALUES(?,?,?,?,?)", (pid, dom, val, "hand-set", "[]"))
        for iid, val in (d["INDEX"].get(c["name"]) or {}).items():
            if val is not None and iid in ("gci", "gco", "gfci", "gser", "blink", "qol", "safety", "pollution", "eiu", "col", "rent", "colr"):
                con.execute("INSERT INTO index_values VALUES(?,?,?)", (pid, iid, val))
        n += 1
    for c in d["INTL_CITIES"]:
        pid = "intl-" + slug(f"{c['name']}-{c['cc']}")
        con.execute("INSERT INTO places VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                    (pid, "intl_city", c["name"], c.get("country"), c.get("country"), c.get("cc"), c.get("group"), c.get("lat"), c.get("lon"),
                     None, c.get("tier"), c.get("cost"), c.get("description"), json.dumps(c.get("tags", [])), None, int(bool(c.get("road"))),
                     None, None, ds_ids["International business cities (35)"]))
        used = c.get("used") or {}
        for dom, val in (c.get("scores") or {}).items():
            src = used.get(dom) or []
            con.execute("INSERT INTO scores VALUES(?,?,?,?,?)", (pid, dom, val, "index-derived" if src else "hand-set", json.dumps(src)))
        for iid, val in (d["INDEX"].get(c["name"]) or {}).items():
            if val is not None and iid in ("gci", "gco", "gfci", "gser", "blink", "qol", "safety", "pollution", "eiu", "col", "rent", "colr"):
                con.execute("INSERT INTO index_values VALUES(?,?,?)", (pid, iid, val))
        n += 1
    # Safety, affordability and quality of life are NOT baked in: the engine computes them at read
    # time from index_values by the rule in Settings → Logic (logic.destinations.extra_domains), so
    # the rule can be edited. The goal weights below are the documented origin of that setting's default.
    for goal, w in {"affordable": {"affordability": 3, "lifestyle": 1, "career": 1}, "safe_and_calm": {"safety": 3, "quality_of_life": 2, "lifestyle": 1},
                    "balanced": {"career": 1, "entrepreneurship": 1, "tech": 1, "network": 1, "lifestyle": 1, "safety": 1, "affordability": 1, "quality_of_life": 1}}.items():
        for dom, wt in w.items():
            con.execute("INSERT OR REPLACE INTO goal_weights VALUES(?,?,?)", (goal, dom, wt))
    for c in d["DESTINATIONS"]:
        pid = "leisure-" + slug(c["destination"])
        g = d["GEO"].get(c["destination"]) or {}
        con.execute("INSERT INTO places VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                    (pid, "leisure", c["destination"], c.get("continent"), None, None, c.get("continent"), g.get("lat"), g.get("lon"), g.get("hub"),
                     c.get("tier"), c.get("cost"), c.get("why"), "[]", None, None, None, None, ds_ids["Leisure destinations (119)"]))
        n += 1
    for name, state, lat, lon in d["PLACES_RAW"]:
        pid = "place-" + slug(f"{name}-{state}")
        if con.execute("SELECT 1 FROM places WHERE id=?", (pid,)).fetchone():
            continue
        con.execute("INSERT INTO places VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
                    (pid, "us_place", name, state, "United States", "US", None, lat, lon, None, None, None, None, "[]", None, None, None, None,
                     ds_ids["US places (190)"]))
        n += 1
    # ---- GeoNames world cities: the whole world, not just the major stuff
    import io
    import zipfile
    countries = {}
    ci = HERE / "source" / "geonames-countryInfo-2026-09-28.txt"
    if ci.exists():
        for line in ci.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            f = line.split("\t")
            countries[f[0]] = f[4]
    zp = HERE / "source" / "geonames-cities15000-2026-09-28.zip"
    if zp.exists():
        z = zipfile.ZipFile(zp)
        txt = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")
        seen = {r[0] for r in con.execute("SELECT id FROM places")}
        for line in txt:
            f = line.rstrip("\n").split("\t")
            if len(f) < 18:
                continue
            gid, name, cc, admin1, lat, lon, pop, tz, fcode = f[0], f[1], f[8], f[10], float(f[4]), float(f[5]), int(f[14] or 0), f[17], f[7]
            if pop <= 0:
                continue
            pid = "geo-" + gid
            if pid in seen:
                continue
            con.execute("INSERT INTO places VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (pid, "world_city", name, admin1 if cc != "US" else admin1, countries.get(cc, cc), cc, None, lat, lon, None, None, None,
                         None, "[]", None, None, None, None, "geonames-cities15000", pop, tz, fcode))
            n += 1
    con.commit()
    counts = {k: v for k, v in con.execute("SELECT kind, count(*) FROM places GROUP BY kind")}
    con.close()
    print(f"built {OUT.name}: {n} places {counts}, {len(d['INDEX_META'])} indexes, {len(d['DATASETS'])} datasets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
