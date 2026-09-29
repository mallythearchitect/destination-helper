#!/bin/sh
# Registers the engine as an MCP server named "destination-helper" for Claude Code
# (this machine, user scope). After this, a Claude Code chat can ask "check my
# trip" or "compare every way from Krabi to Phuket" and it presses the engine's buttons.
# For Claude Desktop, add the same command to its config (see docs/how-it-works.md).
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
if command -v claude >/dev/null 2>&1; then
  claude mcp remove destination-helper -s user >/dev/null 2>&1 || true
  claude mcp add -s user destination-helper -- "$ROOT/.venv/bin/python" -m engine.ai.mcp_server
  echo "registered 'destination-helper' with Claude Code (user scope). Start a new chat and ask: what does the checker say about my trip?"
else
  echo "claude (Claude Code) not found. Add this to your MCP config by hand:"
  echo "  command: $ROOT/.venv/bin/python   args: -m engine.ai.mcp_server   cwd: $ROOT"
fi
