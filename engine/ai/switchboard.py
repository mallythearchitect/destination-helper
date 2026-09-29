"""One place decides which model does a job, whether it may see the data,
whether the month's cap allows it, and logs what happened. Apps and
workflows never name a provider; they ask for a job."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from .. import settings
from ..ids import uuid7
from ..store import Store, now_iso
from . import prompts, providers


class Refused(RuntimeError):
    """The switchboard would not make the call: cap reached, visibility, no model."""


@dataclass
class Outcome:
    call_id: str
    model: str
    text: str
    cost_cents: float
    fell_back: bool


def month_spend_cents(store: Store) -> float:
    start = datetime.now(UTC).strftime("%Y-%m-01")
    with store.read():
        r = store.con.execute("SELECT COALESCE(sum(cost_cents),0) FROM ai_calls WHERE ts >= ?", (start,)).fetchone()
    return float(r[0])


def models_for(store: Store, job: str) -> tuple[str, str]:
    jobs = settings.get_value(store, "ai.jobs")
    cfg = jobs.get(job) or {}
    return cfg.get("model", "none"), cfg.get("fallback", "none")


def may_see(store: Store, scope: str | None, model: str) -> bool:
    if not scope:
        return True
    level = (settings.get_value(store, "ai.visibility") or {}).get(scope, "cloud")
    if level == "none":
        return False
    if level == "local":
        return providers.is_local(model)
    return True


def status(store: Store) -> dict:
    cap = int(settings.get_value(store, "ai.monthly_cap_cents"))
    spend = month_spend_cents(store)
    jobs = settings.get_value(store, "ai.jobs")
    from .. import secrets
    return {"month_spend_cents": round(spend, 2), "monthly_cap_cents": cap, "cap_reached": spend >= cap,
            "claude_key_set": secrets.is_set("ANTHROPIC_API_KEY"), "jobs": jobs,
            "visibility": settings.get_value(store, "ai.visibility"),
            "sure_threshold": settings.get_value(store, "logic.ai.inbox").get("sure_threshold", 0.85)}


def _log(store: Store, *, job, workflow, model, version, user, text, reply, ok, error) -> str:
    cid = uuid7()
    with store.tx() as con:
        con.execute("INSERT INTO ai_calls(id, ts, job, workflow, model, prompt_version, input_chars, output_chars, input_tokens, "
                    "output_tokens, cost_cents, ms, ok, error, input_preview, output_preview) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, now_iso(), job, workflow, model, version, len(user), len(text or ""),
                     reply.input_tokens if reply else None, reply.output_tokens if reply else None,
                     reply.cost_cents if reply else 0.0, reply.ms if reply else 0, int(ok), error, user[:400], (text or "")[:400]))
    return cid


def run(store: Store, *, job: str, workflow: str, user: str, scope: str | None = None, max_tokens: int = 4000, effort: str = "low") -> Outcome:
    """Call the model set for `job` with the workflow's prompt; on failure try
    the fallback. Refuses before calling if the cap is reached or the data
    may not be seen by that model."""
    version, system = prompts.get(workflow, store)
    cap = int(settings.get_value(store, "ai.monthly_cap_cents"))
    if month_spend_cents(store) >= cap:
        raise Refused(f"This month's AI spending cap (${cap / 100:.2f}) is reached. Raise it in Settings → AI.")
    primary, fallback = models_for(store, job)
    tried = []
    for i, model in enumerate([m for m in (primary, fallback) if m and m != "none"]):
        if not may_see(store, scope, model):
            tried.append(f"{model}: not allowed to see {scope} (Settings → AI → what each model may see)")
            continue
        try:
            reply = providers.call(model, system, user, max_tokens, effort, prices=settings.get_value(store, "logic.ai.prices"))
        except providers.ProviderError as e:
            _log(store, job=job, workflow=workflow, model=model, version=version, user=user, text="", reply=None, ok=False, error=str(e))
            tried.append(f"{model}: {e}")
            continue
        cid = _log(store, job=job, workflow=workflow, model=model, version=version, user=user, text=reply.text, reply=reply, ok=True, error=None)
        return Outcome(cid, model, reply.text, reply.cost_cents, fell_back=i > 0)
    if not tried:
        raise Refused(f"No model is set for the job '{job}'. Pick one in Settings → AI.")
    raise Refused("; ".join(tried))


def parse_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or fences; take the outermost object."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[s.find("{"):]
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("the model did not answer with JSON")
    return json.loads(s[a:b + 1])


def recent_calls(store: Store, limit: int = 50) -> list[dict]:
    with store.read():
        return [dict(r) for r in store.con.execute("SELECT * FROM ai_calls ORDER BY id DESC LIMIT ?", (limit,))]
