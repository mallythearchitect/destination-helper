"""Build packs/helper.sqlite: the Destination Helper's capability list as
reference data. Questions with codes, workflows with steps, guardrails with
their "why", methods (setup, defaults, sources, checks, formats), the region
pack template and the region packs, plus the sites the helper sends you to.

    .venv/bin/python packs/build_helper.py

Source: packs/source/destination-helper-<version>-<date>.json, written by
scripts/extract_helper_doc.py from the brief. Per-trip data (track records,
your bookings) lives in the vault, never here.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
from datetime import UTC, datetime

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "helper.sqlite"
SRC = sorted(HERE.glob("source/destination-helper-*.json"))[-1]

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections(code TEXT PRIMARY KEY, label TEXT NOT NULL, ord INTEGER NOT NULL);
CREATE TABLE questions(code TEXT PRIMARY KEY, section TEXT NOT NULL REFERENCES sections(code), text TEXT NOT NULL, new INTEGER NOT NULL DEFAULT 0, ord INTEGER NOT NULL);
CREATE TABLE workflows(code TEXT PRIMARY KEY, title TEXT NOT NULL, runs_when TEXT, steps TEXT NOT NULL, gives TEXT, track_record TEXT, new INTEGER NOT NULL DEFAULT 0, ord INTEGER NOT NULL);
CREATE TABLE guardrails(code TEXT PRIMARY KEY, rule TEXT NOT NULL, why TEXT, ord INTEGER NOT NULL);
CREATE TABLE methods(id INTEGER PRIMARY KEY, grp TEXT NOT NULL, sub TEXT, name TEXT, text TEXT NOT NULL, new INTEGER NOT NULL DEFAULT 0, ord INTEGER NOT NULL);
CREATE TABLE brief(id INTEGER PRIMARY KEY, part TEXT NOT NULL, heading TEXT NOT NULL, lines TEXT NOT NULL, ord INTEGER NOT NULL);
CREATE TABLE region_packs(id TEXT PRIMARY KEY, name TEXT NOT NULL, country_code TEXT, currency TEXT, time_zone TEXT, intro TEXT, sections TEXT NOT NULL, worked_examples TEXT NOT NULL, sites TEXT NOT NULL, channels TEXT NOT NULL);
CREATE TABLE indexes(id TEXT PRIMARY KEY, name TEXT NOT NULL, edition TEXT, used_for TEXT, urls TEXT NOT NULL);
CREATE TABLE services(name TEXT PRIMARY KEY, used_for TEXT, url TEXT);
"""

# The sites the methods name, with a URL each, so the source registry can check them.
SERVICES = [
    ("Expedia", "Flight and hotel search (group size, sorted by price, nonstop; neighborhood, never the airport)", "https://www.expedia.com/"),
    ("Booking.com", "Hotel search and the in-app message to a property", "https://www.booking.com/"),
    ("Booking.com Taxi", "Airport and pier transfers", "https://taxi.booking.com/"),
    ("Google Flights", "Live fares and price tracking", "https://www.google.com/travel/flights"),
    ("Rome2Rio", "Every way between two places on one map", "https://www.rome2rio.com/"),
    ("12Go", "Buses, vans, trains, ferries and taxis in Asia; opens on today's date, so set the date and headcount", "https://12go.asia/en"),
    ("Direct Ferries", "Ferry schedules and the last departure of the day", "https://www.directferries.com/"),
    ("GetYourGuide", "Tours and transfers", "https://www.getyourguide.com/"),
    ("Viator", "Tours", "https://www.viator.com/"),
    ("Klook", "Tours and transfers", "https://www.klook.com/"),
    ("Bookaway", "Ground transport when the main site has nothing", "https://www.bookaway.com/"),
    ("Bounce", "Luggage storage network", "https://usebounce.com/"),
    ("Radical Storage", "Luggage storage network", "https://radicalstorage.com/"),
    ("Tripadvisor", "Reviews: overcharging, theft, noise", "https://www.tripadvisor.com/"),
    ("travel.state.gov", "Entry rules, safety warnings and embassy details for US passports", "https://travel.state.gov/content/travel/en/international-travel.html"),
    ("CDC Travelers' Health", "Vaccines and health rules by country", "https://wwwnc.cdc.gov/travel"),
    ("AAA International Driving Permit", "The permit for driving or riding abroad; get it before flying", "https://www.aaa.com/vacation/idpf.html"),
    ("TradingView", "The exchange rate, looked up that day", "https://www.tradingview.com/"),
    ("Google Maps", "Directions with live traffic; 'leave by' on the day", "https://www.google.com/maps"),
]

