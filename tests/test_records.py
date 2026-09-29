"""Phase 1 done-when: from the browse page you can find, link, attach a file
to, and undo anything. These tests prove the engine side of each verb."""


def _person(client, name="Ada Lovelace", **kw):
    r = client.post("/v1/entities", json={"type": "person", "name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_find_update(client):
    ada = _person(client, data={"city": "London", "born": 1815}, external_ids={"wikidata": "Q7259"}, source="test")
    assert ada["version"] == 1 and ada["data"]["city"] == "London"
    hits = client.get("/v1/search?q=lond").json()          # prefix match on a detail, not the name
    assert [h["name"] for h in hits] == ["Ada Lovelace"] and "[London]" in hits[0]["snippet"]
    assert client.get("/v1/search?q=Q7259").json()[0]["id"] == ada["id"]   # outside ids are searchable
    assert client.get("/v1/search?q=nobody").json() == []
    r = client.put(f"/v1/entities/{ada['id']}", json={"data": {"city": "Turin"}, "version": 1})
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["data"] == {"city": "Turin"}
    assert client.get("/v1/search?q=london").json() == []
    assert client.get("/v1/search?q=turin").json()[0]["id"] == ada["id"]
    assert client.get("/v1/search?type=person").json()[0]["id"] == ada["id"]
    assert client.get("/v1/types").json()["types"][0] == {"type": "person", "label": "Person", "count": 1}


def test_bad_records_refused(client):
    assert client.post("/v1/entities", json={"type": "Person!", "name": "x"}).status_code == 400
    assert client.post("/v1/entities", json={"type": "person", "name": "  "}).status_code == 400
    assert client.get("/v1/entities/nope").status_code == 404


def test_second_window_cannot_overwrite_a_record(client):
    ada = _person(client)
    client.put(f"/v1/entities/{ada['id']}", json={"name": "Ada King", "version": 1})
    r = client.put(f"/v1/entities/{ada['id']}", json={"name": "Countess", "version": 1})
    assert r.status_code == 409 and r.json()["detail"]["theirs"]["name"] == "Ada King"


def test_link_tag_note_file_and_undo_each(client, tmp_path):
    ada = _person(client)
    babbage = _person(client, name="Charles Babbage")
    eid = ada["id"]
    # link
    lk = client.post(f"/v1/entities/{eid}/links", json={"to_id": babbage["id"], "rel": "related", "note": "worked with"})  # noqa: E501
    assert lk.status_code == 201
    other = client.get(f"/v1/entities/{babbage['id']}").json()["links"]
    assert other[0]["other_name"] == "Ada Lovelace" and other[0]["direction"] == "in"
    assert client.post(f"/v1/entities/{eid}/links", json={"to_id": eid}).status_code == 400
    # tag
    assert client.post(f"/v1/entities/{eid}/tags", json={"tag": "Mathematics"}).json()["tags"] == ["mathematics"]
    assert client.get("/v1/search?q=mathem").json()[0]["id"] == eid
    assert client.get("/v1/search?tag=mathematics").json()[0]["id"] == eid
    # note
    nt = client.post(f"/v1/entities/{eid}/notes", json={"body": "First programmer."})
    assert nt.status_code == 201 and client.get("/v1/search?q=programmer").json()[0]["id"] == eid
    # file
    up = client.post(f"/v1/entities/{eid}/files", files={"file": ("portrait.txt", b"hello ada", "text/plain")})
    assert up.status_code == 201
    fid = up.json()["id"]
    got = client.get(f"/v1/files/{fid}")
    assert got.content == b"hello ada" and got.headers["content-type"].startswith("text/plain")
    full = client.get(f"/v1/entities/{eid}").json()
    assert full["tags"] == ["mathematics"] and len(full["notes"]) == 1 and full["files"][0]["name"] == "portrait.txt"
    assert len(full["links"]) == 1 and full["history"][0]["action"] == "files.attach"

    # delete each, then undo each, newest first
    assert client.delete(f"/v1/files/{fid}").status_code == 200
    assert client.get(f"/v1/files/{fid}").status_code == 404
    client.delete(f"/v1/notes/{nt.json()['id']}")
    client.delete(f"/v1/entities/{eid}/tags/mathematics")
    client.delete(f"/v1/links/{lk.json()['id']}")
    full = client.get(f"/v1/entities/{eid}").json()
    assert full["files"] == [] and full["notes"] == [] and full["tags"] == [] and full["links"] == []
    for entry in client.get("/v1/history?limit=4").json():
        assert client.post(f"/v1/history/{entry['id']}/undo").status_code == 200, entry
    full = client.get(f"/v1/entities/{eid}").json()
    assert full["files"][0]["id"] == fid and full["notes"][0]["body"] == "First programmer."
    assert full["tags"] == ["mathematics"] and full["links"][0]["other_name"] == "Charles Babbage"
    assert client.get(f"/v1/files/{fid}").content == b"hello ada"


def test_delete_record_and_undo(client):
    ada = _person(client)
    client.post(f"/v1/entities/{ada['id']}/tags", json={"tag": "x"})
    r = client.delete(f"/v1/entities/{ada['id']}")
    assert r.json()["deleted_at"] and client.get("/v1/search").json() == []
    assert client.get("/v1/search?deleted=true").json()[0]["id"] == ada["id"]
    h = client.get("/v1/history?limit=1").json()[0]
    assert h["action"] == "entities.delete"
    client.post(f"/v1/history/{h['id']}/undo")
    back = client.get(f"/v1/entities/{ada['id']}").json()
    assert back["deleted_at"] is None and back["tags"] == ["x"] and back["version"] == 3
    assert client.get("/v1/search?q=ada").json()[0]["id"] == ada["id"]
    # undoing a creation soft-deletes it, and undoing that brings it back
    create_entry = [e for e in client.get("/v1/history?limit=50").json() if e["action"] == "entities.create"][0]
    client.post(f"/v1/history/{create_entry['id']}/undo")
    assert client.get("/v1/search?q=ada").json() == []
    client.post(f"/v1/history/{client.get('/v1/history?limit=1').json()[0]['id']}/undo")
    assert client.get("/v1/search?q=ada").json()[0]["id"] == ada["id"]


def test_history_download_includes_records(client):
    ada = _person(client)
    d = client.get("/v1/history/export?tbl=entities").json()
    assert d["count"] == 1 and d["changes"][0]["row_key"] == ada["id"]
