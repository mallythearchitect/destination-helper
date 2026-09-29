"""Every prompt, with a version. Change a prompt: bump its version, then run
the test set before switching (Settings → AI). Prompts speak plainly and
ask for JSON only, so any model can answer them."""
from __future__ import annotations

PROMPTS: dict[str, tuple[str, str]] = {
    "_example": ("v1", "You answer with JSON only, in the exact shape asked for, and say how sure you are from 0 to 1."),
}


def get(name: str, store=None) -> tuple[str, str]:
    """The prompt for a workflow: a Settings → Logic override (version 'custom') or the built-in one."""
    if store is not None:
        from .. import settings
        try:
            override = (settings.get_value(store, "logic.ai.prompts") or {}).get(name)
            if override and override.strip():
                return "custom", override
        except Exception:
            pass
    return PROMPTS[name]
