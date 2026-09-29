"""Actions: what an app can do, each an all-or-nothing write with a typed
input. Apps register them here; the API exposes them at
POST /v1/actions/<app>.<name>, and GET /v1/actions lists them with their
input schema. That same list is what the AI plug (phase 3) will offer as
tools, so each action's description is written for a reader who has never
seen the code."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .store import Store


@dataclass(frozen=True)
class Action:
    name: str                      # app.verb, e.g. trips.add_item
    description: str
    model: type[BaseModel]
    run: Callable[[Store, BaseModel, str], Any]   # (store, input, app) -> result
    dangerous: bool = False        # sends, pays or deletes: the AI must ask first


REGISTRY: dict[str, Action] = {}


def action(name: str, description: str, model: type[BaseModel], dangerous: bool = False):
    def wrap(fn):
        REGISTRY[name] = Action(name, description, model, fn, dangerous)
        return fn
    return wrap


def describe() -> list[dict]:
    return [{"name": a.name, "description": a.description, "dangerous": a.dangerous,
             "input": a.model.model_json_schema()} for a in REGISTRY.values()]


def run(store: Store, name: str, payload: dict, app: str) -> Any:
    a = REGISTRY.get(name)
    if not a:
        raise KeyError(name)
    data = a.model.model_validate(payload)
    return a.run(store, data, app)
