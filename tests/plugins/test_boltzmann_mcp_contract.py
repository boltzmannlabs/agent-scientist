"""The MCP adapter must expose and forward the native connector's public arguments."""

import asyncio
import importlib
import json


def test_mcp_discovery_and_argument_forwarding_match_native_schemas(monkeypatch):
    from plugins.boltzmann.schemas import SCHEMAS

    adapter = importlib.import_module("plugins.boltzmann.boltzmann_mcp_server")
    discovered = {tool.name: tool.input_schema for tool in asyncio.run(adapter.mcp.list_tools())}
    for native in SCHEMAS:
        name = native["name"]
        expected = native["parameters"]
        actual = discovered[name]
        assert set(actual["properties"]) == set(expected["properties"])
        assert set(actual.get("required", [])) == set(expected.get("required", []))
        captured = []

        def handler(**kwargs):
            captured.append(kwargs)
            return json.dumps({"fixture": True})

        monkeypatch.setattr(adapter, "handle_" + name, handler)
        args = {field: ({"fixture": "value"} if spec["type"] == "object" else
                        True if spec["type"] == "boolean" else "fixture")
                for field, spec in expected["properties"].items()}
        # Real decorated entry point; only the final handler is intercepted.
        # No credentials, service calls or scientific workers.
        result = getattr(adapter, name)(**args)
        assert json.loads(result) == {"fixture": True}
        assert captured == [args]
        if name == 'boltzmann_submit':
            without_name = {key: value for key, value in args.items() if key != 'experiment_name'}
            assert json.loads(getattr(adapter, name)(**without_name)) == {'fixture': True}
            assert captured[-1] == {**without_name, 'experiment_name': ''}
