"""The plug offers the actions and reads as tools."""
import json

import pytest


@pytest.mark.anyio
async def test_mcp_lists_actions_and_reads(env, store):
    from engine.ai.mcp_server import build
    server = build(store)
    tools = {t.name: t for t in await server.list_tools()}
    assert {"trips_create", "trips_add_item", "trip_checks", "search_records", "destinations_search", "logic_settings"} <= set(tools)
    assert not any(n.startswith("money") for n in tools)
    assert tools["trips_delete"].description.startswith("DANGEROUS")
    assert "headcount" in json.dumps(tools["trips_create"].input_schema)
    res = await server.call_tool("trips_create", {"input": {"name": "Plug trip", "headcount": 2}})
    text = res[0].text if isinstance(res, list) else res.content[0].text
    assert json.loads(text)["name"] == "Plug trip"
    res = await server.call_tool("trips_list", {})
    text = res[0].text if isinstance(res, list) else res.content[0].text
    assert json.loads(text)[0]["name"] == "Plug trip"
