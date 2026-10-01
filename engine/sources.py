"""Every outside place a figure comes from, with a checker. Sources are
seeded from the packs (their indexes and services) and can be added by
hand; `check` re-fetches each URL and flags what changed or died."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request

from .ids import uuid7
from .store import Store, now_iso


def seed_from_packs(store: Store) -> int:
    """Idempotent: a URL already present is left alone."""
    from . import packs
    added = 0
    with store.tx() as con:
        have = {r[0] for r in con.execute("SELECT url FROM sources")}
        for p in packs.pack_files():
            name = p.stem
            for r in con.execute(f"SELECT id, name, edition, used_for, urls FROM pack_{name}.indexes"):
                for u in json.loads(r["urls"]):
                    if u and u not in have:
                        con.execute("INSERT INTO sources(id, name, url, kind, used_for, first_seen, note) VALUES(?,?,?,?,?,?,?)",
                                    (uuid7(), f"{r['name']} ({r['edition']})" if r["edition"] else r["name"], u, "index", r["used_for"], now_iso(), f"pack {name}"))
                        have.add(u); added += 1
            for r in con.execute(f"SELECT name, used_for, url FROM pack_{name}.services"):
                if r["url"] and r["url"] not in have:
                    con.execute("INSERT INTO sources(id, name, url, kind, used_for, first_seen, note) VALUES(?,?,?,?,?,?,?)",
                                (uuid7(), r["name"], r["url"], "service", r["used_for"], now_iso(), f"pack {name}"))
                    have.add(r["url"]); added += 1
    return added + seed_travel(store)


TRAVEL_SITES = [
    ("Google Maps directions", "https://www.google.com/maps", "Ways to get there: driving and transit directions from home (live)"),
    ("Google Flights", "https://www.google.com/travel/flights", "Ways to get there: live fares"),
    ("Rome2Rio", "https://www.rome2rio.com/", "Ways to get there: every mode with live times and prices"),
    ("Amtrak", "https://www.amtrak.com/", "Ways to get there: US trains"),
    ("OpenStreetMap Nominatim", "https://nominatim.openstreetmap.org/", "Trips: finding the places a way starts and ends, to estimate its distance"),
    ("OSRM road routes", "https://project-osrm.org/", "Trips: road distance and driving time for car, taxi, van and bus legs (OpenStreetMap data)"),
]


def seed_travel(store: Store) -> int:
    added = 0
    with store.tx() as con:
        have = {r[0] for r in con.execute("SELECT url FROM sources")}
        for name, url, used in TRAVEL_SITES:
            if url not in have:
                con.execute("INSERT INTO sources(id, name, url, kind, used_for, first_seen, note) VALUES(?,?,?,?,?,?,?)",
                            (uuid7(), name, url, "service", used, now_iso(), "destinations: ways there"))
                added += 1
    return added


def add(store: Store, name: str, url: str, kind: str = "page", license: str | None = None, used_for: str | None = None) -> dict:
    if not url.startswith(("http://", "https://")):
        raise ValueError("a source needs an http(s) URL")
    with store.tx() as con:
        if con.execute("SELECT 1 FROM sources WHERE url=?", (url,)).fetchone():
            raise ValueError("that URL is already a source")
        sid = uuid7()
        con.execute("INSERT INTO sources(id, name, url, kind, license, used_for, first_seen) VALUES(?,?,?,?,?,?,?)",
                    (sid, name.strip(), url, kind, license, used_for, now_iso()))
    return get(store, sid)


def get(store: Store, sid: str) -> dict:
    with store.read():
        r = store.con.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
    if not r:
        raise LookupError(sid)
    return dict(r)


def all_sources(store: Store) -> list[dict]:
    with store.read():
        return [dict(r) for r in store.con.execute("SELECT * FROM sources ORDER BY kind, name")]


def fetch(url: str, timeout: float = 15.0) -> tuple[int | None, bytes | None, str | None]:
    """Returns (http status, body, error). Real network; tests pass their own fetcher."""
    req = urllib.request.Request(url, headers={"User-Agent": "Destination Helper source checker (personal, low volume)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2_000_000), None
    except urllib.error.HTTPError as e:
        return e.code, None, str(e)
    except Exception as e:  # DNS, timeout, TLS
        return None, None, str(e)[:200]


def check(store: Store, fetcher=fetch, only_ids: list[str] | None = None) -> dict:
    """Re-fetch each source. ok = reachable and same body as last time;
    changed = reachable but different; dead = 404/410 or unreachable."""
    from . import settings
    rule = {"timeout_seconds": 15, "dead_http_codes": [404, 410], **settings.get_value(store, "logic.sources.checker")}
    dead_codes = set(rule["dead_http_codes"])
    rows = [s for s in all_sources(store) if not only_ids or s["id"] in only_ids]
    result = {"checked": 0, "ok": 0, "changed": 0, "dead": 0, "error": 0, "details": []}
    for s in rows:
        status, body, err = fetcher(s["url"], timeout=float(rule["timeout_seconds"]))
        fp = hashlib.sha256(body).hexdigest() if body is not None else None
        if status in dead_codes or (status is None and err):
            new = "dead" if status in dead_codes or status is None else "error"
        elif status and status >= 400:
            new = "error"
        elif s["fingerprint"] and fp and fp != s["fingerprint"]:
            new = "changed"
        else:
            new = "ok"
        with store.tx() as con:
            con.execute("UPDATE sources SET last_checked=?, status=?, http_status=?, fingerprint=COALESCE(?, fingerprint), note=? WHERE id=?",
                        (now_iso(), new, status, fp if new in ("ok", "changed") else None, err if err else s["note"], s["id"]))
        result["checked"] += 1
        result[new] = result.get(new, 0) + 1
        result["details"].append({"id": s["id"], "name": s["name"], "url": s["url"], "status": new, "http_status": status})
    return result
