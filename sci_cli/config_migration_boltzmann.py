"""Retire the formerly shipped Tailscale model endpoint, preserving custom routes."""

from copy import deepcopy

LEGACY_BASE_URL = "http://100.87.197.84:8010/v1"
PUBLIC_BASE_URL = "https://sciagent.boltzmann.co.in/v1"
PROVIDER_NAMES = ("boltzmann_models", "boltzmann-models")


def migrate_endpoints(config):
    """Rewrite only explicit Boltzmann routes using the exact retired default."""
    changed = []

    def update(route, path):
        if not isinstance(route, dict):
            return
        value = route.get("base_url")
        if isinstance(value, str) and value.strip().rstrip("/") == LEGACY_BASE_URL:
            route["base_url"] = PUBLIC_BASE_URL
            changed.append(path + ".base_url")

    model = config.get("model")
    if isinstance(model, dict) and model.get("provider") in PROVIDER_NAMES:
        update(model, "model")
    providers = config.get("providers")
    if isinstance(providers, dict):
        for name in PROVIDER_NAMES:
            update(providers.get(name), "providers." + name)
    auxiliary = config.get("auxiliary")
    if isinstance(auxiliary, dict):
        for name, route in auxiliary.items():
            if isinstance(route, dict) and route.get("provider") in PROVIDER_NAMES:
                update(route, "auxiliary." + name)
    return changed


def is_expected_endpoint_upgrade(snapshot, live, path):
    """The updater must not restore the retired URL over this approved migration."""
    if path != ("model", "base_url"):
        return False
    before, after = snapshot.get("model"), live.get("model")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return False
    if before.get("provider") != after.get("provider"):
        return False
    expected = deepcopy(snapshot)
    return ("model.base_url" in migrate_endpoints(expected)
            and after.get("base_url") == expected["model"]["base_url"])
