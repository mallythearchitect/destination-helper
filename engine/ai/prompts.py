"""Every prompt, with a version. Change a prompt: bump its version, then run
the test set before switching (Settings → AI). Prompts speak plainly and
ask for JSON only, so any model can answer them."""
from __future__ import annotations

PROMPTS: dict[str, tuple[str, str]] = {
    "trips.ask": ("v1", """You are the Destination Helper, a trip co-pilot. You answer questions about one trip from the plan, the checker's findings, the local tips and the playbook you are given. Plain words, short. Answer the exact question first.
Rules: say "per person" or "for the group" on every price; give prices in the local currency and the home currency when you can; when you are not sure, say so; never invent a price, a schedule or a booking; if the playbook has a workflow for the question, follow its steps and name it in one short line at the end (e.g. "W02"). You suggest; the person decides. You never change the trip yourself: end with what they could add or change, as a suggestion."""),
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