# Per region: URL templates the page fills in ({a} {b} = places as slugs, {date} = YYYY-MM-DD, {n} = headcount).
REGION_EXTRA = {
    "Thailand": {"id": "thailand", "country_code": "TH", "currency": "THB", "time_zone": "Asia/Bangkok",
                 "channels": ["whatsapp", "line", "app", "sms", "email", "call"],
                 "sites": [
                     {"name": "12Go route page", "means": "buses, vans, ferries, taxis between two places (set the date and headcount)",
                      "url": "https://12go.asia/en/travel/{a}/{b}?date={date}&people={n}"},
                     {"name": "Thai arrival card (TDAC)", "means": "file no more than 72 hours before landing; free", "url": "https://tdac.immigration.go.th/"},
                     {"name": "AirAsia", "means": "not on Expedia; check its own site", "url": "https://www.airasia.com/"},
                     {"name": "Nok Air", "means": "budget airline, mostly from Don Mueang", "url": "https://www.nokair.com/"},
                     {"name": "Thai Lion Air", "means": "budget airline, mostly from Don Mueang", "url": "https://www.lionairthai.com/"},
                     {"name": "Thai Vietjet", "means": "budget airline; used BKK on the routes checked", "url": "https://www.vietjetair.com/"},
                     {"name": "Rassada Pier", "means": "Phuket ferries; the last boats leave mid-afternoon", "url": "https://rassadapier.net/"},
                     {"name": "Grab", "means": "ride-hail; set up with a card before the trip", "url": "https://www.grab.com/th/en/"},
                     {"name": "Bolt", "means": "ride-hail; set up with a card before the trip", "url": "https://bolt.eu/en-th/"},
                     {"name": "AIRPORTELs", "means": "luggage storage at BKK and DMK, 24 hours", "url": "https://airportels.asia/"},
                 ]},
}


def main() -> int:
    d = json.loads(SRC.read_text())
    if OUT.exists():
        OUT.unlink()
    con = sqlite3.connect(OUT)
    con.executescript(SCHEMA)
    m = d["meta"]
    for k, v in {"built_at": datetime.now(UTC).isoformat(timespec="seconds"), "source_file": SRC.name, "name": "helper",
                 "title": m["title"], "version": m["version"], "updated": m.get("updated_line", ""), "extracted": m["extracted"]}.items():
        con.execute("INSERT INTO meta VALUES(?,?)", (k, v))
    for i, s in enumerate(d["sections"]):
        con.execute("INSERT INTO sections VALUES(?,?,?)", (s["code"], s["label"], i))
    for i, q in enumerate(d["questions"]):
        con.execute("INSERT INTO questions VALUES(?,?,?,?,?)", (q["code"], q["section"], q["text"], int(q["new"]), i))
    for i, w in enumerate(d["workflows"]):
        con.execute("INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?)", (w["code"], w["title"], w["runs_when"], json.dumps(w["steps"]), w["gives"], w["track_record"], int(w["new"]), i))
    for i, g in enumerate(d["guardrails"]):
        con.execute("INSERT INTO guardrails VALUES(?,?,?,?)", (g["code"], g["rule"], g["why"], i))
    n = 0

    def method(grp, text, sub=None, name=None, new=False):
        nonlocal n
        n += 1
        con.execute("INSERT INTO methods(grp, sub, name, text, new, ord) VALUES(?,?,?,?,?,?)", (grp, sub, name, text, int(new), n))
    for t in d["setup"]:
        method("setup", t.removesuffix(" NEW"), new=t.endswith(" NEW"))
    for t in d["defaults"]:
        method("defaults", t)
    for s in d["sources"]:
        method("sources", s["text"], name=s["name"], new=s["new"])
    for grp, items in d["checks"].items():
        for c in items:
            method("checks", c["text"], sub=grp, new=c["new"])
    for t in d["formats"]:
        method("formats", t)
    method("run_order", d["run_order"])
    for t in d["region_template"]:
        method("region_template", t)
    for t in d["changelog"]:
        method("changelog", t)
    k = 0
    for part in ("brief", "market", "how_it_is_built"):
        for b in d[part]:
            k += 1
            con.execute("INSERT INTO brief(part, heading, lines, ord) VALUES(?,?,?,?)", (part, b["heading"], json.dumps(b["lines"]), k))
    for rp in d["region_packs"]:
        x = REGION_EXTRA.get(rp["name"], {})
        con.execute("INSERT INTO region_packs VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (x.get("id", rp["name"].lower()), rp["name"], x.get("country_code"), x.get("currency"), x.get("time_zone"), rp["intro"],
                     json.dumps(rp["sections"]), json.dumps(rp["worked_examples"]), json.dumps(x.get("sites", [])), json.dumps(x.get("channels", ["sms", "email", "call"]))))
    for name, used, url in SERVICES:
        con.execute("INSERT INTO services VALUES(?,?,?)", (name, used, url))
    con.commit()
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("sections", "questions", "workflows", "guardrails", "methods", "brief", "region_packs", "services")}
    print(OUT.name, f"{OUT.stat().st_size // 1024} KB", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
