"""Secure CLI-only authorization; default activation leaves the live agent untouched."""

from pathlib import Path

from sci_cli.config import is_managed, load_config
from .auth import KEY_NAME, authorize_saved_key, current_key, fingerprint
from .nodeapi_helpers import authenticate_api_key


def register_skills(ctx):
    ctx.register_skill("tools", Path(__file__).parent / "skills" / "boltzmann-tools" / "SKILL.md",
                       description="List Boltzmann scientific tools by module and run authenticated workflows.")


def enable_toolset(*, expected_config=None, after_save=None):
    from agent.skill_utils import parse_config_string_list
    from sci_cli.config import _CONFIG_LOCK, get_config_path, read_user_config_raw, atomic_config_write
    from sci_cli.plugins_state import _locked_plugin_state
    from sci_cli.tools_config import _get_platform_tools
    # Plugin discovery can use worker threads which read configuration. Never
    # wait for it while holding the config writer's lock.
    defaults = sorted(_get_platform_tools(load_config(), "cli"))
    with _locked_plugin_state(get_config_path()), _CONFIG_LOCK:
        raw = read_user_config_raw()
        if expected_config is not None and raw != expected_config:
            raise ValueError("Profile configuration changed during authorization; retry.")
        configured = raw.get("platform_toolsets", {}).get("cli")
        selected = (parse_config_string_list(configured) if configured is not None
                    else defaults)
        patch = {"platform_toolsets": {"cli": list(dict.fromkeys([*selected, "boltzmann"]))}}
        plugins = raw.get("plugins", {})
        enabled = parse_config_string_list(plugins.get("enabled"))
        patch["plugins"] = {"enabled": list(dict.fromkeys([*enabled, "boltzmann"]))}
        plugin_disabled = parse_config_string_list(plugins.get("disabled"))
        if "boltzmann" in plugin_disabled:
            patch["plugins"]["disabled"] = [name for name in plugin_disabled if name != "boltzmann"]
        disabled = parse_config_string_list(raw.get("agent", {}).get("disabled_toolsets"))
        if "boltzmann" in disabled:
            patch["agent"] = {"disabled_toolsets": [name for name in disabled if name != "boltzmann"]}
        # Only these settings change. The general setup saver also migrates
        # unrelated backend values, which would invalidate a reviewed sandbox.
        for section, values in patch.items():
            raw.setdefault(section, {}).update(values)
        atomic_config_write(get_config_path(), raw)
        if after_save is not None:
            after_save(read_user_config_raw())


def add_boltzmann(ctx, raw_args, *, complete_setup=None, reuse_saved=False):
    words = raw_args.strip().split()
    if any(word not in {"--now", "--replace"} for word in words):
        return "Usage: /add_boltzmann [--now] [--replace]. Never paste a key in the command; use the masked prompt."
    if is_managed():
        return "Boltzmann setup is unavailable in a managed installation. Contact your administrator."
    verification = None
    verified_fingerprint = None

    def validate(value):
        nonlocal verification, verified_fingerprint
        verification = authenticate_api_key(value)
        if verification.authenticated:
            verified_fingerprint = fingerprint(value.strip())
        return verification.authenticated

    try:
        if reuse_saved:
            if not validate(current_key()):
                return "[add_boltzmann] FAILED. Existing key and authorization are unchanged. " + verification.message
        else:
            result = ctx.prompt_secret(KEY_NAME, "Enter your Boltzmann API key", validator=validate)
            if result.get("skipped"):
                return "[add_boltzmann] CANCELLED. Existing authorization is unchanged. " + result["message"]
            if not result.get("success") or not result.get("validated") or verification is None or not verification.authenticated:
                detail = verification.message if verification else result.get("message", "Key not validated.")
                return "[add_boltzmann] FAILED. No new authorization granted. " + detail
    except (KeyboardInterrupt, EOFError):
        return ("[add_boltzmann] CANCELLED during credential capture or verification. No new authorization granted. "
                "If interrupted while saving, check this profile's credential storage before retrying.")
    except Exception:
        return "[add_boltzmann] FAILED during credential capture/storage. No new authorization granted. Check credential storage permissions."
    try:
        if complete_setup is None:
            enable_toolset()
        else:
            complete_setup()
        authorize_saved_key(expected_fingerprint=verified_fingerprint)
    except (KeyboardInterrupt, EOFError):
        return ("[add_boltzmann] CANCELLED while enabling. A key is retained; settings may be partially updated. "
                "Activation was not confirmed. Run /boltzmann_login to review and retry.")
    except Exception:
        return (verification.account_summary() + "\n[add_boltzmann] FAILED while enabling. A key is retained; settings may be partially updated. "
                "If another process changed the key after verification, verify the current key again. "
                "Activation was not confirmed. Check profile write permissions and run /add_boltzmann again.")
    if "--now" in words:
        from sci_cli.plugins import discover_plugins
        try:
            discover_plugins(force=True)
            register_skills(ctx)
            refreshed = ctx.refresh_tools(now=True)
        except (KeyboardInterrupt, EOFError):
            return (verification.account_summary() + "\n[add_boltzmann] SAVED. Key and authorization retained. "
                    "Immediate refresh was cancelled; live activation was not confirmed. Use /new for a fresh runtime.")
        except Exception:
            return (verification.account_summary() + "\n[add_boltzmann] SAVED. Key and authorization retained, "
                    "but immediate tool refresh failed. Live activation was not confirmed. Use /new for a fresh runtime.")
        if refreshed:
            return verification.account_summary() + "\n[add_boltzmann] SAVED. Boltzmann enabled now by explicit request; the prompt cache may be rebuilt."
        return (verification.account_summary() + "\n[add_boltzmann] SAVED. Key and authorization retained. "
                "Immediate activation was not confirmed. Use /new for a fresh runtime.")
    return (verification.account_summary() + "\n[add_boltzmann] SAVED. Enabled. Available automatically in your next session.")
