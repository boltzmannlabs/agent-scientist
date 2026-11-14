"""Gateway-discovered platform models with profile-local authorization."""

from providers import register_provider
from providers.base import ProviderProfile


class BoltzmannModels(ProviderProfile):
    def fetch_models(self, *, api_key=None, base_url=None, timeout=8.0):
        from plugins.boltzmann.model_gateway import catalog_models, endpoint, owner_scope

        with owner_scope():
            if base_url and str(base_url).rstrip("/") != endpoint():
                return []
            return catalog_models(timeout=timeout)

    def get_model_context_length(self, model):
        from plugins.boltzmann.model_context import model_limits

        limits = model_limits(model)
        return limits.context if limits else None

    def get_model_context_note(self, model, context_length):
        from plugins.boltzmann.model_context import context_note

        return context_note(model, context_length)

    def get_max_tokens(self, model):
        from plugins.boltzmann.model_context import model_limits

        limits = model_limits(model)
        return limits.output if limits else None

    def get_output_reservation(self, model, max_tokens):
        from plugins.boltzmann.model_context import output_reservation

        return output_reservation(model, max_tokens)

    def resolve_credentials(self, *, strict=False):
        from plugins.boltzmann.model_gateway import credentials

        return credentials(strict=strict)

    def setup_model(self, config, current_model=""):
        from plugins.boltzmann.model_gateway import setup_model

        setup_model(current_model)
        return True

    def supported_reasoning_efforts(self, model=None):
        return ()  # Gateway model IDs do not declare a reasoning-control contract.

    def create_client(self, **kwargs):
        from plugins.boltzmann.model_client import BoltzmannClient

        return BoltzmannClient(**kwargs)

    def fetch_account_usage(self, **kwargs):
        from plugins.boltzmann.model_gateway import account_usage

        return account_usage()


def classify(error, **context):
    # An explicit platform route must not rotate onto another account/provider.
    status = context.get("status_code")
    if isinstance(error, PermissionError) or status in {401, 403}:
        return {
            "reason": "auth_permanent",
            "retryable": False,
            "should_rotate_credential": False,
            "should_fallback": False,
        }
    if status == 402:
        return {
            "reason": "billing",
            "retryable": False,
            "should_rotate_credential": False,
            "should_fallback": False,
        }
    return None


register_provider(
    BoltzmannModels(
        name="boltzmann_models",
        aliases=("boltzmann-models",),
        display_name="boltzmann_models",
        description="Boltzmann platform models — requires /boltzmann_login in this profile",
        signup_url="https://app.boltzmann.co/home",
        env_vars=("BOLTZMANN_API_KEY",),
        base_url="https://sciagent.boltzmann.co.in/v1",
        api_mode="chat_completions",
        fallback_models=(),
        credential_scope="profile",
        picker_visible_when_locked=True,
        requires_custom_client=True,
        allow_fallback=False,
        show_account_usage_after_turn=True,
        supports_health_check=False,
        supports_model_listing=True,
        classify_api_error=classify,
    )
)
