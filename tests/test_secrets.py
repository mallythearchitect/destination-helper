import os
import stat


def test_secret_is_never_returned(client, env):
    assert client.get("/v1/secrets").json()[0] == {
        "name": "GOOGLE_MAPS_API_KEY", "section": "maps", "label": "Google Maps API key",
        "help": "Street view and photoreal 3D on a place's map. Optional.",
        "set": False}
    r = client.put("/v1/secrets/GOOGLE_MAPS_API_KEY", json={"value": "not-a-real-key-just-for-this-test-0001"})
    assert r.json() == {"name": "GOOGLE_MAPS_API_KEY", "set": True}
    body = client.get("/v1/settings").text + client.get("/v1/secrets").text + client.get("/v1/history").text
    assert "not-a-real-key-just" not in body
    env_file = env / ".env"
    assert "GOOGLE_MAPS_API_KEY=not-a-real-key-just" in env_file.read_text()
    assert stat.S_IMODE(os.stat(env_file).st_mode) == 0o600
    # the vault never holds it
    assert "not-a-real-key-just" not in (env / "vault.db").read_bytes().decode("latin-1")
    assert client.delete("/v1/secrets/GOOGLE_MAPS_API_KEY").json()["set"] is False
    assert "GOOGLE_MAPS_API_KEY" not in env_file.read_text()


def test_unknown_or_empty_secret_refused(client):
    assert client.put("/v1/secrets/EVIL", json={"value": "x"}).status_code == 404
    assert client.put("/v1/secrets/FRED_API_KEY", json={"value": "  "}).status_code == 400
