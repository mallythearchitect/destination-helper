#!/bin/sh
# Start the engine on http://127.0.0.1:8772
cd "$(dirname "$0")/.."
exec .venv/bin/python -m engine
