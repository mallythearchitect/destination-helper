# 7. AI is a switchboard, an inbox and a plug, not a second engine (2026-09-27)

**Chose:** apps and workflows ask the engine for a job (sort, read, draft,
answer). A switchboard (`engine/ai/switchboard.py`) maps the job to a model
from Settings, checks what that model may see and the month's cap, calls
it, logs the call, and tries the backup on failure. Workflows only file
suggestions into an inbox; approval runs an ordinary action. The MCP plug
offers the same actions and reads to any Claude chat.

**Why:** the plan's rules: don't build a second engine for AI; workflows
before agents; AI can only press buttons the apps already have; anything
that sends, pays or deletes waits for the person. Keeping every call in one
table with its cost makes the cap real and the bill explainable. Making
every approval a labelled example gives each workflow its own test set for
free, so switching models is a measured settings change.

**Chose too:** Claude through the official Anthropic SDK; Ollama for a local
model; no LiteLLM until a third provider is actually wanted (the switchboard
already isolates providers, so adding one is one function). Prompts ask for
JSON only, so any model can answer them, and the engine validates every
answer before it becomes a suggestion.

**Cost:** one more place to look when something is off (the Log tab). Worth
it: the log is the audit trail the plan asks for.
