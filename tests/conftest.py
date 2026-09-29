"""Every test gets its own throwaway vault and .env in a temp folder.
Tests never touch real data (the rule from the old workspace)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.main import create_app
from engine.store import Store


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("MINDSCAPE_VAULT", str(tmp_path / "vault.db"))
    monkeypatch.setenv("MINDSCAPE_ENV", str(tmp_path / ".env"))
    monkeypatch.setenv("MINDSCAPE_NO_HOUSEKEEPING", "1")
    for name in ("GOOGLE_MAPS_API_KEY", "MAPILLARY_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "FRED_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture
def store(env):
    s = Store()
    yield s
    s.close()


@pytest.fixture
def client(env):
    with TestClient(create_app(vault_path=env / "vault.db")) as c:
        # backups land in the temp folder too
        c.put("/v1/settings/backup.destination", json={"value": str(env / "backups")})
        yield c
