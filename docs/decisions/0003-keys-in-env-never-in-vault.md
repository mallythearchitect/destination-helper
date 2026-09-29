# 3. Keys live in .env; the API only says whether one is set (2026-09-27)

**Chose:** every API key is a named entry in one file, `.env`, mode 600, that
git ignores. `PUT /v1/secrets/<name>` writes it, `GET /v1/secrets` returns
`set: true/false`, and no route ever returns a value. Engine code that needs
a key calls `secrets.get_for_engine(name)` directly.

**Why:** the old City Viewer kept keys in the browser and forgot them on
reload; the old repo leaked one to GitHub. Keys in the vault would land in
every backup. One file, one rule, one scanner.

**Later:** the macOS Keychain, if `.env` ever proves too loose. Same API.
