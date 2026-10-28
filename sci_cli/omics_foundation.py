"""Render and install reviewed Omics instruction bundles, never scientific software."""

import json
from pathlib import Path


def foundation():
    return json.loads((Path(__file__).parent / "data/omics-foundation.json").read_text(encoding="utf-8-sig"))


def bundles():
    from tools.skills_hub_models import SkillBundle
    from sci_cli.skill_add_sources import validate_bundle
    pack = foundation()
    contracts = (Path(__file__).parent / "data/omics-contracts.schema.json").read_text(encoding="utf-8-sig")
    for item in pack["skills"]:
        name = item["name"]
        content = f'''---
name: {name}
description: {item["description"]}
metadata:
  author: Boltzmann Labs
  version: {pack["version"]}
---
# {item["title"]} Skill

{item["description"]} This is coordinator guidance, not an installed scientific program or connector.

## When to Use
{item["when"]}

## Prerequisites
Inspect tools available in this session. Retrieval requires an authorized connector or `web_search`/`web_extract`; file inspection requires approved file tools; execution requires a configured scientific tool or an approved `terminal` runtime. These are conditional prerequisites, not capabilities granted by this skill. Never send private data to a source just because its URL is listed.

## How to Run
Load this skill through `skill_view`. Before producing shared records, load `references/contracts.schema.json` through `skill_view` with this skill name and that file path. The named `$defs` entries define StudyManifest, AnalysisPlan, ToolResult, RunRecord and EvidenceClaim. Other interface result names below are descriptive deliverables, not implemented APIs. Null means unknown, never a verified value; explain missing facts. Schemas validate record shape only, not scientific correctness, identity relationships or access rights.

## Quick Reference
Conceptual interface: `{item["interface"]}`.
No function with this name is registered by loading this skill. Use only real tools currently available.

## Procedure
{item["procedure"]}

## Pitfalls
{item["pitfall"]}
Keep proposed work, observed execution and completed results distinct. Missing tools or permissions must be reported rather than bypassed. Approval for a plan is not blanket approval for software installation or external sharing.

## Verification
{item["verification"]}
Preserve identifiers across handoffs and keep unresolved facts visible. A failed or partial run cannot support a claim of completion. Check that every sample/donor/file reference resolves, and that identifiers are unique where required; the JSON schema alone does not enforce these relationships.

## Sources and attribution
Adapted from Boltzmann Labs' {pack["source"]}. Links below are supplied integration references, not evidence that connectors are installed or that current API behavior was verified. Recheck official documentation when implementing a connector. Do not apply one assay's methods to another without justification.
'''
        content += "\n".join(f"- {url}" for url in item["sources"]) + "\n"
        yield validate_bundle(SkillBundle(name, {"SKILL.md": content, "references/contracts.schema.json": contracts},
            "bundled", f"boltzmann-labs-omics/{pack['version']}/{name}", "builtin",
            metadata={"foundation_version": pack["version"], "source": pack["source"]}))


def install_missing(home):
    """Preserve edited/existing names; failures may retain earlier successful installs."""
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.skill_add_store import existing_skill, scanned_bundle
    from tools.skill_manager_tool import _skill_mutation_lock
    from tools.skills_hub_install import install_from_quarantine
    from tools.skills_guard import should_allow_install
    installed, preserved = [], []
    with profile_scope(home):
        for bundle in bundles():
            if existing_skill(bundle.name):
                preserved.append(bundle.name)
                continue
            with scanned_bundle(bundle) as (staged, scan):
                allowed, reason = should_allow_install(scan, force=True)
                if scan.verdict == "dangerous" or not allowed:
                    raise ValueError(f"Foundation skill {bundle.name} blocked by scan: {reason}")
                with _skill_mutation_lock(bundle.name):
                    if existing_skill(bundle.name):
                        preserved.append(bundle.name)
                        continue
                    install_from_quarantine(staged, bundle.name, "", bundle, scan, overwrite=False)
            installed.append(bundle.name)
    return installed, preserved


def configure_skill_access(config):
    """Add only skill tools; don't implicitly enable newly shipped execution toolsets."""
    from sci_cli.tools_config import _configurable_keys
    tools = config.setdefault("platform_toolsets", {}).setdefault("cli", [])
    if not isinstance(tools, list):
        raise ValueError("Review platform_toolsets.cli: it must be a list before adding foundation skills.")
    if "skills" not in tools:
        tools.append("skills")
    known = config.setdefault("known_builtin_toolsets", {}).setdefault("cli", [])
    config["known_builtin_toolsets"]["cli"] = sorted(set(known) | _configurable_keys())


def offer_foundation(home, ui):
    from sci_cli.config import read_user_config_raw, atomic_config_replace
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.skill_add_store import existing_skill
    with profile_scope(home):
        missing = [b.name for b in bundles() if not existing_skill(b.name)]
    config_path = home / "config.yaml"
    before = config_path.read_bytes()
    config = read_user_config_raw(config_path)
    if not missing and "skills" in (config.get("platform_toolsets") or {}).get("cli", []):
        return
    ui.show(f"Omics foundation: {len(missing)} missing instruction skills. "
            "Existing skills and disabled choices are preserved. Adds skill listing/loading/management, "
            "not scientific executors or web connections. Security scanning does not establish scientific correctness.")
    answer = ui.choose("Add the Omics foundation for a new conversation?",
                       ("Add foundation skills", "Keep current setup", "Cancel"))
    if answer == "Keep current setup":
        return
    configure_skill_access(config)
    try:
        installed, preserved = install_missing(home)
        if config_path.read_bytes() != before:
            raise ValueError("Configuration changed during installation; settings were not overwritten.")
        atomic_config_replace(config_path, config)
        # Only the exact shipped predecessor persona is eligible for replacement.
        # User-edited personas remain private user-owned instructions.
        import hashlib
        from sci_cli.omics_starter import definition
        from utils import atomic_write_text
        starter = definition()
        soul = home / "SOUL.md"
        if soul.is_file() and not soul.is_symlink():
            if hashlib.sha256(soul.read_bytes()).hexdigest() == starter["previous_persona_sha256"]:
                atomic_write_text(soul, starter["persona"])
            elif soul.read_text(encoding="utf-8-sig") != starter["persona"]:
                ui.show("Custom Omics persona preserved. Review it if it still says foundation skills are unavailable.")
    except Exception:
        ui.show("Foundation update stopped. Some skill files may already be installed; "
                "no existing files were overwritten. Review /capabilities and skill settings before retrying.")
        raise
    ui.show(f"Added {len(installed)} foundation skills; preserved {len(preserved)} existing skills. "
            "Start a new conversation with /new after activating Omics to load the additions. "
            "The saved conversation's cached prompt was not refreshed.")
