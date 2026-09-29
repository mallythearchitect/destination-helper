"""What Destinations can do: keep your own list. A place you mark or note
becomes a record (type place) carrying the pack id, so it gets notes, tags,
files, links and history like everything else."""
from __future__ import annotations

from pydantic import BaseModel, Field

from engine import records
from engine.actions import action
from engine.store import Store

from .queries import STATUSES


def ensure_record(store: Store, pid: str, app: str) -> dict:
    with store.tx() as con:
        r = con.execute("SELECT id FROM entities WHERE type='place' AND deleted_at IS NULL AND json_extract(external_ids,'$.pack_place')=?", (pid,)).fetchone()
        if r:
            return records.get_entity(store, r["id"])
        p = con.execute("SELECT name, region, country, lat, lon, kind FROM pack_destinations.places WHERE id=?", (pid,)).fetchone()
        if not p:
            raise records.NotFound(pid)
        name = f"{p['name']}, {p['region']}" if p["region"] and p["kind"] != "leisure" else p["name"]
        e = records.create_entity(store, type="place", name=name, data={"lat": p["lat"], "lon": p["lon"], "kind": p["kind"]},
                                  external_ids={"pack_place": pid}, source="pack: destinations", app=app)
        return records.get_entity(store, e["id"])


class SetStatus(BaseModel):
    place_id: str = Field(description="The pack id, e.g. us-boston-ma")
    status: str | None = Field(None, description="shortlist, want, base, visited, or null to clear")


@action("destinations.set_status", "Mark a place: shortlist, want to go, base candidate, visited, or clear it.", SetStatus)
def set_status(store: Store, i: SetStatus, app: str = "destinations") -> dict:
    if i.status is not None and i.status not in dict(STATUSES):
        raise ValueError(f"status must be one of {[s[0] for s in STATUSES]}")
    e = ensure_record(store, i.place_id, app)
    data = {**e["data"]}
    if i.status:
        data["status"] = i.status
    else:
        data.pop("status", None)
    return records.update_entity(store, e["id"], {"data": data}, None, app=app)


class AddNote(BaseModel):
    place_id: str
    body: str


@action("destinations.add_note", "Add a note to a place (it becomes a record if it isn't one yet).", AddNote)
def add_note(store: Store, i: AddNote, app: str = "destinations") -> dict:
    e = ensure_record(store, i.place_id, app)
    return records.add_note(store, e["id"], i.body, app=app)
