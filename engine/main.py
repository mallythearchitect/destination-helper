"""FastAPI app: the /v1 API plus the app pages and ui-kit as static files.

    python -m engine            → http://127.0.0.1:8772

It listens on this machine only. No accounts, no cloud.
"""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

# Each app registers its actions when imported.
import apps.destinations.server.actions  # noqa: E402, F401
import apps.trips.server.actions  # noqa: E402, F401
import engine.engine_actions  # noqa: E402, F401
from apps.destinations.server import api as destinations_api  # noqa: E402
from apps.trips.server import api as trips_api  # noqa: E402

from .api.routes import router
from .store import ROOT, Store

PORT = int(os.environ.get("MINDSCAPE_PORT") or 8772)


def _housekeeping(app: FastAPI, stop: threading.Event):
    """A catch-up pass at start (the Mac may have slept through a schedule), then the
    workflow runner takes over: every minute it runs whatever is due."""
    from . import workflows
    if stop.wait(3):
        return
    try:
        for name in workflows.due_now(app.state.store):
            workflows.run(app.state.store, name, trigger="startup")
    except Exception as e:
        print("housekeeping:", e)
    runner = workflows.Runner(app.state.store)
    runner.stop = stop
    runner._loop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = Store(app.state.vault_path if hasattr(app.state, "vault_path") else None)
    from . import sources
    sources.seed_from_packs(app.state.store)
    stop = threading.Event()
    worker = threading.Thread(target=_housekeeping, args=(app, stop), daemon=True)
    if not os.environ.get("MINDSCAPE_NO_HOUSEKEEPING"):
        worker.start()
    try:
        yield
    finally:
        stop.set()
        app.state.store.close()


def create_app(vault_path=None) -> FastAPI:
    app = FastAPI(title="Destination Helper", version="0.1.0", lifespan=lifespan,
                  docs_url="/v1/docs", openapi_url="/v1/openapi.json")
    if vault_path:
        app.state.vault_path = vault_path
    app.include_router(router)
    app.include_router(destinations_api.router)
    app.include_router(trips_api.router)

    @app.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/apps/launcher/web/")

    @app.middleware("http")
    async def always_revalidate(request, call_next):
        """Pages and scripts change often while this is being built: tell the
        browser to check with the server every time (ETags keep that cheap),
        so a stale copy never hides a change."""
        response = await call_next(request)
        if request.url.path.startswith(("/apps/", "/ui-kit/")):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/ui-kit", StaticFiles(directory=ROOT / "ui-kit"), name="ui-kit")
    app.mount("/apps", StaticFiles(directory=ROOT / "apps", html=True), name="apps")
    return app


app = create_app()
