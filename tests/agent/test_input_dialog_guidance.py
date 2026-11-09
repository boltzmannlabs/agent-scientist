"""Missing-input dialogs must not depend on a profile loading a particular skill."""

from types import SimpleNamespace


def test_dialog_guidance_follows_the_session_tool_surface():
    from agent.system_prompt import _tool_guidance_block

    agent = SimpleNamespace(valid_tool_names={'clarify'})
    guidance = _tool_guidance_block(agent)
    assert guidance, 'An interactive input tool needs shared guidance, even with no skills loaded'
    assert 'clarify' in guidance and 'choices' in guidance
    agent.valid_tool_names = set()
    assert _tool_guidance_block(agent) is None
