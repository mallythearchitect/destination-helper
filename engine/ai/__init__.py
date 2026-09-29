"""The AI part of the engine: the models are the brain, the engine is the hands.

switchboard  picks the model for a job from Settings, checks what it may
             see and the monthly cap, calls it, logs the call, falls back
providers    Anthropic (Claude), Ollama (a model on this machine), and a fake
             one for tests
prompts      every prompt with a version
inbox        suggestions that wait for the person's OK; approval runs an action
tests        labelled examples and a score per model per job
workflows/   the workflows themselves (none yet: the first will draft trip confirmations)
mcp_server   the plug: the engine's actions and reads offered as tools
"""
