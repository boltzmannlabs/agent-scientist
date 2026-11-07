"""The route's output reservation, shared by startup, switching and previews."""


def output_reservation(model, provider, base_url, max_tokens=None):
    from providers import get_provider_profile

    profile = get_provider_profile(provider)
    reservation = profile.get_output_reservation(model, max_tokens) if profile else max_tokens
    if reservation is not None:
        return reservation
    from agent.gemini_native_adapter import (
        GEMINI_DEFAULT_MAX_OUTPUT_TOKENS, is_native_gemini_base_url,
    )

    if str(provider or "").strip().lower() in {
        "gemini", "google", "google-gemini", "google-ai-studio",
    } or is_native_gemini_base_url(base_url):
        return GEMINI_DEFAULT_MAX_OUTPUT_TOKENS
    return None
