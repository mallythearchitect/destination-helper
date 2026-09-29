"""The engine's front door: /v1. Apps and AI both come through here."""
from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from .. import backup, history, secrets, settings
from ..store import Store

router = APIRouter(prefix="/v1")


def store_of(request: Request) -> Store:
    return request.app.state.store


@router.get("/health")
def health(request: Request):
    s = store_of(request)
    with s.read():
        n = s.con.execute("SELECT count(*) FROM settings").fetchone()[0]
    return {"ok": True, "vault": str(s.path), "settings_stored": n}


# ---- settings -------------------------------------------------------------

class SettingWrite(BaseModel):
    value: Any
    version: int | None = None   # the version the page last saw; None skips the check
    app: str = "settings"


@router.get("/settings")
def settings_describe(request: Request):
    return settings.describe(store_of(request))


@router.get("/settings/values")
def settings_values(request: Request):
    """Flat key → value, for pages that just want their defaults."""
    return settings.values(store_of(request))


@router.get("/settings/{key}")
def settings_get(key: str, request: Request):
    if key not in settings.BY_KEY:
        raise HTTPException(404, f"no setting {key}")
    d = settings.describe(store_of(request))
    for sec in d["sections"]:
        for s in sec["settings"]:
            if s["key"] == key:
                return s
    raise HTTPException(404, key)


@router.put("/settings/{key}")
def settings_put(key: str, body: SettingWrite, request: Request):
    try:
        return settings.set_value(store_of(request), key, body.value, body.version, app=body.app)
    except KeyError:
        raise HTTPException(404, f"no setting {key}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except settings.Conflict as c:
        raise HTTPException(409, {"message": "someone else saved this setting first",
                                  "yours": c.yours, "theirs": c.theirs})


@router.delete("/settings/{key}")
def settings_reset(key: str, request: Request, app: str = "settings"):
    try:
        return settings.reset(store_of(request), key, app=app)
    except KeyError:
        raise HTTPException(404, f"no setting {key}")


# ---- secrets: the API only ever says whether a key is set ----------------

class SecretWrite(BaseModel):
    value: str


@router.get("/secrets")
def secrets_status():
    return secrets.status()


@router.put("/secrets/{name}")
def secrets_put(name: str, body: SecretWrite):
    try:
        secrets.set_secret(name, body.value)
    except KeyError:
        raise HTTPException(404, f"no secret {name}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"name": name, "set": True}


@router.delete("/secrets/{name}")
def secrets_clear(name: str):
    try:
        secrets.clear_secret(name)
    except KeyError:
        raise HTTPException(404, f"no secret {name}")
    return {"name": name, "set": False}


# ---- history and undo -----------------------------------------------------

@router.get("/history")
def history_recent(request: Request, limit: int = Query(50, ge=1, le=500), tbl: str | None = None):
    return history.recent(store_of(request), limit=limit, tbl=tbl)


@router.get("/history/export")
def history_export(request: Request, format: str = "json", since: str | None = None, until: str | None = None,
                   tbl: str | None = None, key: str | None = None, app: str | None = None):
    """Download history as a file. No filters = all time. Dates are ISO
    (2026-09-01 or 2026-09-01T00:00:00+00:00); `until` is inclusive of that day."""
    if format not in ("json", "csv"):
        raise HTTPException(400, "format must be json or csv")
    if until and len(until) == 10:
        until = until + "T23:59:59+00:00"
    rows = history.export(store_of(request), since=since, until=until, tbl=tbl, row_key=key, app=app)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    label = "all-time" if not (since or until) else f"{(since or '')[:10] or 'start'}_to_{(until or '')[:10] or 'now'}"
    name = f"destination-helper-history-{label}-{stamp}.{format}"
    if format == "json":
        body = json.dumps({"exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "filters": {"since": since, "until": until, "tbl": tbl, "key": key, "app": app},
                           "count": len(rows), "changes": rows}, indent=1)
        media = "application/json"
    else:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "time", "app", "action", "table", "key", "before", "after", "undone_by"])
        for r in rows:
            w.writerow([r["id"], r["ts"], r["app"], r["action"], r["tbl"], r["row_key"],
                        "" if r["before"] is None else json.dumps(r["before"]),
                        "" if r["after"] is None else json.dumps(r["after"]), r["undone_by"] or ""])
        body, media = buf.getvalue(), "text/csv"
    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "X-Row-Count": str(len(rows))})


