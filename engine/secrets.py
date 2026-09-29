"""API keys live in one private file (.env, mode 0600) that git ignores.
Pages and the API only ever learn whether a key is set. Values are never
returned, logged or written to the vault."""
from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass

from .store import ROOT

NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


@dataclass(frozen=True)
class Secret:
    name: str
    section: str
    label: str
    help: str = ""


SECRETS: list[Secret] = [
    Secret("GOOGLE_MAPS_API_KEY", "maps", "Google Maps API key",
           "Street view and photoreal 3D in City Viewer. Replace the key that leaked from the old repo."),
    Secret("MAPILLARY_TOKEN", "maps", "Mapillary token",
           "Crowdsourced street imagery, the fallback when Google has none."),
    Secret("ANTHROPIC_API_KEY", "ai", "Claude API key",
           "The default brain for background jobs (phase 3). Chat work runs on the Claude plan, not this key."),
    Secret("OPENAI_API_KEY", "ai", "Backup AI service key",
           "Optional second provider behind the switchboard. Ollama on this machine needs no key."),
    Secret("FRED_API_KEY", "data", "FRED API key",
           "Economic data from the St. Louis Fed (phase 7). Free key."),
]
BY_NAME = {s.name: s for s in SECRETS}


def env_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("MINDSCAPE_ENV") or ROOT / ".env")


def _read_lines() -> list[str]:
    p = env_path()
    return p.read_text().splitlines() if p.exists() else []


def _parse(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k] = v
    return out


def is_set(name: str) -> bool:
    if os.environ.get(name):
        return True
    return bool(_parse(_read_lines()).get(name))


def status() -> list[dict]:
    return [{"name": s.name, "section": s.section, "label": s.label, "help": s.help,
             "set": is_set(s.name)} for s in SECRETS]


def _write_lines(lines: list[str]) -> None:
    p = env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""))
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
    os.chmod(p, 0o600)


def set_secret(name: str, value: str) -> None:
    if name not in BY_NAME or not NAME_RE.match(name):
        raise KeyError(name)
    value = value.strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("a key is one non-empty line")
    lines = _read_lines()
    quoted = f"{name}={value}"
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip().removeprefix("export ").strip() == name:
            lines[i] = quoted
            break
    else:
        lines.append(quoted)
    _write_lines(lines)


def clear_secret(name: str) -> None:
    if name not in BY_NAME:
        raise KeyError(name)
    lines = [ln for ln in _read_lines()
             if ln.split("=", 1)[0].strip().removeprefix("export ").strip() != name]
    _write_lines(lines)


def get_for_engine(name: str) -> str | None:
    """For the engine's own connectors only. Never call this from an API route."""
    return os.environ.get(name) or _parse(_read_lines()).get(name)
