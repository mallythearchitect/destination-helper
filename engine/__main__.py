import uvicorn

from .main import PORT

uvicorn.run("engine.main:app", host="127.0.0.1", port=PORT, reload=False, log_level="info")