@router.post("/history/{history_id}/undo")
def history_undo(history_id: str, request: Request, app: str = "settings"):
    try:
        return history.undo(store_of(request), history_id, app=app)
    except history.NotFound:
        raise HTTPException(404, "no such change")
    except history.AlreadyUndone as e:
        raise HTTPException(409, f"already undone by {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---- backups --------------------------------------------------------------

@router.get("/backups")
def backups_list(request: Request):
    s = store_of(request)
    return {"backups": backup.list_backups(s), "log": backup.log(s),
            "destination": str(backup.destination(s)), "next_run": backup.next_run(s)}


@router.post("/backups")
def backups_make(request: Request, note: str = "manual"):
    return backup.make_backup(store_of(request), note=note)


@router.post("/backups/restore-test")
def backups_restore_test(request: Request, file: str | None = None):
    return backup.restore_test(store_of(request), file=file)


class RestoreBody(BaseModel):
    file: str
    confirm: bool = False


@router.post("/backups/restore")
def backups_restore(body: RestoreBody, request: Request):
    if not body.confirm:
        raise HTTPException(400, "restore replaces the live vault; send confirm=true")
    try:
        return backup.restore(store_of(request), body.file)
    except FileNotFoundError:
        raise HTTPException(404, "no such backup")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---- records: entities, links, tags, notes, files, search -----------------------

from typing import Annotated  # noqa: E402

from fastapi import File, Form, UploadFile  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from .. import records  # noqa: E402


def _rec(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except records.NotFound as e:
        raise HTTPException(404, f"not found: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))  # noqa: E501
    except records.Conflict as c:
        raise HTTPException(409, {"message": "someone else saved this record first", "yours": c.yours, "theirs": c.theirs})  # noqa: E501


class EntityIn(BaseModel):
    type: str
    name: str
    data: dict = {}
    external_ids: dict = {}
    source: str | None = None
    app: str = "browse"


class EntityPatch(BaseModel):
    type: str | None = None
    name: str | None = None
    data: dict | None = None
    external_ids: dict | None = None
    source: str | None = None
    version: int | None = None
    app: str = "browse"


@router.get("/types")
def types(request: Request):
    rel = records.relations(store_of(request))
    return {"types": records.types_with_counts(store_of(request)), "rels": list(rel), "relations": rel,
            "tags": records.all_tags(store_of(request))}


@router.get("/search")
def search(request: Request, q: str = "", type: str | None = None, tag: str | None = None,
           limit: int = Query(50, ge=1, le=500), deleted: bool = False):
    return records.search(store_of(request), q=q, type=type, tag=tag, limit=limit, include_deleted=deleted)


@router.get("/entities")
def entities_list(request: Request, q: str = "", type: str | None = None, tag: str | None = None,
                  limit: int = Query(50, ge=1, le=500)):
    return records.search(store_of(request), q=q, type=type, tag=tag, limit=limit)


@router.post("/entities", status_code=201)
def entities_create(body: EntityIn, request: Request):
    return _rec(records.create_entity, store_of(request), type=body.type, name=body.name, data=body.data,
                external_ids=body.external_ids, source=body.source, app=body.app)


@router.get("/entities/{eid}")
def entities_get(eid: str, request: Request):
    return _rec(records.get_entity, store_of(request), eid)


@router.put("/entities/{eid}")
def entities_update(eid: str, body: EntityPatch, request: Request):
    patch = {k: v for k, v in body.model_dump().items() if k not in ("version", "app") and v is not None}
    return _rec(records.update_entity, store_of(request), eid, patch, body.version, app=body.app)


@router.delete("/entities/{eid}")
def entities_delete(eid: str, request: Request, app: str = "browse"):
    return _rec(records.delete_entity, store_of(request), eid, app=app)


class LinkIn(BaseModel):
    to_id: str
    rel: str = "related"
    note: str | None = None
    app: str = "browse"


@router.post("/entities/{eid}/links", status_code=201)
def links_create(eid: str, body: LinkIn, request: Request):
    return _rec(records.link, store_of(request), eid, body.to_id, body.rel, body.note, app=body.app)


@router.delete("/links/{lid}")
def links_delete(lid: str, request: Request, app: str = "browse"):
    return _rec(records.unlink, store_of(request), lid, app=app)


class TagIn(BaseModel):
    tag: str
    app: str = "browse"


@router.post("/entities/{eid}/tags")
def tags_add(eid: str, body: TagIn, request: Request):
    return {"tags": _rec(records.tag, store_of(request), eid, body.tag, app=body.app)}


@router.delete("/entities/{eid}/tags/{tag}")
def tags_remove(eid: str, tag: str, request: Request, app: str = "browse"):
    return {"tags": _rec(records.untag, store_of(request), eid, tag, app=app)}


class NoteIn(BaseModel):
    body: str
    app: str = "browse"


@router.post("/entities/{eid}/notes", status_code=201)
def notes_add(eid: str, body: NoteIn, request: Request):
    return _rec(records.add_note, store_of(request), eid, body.body, app=body.app)


@router.delete("/notes/{nid}")
def notes_delete(nid: str, request: Request, app: str = "browse"):
    return _rec(records.delete_note, store_of(request), nid, app=app)


@router.post("/entities/{eid}/files", status_code=201)
async def files_attach(eid: str, request: Request, file: Annotated[UploadFile, File()],
                       app: Annotated[str, Form()] = "browse"):
    content = await file.read()
    max_mb = settings.get_value(store_of(request), "logic.limits").get("attachment_max_mb", 50)
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"files over {max_mb} MB are not stored in the vault")
    return _rec(records.attach_file, store_of(request), eid, file.filename or "file",
                file.content_type or "application/octet-stream", content, app=app)


@router.get("/files/{fid}")
def files_get(fid: str, request: Request):
    meta, path = _rec(records.get_file, store_of(request), fid)
    return FileResponse(path, media_type=meta["media_type"], filename=meta["name"])


@router.delete("/files/{fid}")
def files_delete(fid: str, request: Request, app: str = "browse"):
    return _rec(records.delete_file, store_of(request), fid, app=app)


# ---- actions: what apps can do, one endpoint for all of them ----------------------

from .. import actions  # noqa: E402


@router.get("/actions")
def actions_list():
    return actions.describe()


@router.post("/actions/{name}")
def actions_run(name: str, request: Request, payload: dict | None = None):
    payload = dict(payload or {})
    app = payload.pop("app", None) or name.split(".")[0]
    try:
        return actions.run(store_of(request), name, payload, app)
    except KeyError:
        raise HTTPException(404, f"no action {name}")
    except (records.NotFound, LookupError) as e:
        raise HTTPException(404, f"not found: {e}")
    except records.Conflict as c:
        raise HTTPException(409, {"message": "someone else saved this first", "yours": c.yours, "theirs": c.theirs})
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:   # the AI switchboard refused, or a provider failed
        raise HTTPException(409, str(e))
    except Exception as e:  # pydantic validation
        if e.__class__.__name__ == "ValidationError":
            raise HTTPException(400, str(e).split("\n")[0] + ": " + "; ".join(
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()))
        raise


# ---- the AI part: status, inbox, calls, tests -------------------------------------

from ..ai import inbox, switchboard  # noqa: E402
from ..ai import tests as ai_tests  # noqa: E402


@router.get("/ai/status")
def ai_status(request: Request):
    s = store_of(request)
    return {**switchboard.status(s), "pending": len(inbox.pending(s)),
            "workflows": [a for a in actions.describe() if a["name"].startswith("ai.")]}


@router.get("/ai/inbox")
def ai_inbox(request: Request, all: bool = False, limit: int = Query(100, ge=1, le=500)):
    s = store_of(request)
    return inbox.recent(s, limit) if all else inbox.pending(s, limit=limit)


class Decide(BaseModel):
    payload: dict | None = None    # corrections to the suggested input, e.g. a different category


@router.post("/ai/inbox/{sid}/approve")
def ai_approve(sid: str, request: Request, body: Decide | None = None):
    try:
        return inbox.approve(store_of(request), sid, payload_override=(body.payload if body else None))
    except LookupError:
        raise HTTPException(404, "no such suggestion")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/ai/inbox/{sid}/reject")
def ai_reject(sid: str, request: Request):
    try:
        return inbox.reject(store_of(request), sid)
    except LookupError:
        raise HTTPException(404, "no such suggestion")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/ai/inbox/approve-all")
def ai_approve_all(request: Request, workflow: str | None = None, min_confidence: float | None = None):
    s = store_of(request)
    if min_confidence is None:
        min_confidence = 0.0
    done, failed = [], []
    for sug in inbox.pending(s, workflow):
        if (sug["confidence"] or 0) < min_confidence:
            continue
        try:
            done.append(inbox.approve(s, sug["id"])["id"])
        except Exception as e:
            failed.append({"id": sug["id"], "error": str(e)})
    return {"approved": len(done), "failed": failed}


@router.get("/ai/calls")
def ai_calls(request: Request, limit: int = Query(50, ge=1, le=500)):
    return switchboard.recent_calls(store_of(request), limit)


@router.get("/ai/tests")
def ai_test_runs(request: Request, test_set: str | None = None):
    s = store_of(request)
    return {"runs": ai_tests.runs(s, test_set), "examples": len(ai_tests.examples(s, test_set or "trips"))}  # noqa: E501


# ---- packs and the source registry ----------------------------------------------

from .. import packs, sources  # noqa: E402


@router.get("/packs")
def packs_list(request: Request):
    s = store_of(request)
    with s.read():
        return packs.describe(s.con)


@router.get("/sources")
def sources_list(request: Request):
    return sources.all_sources(store_of(request))


class SourceIn(BaseModel):
    name: str
    url: str
    kind: str = "page"
    license: str | None = None
    used_for: str | None = None


@router.post("/sources", status_code=201)
def sources_add(body: SourceIn, request: Request):
    try:
        return sources.add(store_of(request), body.name, body.url, body.kind, body.license, body.used_for)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---- tracking, analytics, prediction, workflows ---------------------------------

from .. import analytics, predict, tracking, workflows  # noqa: E402


@router.get("/track/metrics")
def track_metrics(request: Request, app: str | None = None):
    return tracking.metrics(store_of(request), app)


@router.get("/track/series")
def track_series(request: Request, metric: str, subject: str = "all", since: str | None = None, until: str | None = None,
                 predicted: bool = False):
    return {"metric": metric, "subject": subject, "points": tracking.series(store_of(request), metric, subject, since, until, predicted),
            "subjects": tracking.subjects(store_of(request), metric)}


@router.get("/analytics/summary")
def analytics_summary(request: Request, metric: str, subject: str = "all", since: str | None = None, until: str | None = None,
                      step: str = "day", how: str = "last"):
    return analytics.summary(store_of(request), metric, subject, since, until, step, how)


@router.get("/analytics/compare")
def analytics_compare(request: Request, metric: str, subjects: str, since: str | None = None, until: str | None = None,
                      step: str = "day", how: str = "last"):
    return analytics.compare(store_of(request), metric, [s for s in subjects.split(",") if s], since, until, step, how)


@router.get("/predict/series")
def predict_series(request: Request, metric: str, subject: str = "all", days: int = 30):
    return {"metric": metric, "subject": subject, "history": tracking.series(store_of(request), metric, subject)[-90:],
            **predict.forecast_series(tracking.series(store_of(request), metric, subject), days)}


@router.get("/predict/score")
def predict_score(request: Request, metric: str, subject: str = "all"):
    return predict.score(store_of(request), metric, subject)


@router.get("/workflows")
def workflows_list(request: Request):
    return {"workflows": workflows.describe(store_of(request)), "runs": workflows.runs(store_of(request), limit=30)}


@router.post("/workflows/{name}/run")
def workflows_run(name: str, request: Request):
    try:
        return workflows.run(store_of(request), name, trigger="you")
    except KeyError:
        raise HTTPException(404, f"no workflow {name}")
