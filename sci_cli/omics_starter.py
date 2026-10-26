"""Install the bundled Omics foundation through the native profile transaction."""

from copy import deepcopy
import json
from pathlib import Path


def definition():
    return json.loads((Path(__file__).parent / "data" / "omics-starter.json").read_text(encoding="utf-8"))


def is_starter(home):
    from sci_cli.profile_distribution import read_manifest
    manifest = read_manifest(home)
    return manifest is not None and manifest.name == "boltzmann-labs-omics"


def ensure_omics(ui):
    """First activation is explicit; existing user profiles are never converted."""
    from sci_constants import get_sci_home
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.native_profile_creation import reviewed_model_seed
    from sci_cli.profile_distribution import DistributionManifest, write_manifest
    from sci_cli.profiles import create_profile, get_profile_dir

    home = get_profile_dir("omics")
    if home.exists() or home.is_symlink():
        if not is_starter(home):
            ui.show("An existing profile already uses 'omics'. It is not the bundled Omics coordinator. "
                    "It will be opened unchanged; no starter files or capabilities will be applied.")
        else:
            from sci_cli.omics_foundation import offer_foundation
            offer_foundation(home, ui)
        return
    original = read_user_config_raw(get_sci_home() / "config.yaml")
    seed = reviewed_model_seed(original, source_home=get_sci_home())
    starter = definition()
    ui.show(f"Omics coordinator {starter['version']}\nWorkspace: {home / 'workspace'}\n"
            "Separate conversation, memory and settings; shared LLM login where supported. "
            "Includes 16 foundation instruction skills and skill listing/loading/management tools. "
            "No scientific executors, child specialists, service keys or domain software will be installed. "
            "This is application-state separation, not an OS sandbox. "
            "Model authentication is checked by normal SCI sign-in/request handling, not by this setup.")
    ui.choose("Create the Omics coordinator workspace?", ("Create Omics", "Cancel"))

    def prepare(staging):
        config = deepcopy(seed)
        for key in ("display", "reasoning"):
            if key in original:
                config[key] = deepcopy(original[key])
        config.update({
            "platform_toolsets": {"cli": []},
            "plugins": {"enabled": [], "entries": {}},
            "mcp_servers": {},
            "agent": {"coding_context": "off", "disabled_toolsets": ["delegation", "x_search"]},
            "delegation": {"orchestrator_enabled": False},
            "skills": {"external_dirs": [], "trusted_project_dirs": [],
                       "inline_shell": False, "template_vars": False},
            "terminal": {"backend": "local", "cwd": str(home / "workspace")},
        })
        (staging / "workspace").mkdir(exist_ok=True)
        from sci_cli.omics_foundation import configure_skill_access, install_missing
        configure_skill_access(config)
        atomic_config_replace(staging / "config.yaml", config)
        install_missing(staging)
        (staging / "SOUL.md").write_text(starter["persona"], encoding="utf-8")
        write_manifest(staging, DistributionManifest(
            name=starter["name"], version=starter["version"], description=starter["description"],
            author="Boltzmann Labs", distribution_owned=["SOUL.md", "distribution.yaml", "skills"],
        ))

    create_profile("omics", no_alias=True, no_skills=True, prepare_staging=prepare,
                   description=starter["description"])
    ui.show("Created Omics. Ready for conversation once model authentication is available. "
            "Foundation skill instructions installed. No scientific executors or child specialists configured yet.")


def startup_notice(home):
    """Report saved readiness, never claim a probe or live execution succeeded."""
    from sci_cli.config import read_user_config_raw
    if not is_starter(home):
        return None
    config = read_user_config_raw(home / "config.yaml")
    if (set((config.get("platform_toolsets") or {}).get("cli", [])) - {"skills"}
            or (config.get("plugins") or {}).get("enabled") or config.get("mcp_servers")):
        return "[Omics] Capability configuration has changed. Check /capabilities; execution readiness is not verified."
    from sci_cli.omics_foundation import foundation
    names = [s["name"] for s in foundation()["skills"]]
    installed = sum((home / "skills" / name / "SKILL.md").is_file() for name in names)
    return (f"[Omics] {installed}/{len(names)} foundation instruction skills present; "
            "check /capabilities for enablement. Scientific executors and child specialists are not configured. "
            "Use /activate main to return. Model sign-in is managed through /login.")
