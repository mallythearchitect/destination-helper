"""Where a place is, and how far it is by road.

Places are looked up with OpenStreetMap's Nominatim (when the source is on in
Settings → Data), falling back to the GeoNames cities in the reference pack.
Road legs get a real road route from OSRM, on OpenStreetMap data. Both are
cached in the vault and called only when a way is saved, never when a page
reads a plan. Nominatim is held to one request a second, as its usage policy
asks; both requests name the app. Turn either off in Settings → Data, or road
routing as a whole in Settings → Logic → Trips · comparing ways to do a leg."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from engine import settings
from engine.store import Store, now_iso

UA = "DestinationHelper/0.1 (+https://github.com/mallythearchitect/destination-helper)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving"
_lock = threading.Lock()
_last_nominatim = 0.0


def _http_get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts
        return json.loads(r.read().decode("utf-8"))


HTTP = _http_get_json   # tests replace this; it must raise OSError (or return None) when offline


def source_on(store: Store, sid: str) -> bool:
    try:
        rows = settings.get_value(store, "data.sources")
    except Exception:
        return True
    row = next((r for r in rows if r.get("id") == sid), None)
    return True if row is None else bool(row.get("on"))


def _fresh(ts: str, days: int) -> bool:
    try:
        return datetime.fromisoformat(ts) > datetime.now(UTC) - timedelta(days=days)
    except ValueError:
        return False


TOWNISH = re.compile(r"\s*\([^)]*\)|\b(town|city|centre|center|downtown|old town)\b", re.I)


def _queries(place: str) -> list[str]:
    """The place as typed, then a plainer version ('Rassada Pier, Phuket Town' → 'Rassada Pier, Phuket';
    'Don Mueang Airport (DMK), Bangkok' → 'Don Mueang Airport, Bangkok')."""
    plain = ", ".join(x for x in (" ".join(TOWNISH.sub(" ", part).split()) for part in place.split(",")) if x)
    return [place] + ([plain] if plain and plain.lower() != place.lower() else [])


def geocode(store: Store, place: str | None, R: dict, online: bool = True) -> dict | None:
    """{lat, lon, label, source} for a place as typed, or None."""
    if not place or not place.strip():
        return None
    key = " ".join(place.lower().split())
    days = int(R.get("cache_days", 90))
    with store.read():
        hit = store.con.execute("SELECT * FROM trip_geocache WHERE query=?", (key,)).fetchone()
    if hit and _fresh(hit["fetched_at"], days):
        return None if hit["lat"] is None else {"lat": hit["lat"], "lon": hit["lon"], "label": hit["label"], "source": hit["source"]}
    found, src, keep = None, None, True
    if online and R.get("road_routing", True) and source_on(store, "nominatim"):
        global _last_nominatim
        try:
            for qtext in _queries(place):
                with _lock:
                    wait = 1.1 - (time.monotonic() - _last_nominatim)
                    if wait > 0:
                        time.sleep(wait)
                    _last_nominatim = time.monotonic()
                res = HTTP(f"{NOMINATIM}?format=jsonv2&limit=1&q={urllib.parse.quote(qtext)}")
                if res:
                    found = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"]), "label": (res[0].get("display_name") or place)[:160]}
                    src = "nominatim"
                    break
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            keep = False                     # offline or a bad reply: use the fallback now, ask again next time
    if not found:
        from . import routes
        g = routes.locate(store, place)
        if g:
            found, src = {"lat": g["lat"], "lon": g["lon"], "label": f"{g['name']}, {g.get('country') or ''}".strip(", ")}, "geonames"
        else:
            src = src or "none"
    if keep:
        with store.tx() as con:
            con.execute("INSERT OR REPLACE INTO trip_geocache(query, lat, lon, label, source, fetched_at) VALUES(?,?,?,?,?,?)",
                        (key, found["lat"] if found else None, found["lon"] if found else None, found["label"] if found else None, src, now_iso()))
    return {**found, "source": src} if found else None


def road(store: Store, a: dict, b: dict, R: dict, online: bool = True) -> dict | None:
    """{miles, minutes, source} by road between two points, or None."""
    key = f"driving:{a['lat']:.3f},{a['lon']:.3f}:{b['lat']:.3f},{b['lon']:.3f}"
    days = int(R.get("cache_days", 90))
    with store.read():
        hit = store.con.execute("SELECT * FROM trip_route_cache WHERE key=?", (key,)).fetchone()
    if hit and _fresh(hit["fetched_at"], days):
        return None if hit["miles"] is None else {"miles": hit["miles"], "minutes": hit["minutes"], "source": hit["source"]}
    if not (online and R.get("road_routing", True) and source_on(store, "osrm")):
        return None
    try:
        res = HTTP(f"{OSRM}/{a['lon']:.6f},{a['lat']:.6f};{b['lon']:.6f},{b['lat']:.6f}?overview=false")
    except (OSError, ValueError, TypeError):
        return None
    out = None
    if res and res.get("code") == "Ok" and res.get("routes"):
        r = res["routes"][0]
        out = {"miles": round(r["distance"] / 1609.344, 1), "minutes": round(r["duration"] / 60, 1), "source": "road route, OSRM on OpenStreetMap"}
    elif not res or res.get("code") not in ("NoRoute", "NoSegment"):
        return None                          # a hiccup, not an answer: don't cache it
    with store.tx() as con:
        con.execute("INSERT OR REPLACE INTO trip_route_cache(key, miles, minutes, source, fetched_at) VALUES(?,?,?,?,?)",
                    (key, out["miles"] if out else None, out["minutes"] if out else None, out["source"] if out else "osrm: no road", now_iso()))
    return out
