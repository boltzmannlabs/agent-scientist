"""Public input documentation stays separate from executable request validation."""

import copy
import json
import re
from pathlib import Path

from plugins.boltzmann.contract_docs import generated_modules, render_module


def test_documented_inputs_render_without_mutating_execution_or_other_tools():
    module = {"id": "example", "title": "Example"}
    schema = {
        "type": "object",
        "properties": {"backend_count": {"type": "integer", "description": "Execution count."}},
        "required": ["backend_count"],
    }
    tool = {"job_name": "fixture", "display_name": "Fixture", "module_id": "example",
            "description": "Execution description.", "request_schema": schema}
    legacy = dict(tool, job_name="legacy", display_name="Legacy")
    catalog = {"tools": {"fixture": tool, "legacy": legacy}}
    empty = {"tools": {}}
    original = render_module(module, catalog, empty, empty)
    tool["documentation"] = {
        "description": "Explain the design task to the user.",
        "fields": [{"name": "design_count", "type": "number", "required": "Required",
                    "input_kind": "value", "description": "Choose A | B.\nUse a whole number."}],
        "results": "Design records and scores.",
        "input_limits": "Positive counts only.",
        "execution_notices": "Inspect the delivered records.",
    }
    before = copy.deepcopy(catalog)
    rendered = render_module(module, catalog, empty, empty)
    selected = rendered.split("## Fixture\n", 1)[1].split("## Legacy\n", 1)[0]

    assert catalog == before
    assert "Explain the design task to the user." in selected
    assert "| `design_count` | number | Required | value | Choose A \\| B. Use a whole number. |" in selected
    assert "backend_count" not in selected
    assert "Design records and scores." in selected
    assert "Positive counts only." in selected
    assert "Inspect the delivered records." in selected
    assert rendered.split("## Legacy\n", 1)[1] == original.split("## Legacy\n", 1)[1]


def test_generated_public_tables_match_documentation_and_resolve_request_links():
    root = Path(__file__).resolve().parents[2] / "plugins/boltzmann/skills/boltzmann-tools/references"
    catalog = json.loads((root / "tool-contracts.v1.json").read_text())
    modules = {module["id"]: module for module in catalog["modules"]}
    documents = generated_modules(root)
    documented = [tool for tool in catalog["tools"].values() if tool.get("documentation")]
    assert documented

    for tool in documented:
        path = root / modules[tool["module_id"]]["path"]
        sections = re.split(r"^## ", documents[path], flags=re.MULTILINE)
        section = next(part for part in sections if f"Exact job name: `{tool['job_name']}`." in part)
        inputs = section.split("### Inputs", 1)[1].split("### Exact request schema", 1)[0]
        rows = [line for line in inputs.splitlines() if line.startswith("| `")]
        actual = [tuple(cell.strip().strip("`") for cell in re.split(r"(?<!\\)\|", row)[1:5]) for row in rows]
        fields = tool["documentation"]["fields"]
        assert len({field["name"] for field in fields}) == len(fields)
        assert actual == [(field["name"], field["type"], field["required"], field["input_kind"]) for field in fields]
        assert all(field["description"].strip() for field in fields)
        assert tool["documentation"]["description"] in section
        assert tool["documentation"]["results"] in section
        assert not re.search(r"Jyothi|\.xlsx|platform-managed|proposed fixes|review workbook", section, re.IGNORECASE)
        links = re.findall(r"\]\(([^)]+)\)", section)
        assert links
        for link in links:
            assert not link.startswith(("/", "http:", "https:"))
            target = (path.parent / link.split("#", 1)[0]).resolve()
            assert target.is_relative_to(root.resolve()) and target.is_file()
