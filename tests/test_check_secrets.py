import scripts.check_secrets as cs


def test_scanner_catches_keys(tmp_path):
    bad = tmp_path / "page.html"
    # built at runtime so this file never contains a key-shaped string itself
    fake = "AIza" + "SyA1234567890abcdefghijklmnopqrstuv"
    bad.write_text(f'const GOOGLE_KEY = "{fake}";\n')
    assert [label for _, label in cs.scan(str(bad))] == ["Google API key"]
    ok = tmp_path / "fine.py"
    ok.write_text("GOOGLE_MAPS_API_KEY = secrets.get_for_engine('GOOGLE_MAPS_API_KEY')\n")
    assert cs.scan(str(ok)) == []
    env = tmp_path / ".env"
    env.write_text("X=1\n")
    assert cs.scan(str(env))[0][1].startswith("a .env file")
