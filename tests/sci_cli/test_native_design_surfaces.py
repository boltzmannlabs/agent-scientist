"""Native design surfaces stay profile-scoped and keep the composer above status."""

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_composer_uses_advertised_truecolor_and_respects_explicit_overrides(monkeypatch):
    import cli
    from prompt_toolkit.output import ColorDepth
    from sci_cli import cli_tui_runtime_mixin as runtime

    monkeypatch.setattr(cli, "_select_classic_cli_pt_output", lambda _: None)
    monkeypatch.setattr(runtime.pet_render, "supports_kitty_placeholders", lambda: False)
    monkeypatch.setattr(runtime, "Application", lambda **kwargs: SimpleNamespace(**kwargs))
    view = SimpleNamespace(_vim_mode=False)
    for advertised, override, expected in (
        ("truecolor", None, ColorDepth.DEPTH_24_BIT),
        ("24bit", None, ColorDepth.DEPTH_24_BIT),
        ("", None, None),
        ("truecolor", "DEPTH_8_BIT", None),
    ):
        monkeypatch.setenv("COLORTERM", advertised)
        if override:
            monkeypatch.setenv("PROMPT_TOOLKIT_COLOR_DEPTH", override)
        else:
            monkeypatch.delenv("PROMPT_TOOLKIT_COLOR_DEPTH", raising=False)
        app = runtime.CLITuiRuntimeMixin._tui_build_application(view, None, None, None)
        assert getattr(app, "color_depth", None) == expected


def test_paired_surfaces_follow_the_profile_without_leaking_into_custom_skins(
    tmp_path, monkeypatch
):
    import cli
    from rich.console import Console
    from rich.style import Style
    from sci_cli import skin_engine
    from sci_cli.cli_render import assistant_message_panel
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.skin_defaults import DEFAULT_SKIN_NAME
    from sci_cli.config import atomic_config_replace

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
    monkeypatch.setenv("SCI_LIGHT", "1")
    monkeypatch.setenv("SCI_TUI_LIGHT", "1")
    monkeypatch.setenv("SCI_TUI_THEME", "light")
    monkeypatch.setenv("SCI_TUI_BACKGROUND", "#ffffff")
    monkeypatch.setattr(skin_engine, "_active_skin_by_home", {})
    a, b = tmp_path / ".sci/profiles/a", tmp_path / ".sci/profiles/b"
    a.mkdir(parents=True)
    (a / "skins").mkdir()
    # Previously installed default skins lack the new canvas field. They
    # inherit it without rewriting the user's file or affecting custom skins.
    (a / "skins/neon-theme.yaml").write_text("name: neon-theme\ncolors: {}\n")
    (b / "skins").mkdir(parents=True)
    (b / "skins/custom.yaml").write_text(
        "name: custom\ncolors:\n  banner_text: '#dddddd'\n"
        "light_colors:\n  banner_text: '#202020'\n"
    )
    atomic_config_replace(
        a / "config.yaml", {"display": {"skin": DEFAULT_SKIN_NAME, "color_mode": "light"}}
    )
    atomic_config_replace(b / "config.yaml", {"display": {"skin": "custom"}})
    expected = []
    for home, name in ((a, DEFAULT_SKIN_NAME), (b, "custom"), (a, DEFAULT_SKIN_NAME)):
        with profile_scope(home):
            skin_engine.set_active_skin(name)
            skin = skin_engine.get_active_skin()
            styles = skin_engine.get_prompt_toolkit_style_overrides()
            if name == "custom":
                assert not skin.get_color("terminal_bg")
                assert styles["input-area"] == ""
                assert skin.get_color("banner_text") == "#dddddd"
                continue
            paired = skin.colors
            assert f"bg:{paired['terminal_elevated']}" in styles["input-area"]
            assert paired["banner_text"] in styles["input-area"]
            assert paired["status_bar_bg"] in styles["status-bar"]
            assert f"bg:{paired['terminal_elevated']}" in styles["clarify-choice"]
            panel = assistant_message_panel("Fixture answer", width=60)
            from sci_cli.banner_science import science_welcome_panel
            for width in (32, 100):
                welcome = science_welcome_panel(
                    skin=skin, profile=home.name, model="test-model", provider="test-provider",
                    cwd="/workspace/[private]", tool_count=2, skill_count=3, width=width,
                )
                rendered = StringIO()
                Console(file=rendered, width=width).print(welcome)
                text = rendered.getvalue()
                assert "[private]" in text
                assert "Profile" in text and home.name in text
                assert "agent-sci" in text
                assert "Agent Scientist" in text and "☤ Agent Scientist" not in text
                assert all(len(line) <= width for line in text.splitlines())
            assert (
                Style.parse(panel.style).bgcolor.get_truecolor().hex.upper()
                == paired["terminal_bg"].upper()
            )
            output = StringIO()
            Console(
                file=output, width=60, force_terminal=True, color_system="truecolor"
            ).print(panel)
            assert "Fixture answer" in output.getvalue()
            expected.append(styles)
    assert expected[0] == expected[1]


def test_terminal_defaults_follow_the_skin_and_restore_only_when_owned(monkeypatch):
    from sci_cli.skin_defaults import DEFAULT_COLORS
    from sci_cli.skin_engine import SkinConfig
    from sci_cli.terminal_appearance import TerminalAppearance

    class Terminal(StringIO):
        def isatty(self):
            return True

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    registered = []
    monkeypatch.setattr("sci_cli.terminal_appearance.atexit.register", registered.append)
    out = Terminal()
    view = TerminalAppearance(out)
    view.restore()
    assert not out.getvalue()
    for palette in (DEFAULT_COLORS, DEFAULT_COLORS):
        view.apply(SkinConfig("fixture", colors=palette))
        assert out.getvalue().endswith(
            f"\033]11;{palette['background']}\007\033]10;{palette['banner_text']}\007"
        )
    view.apply(SkinConfig("custom", colors={"banner_text": "#FFFFFF"}))
    assert out.getvalue().endswith("\033]111\007\033]110\007")
    count = len(out.getvalue())
    registered[0]()
    assert len(out.getvalue()) == count and len(registered) == 1
    pipe = StringIO()
    TerminalAppearance(pipe).apply(SkinConfig("fixture", colors=DEFAULT_COLORS))
    assert not pipe.getvalue()


def test_secure_panel_and_account_card_preserve_literal_data_without_exposing_secrets(monkeypatch):
    from cli import SciCLI
    from plugins.boltzmann.authentication import AuthenticationResult
    from sci_cli.boltzmann_setup import result_display

    view = SciCLI.__new__(SciCLI)
    queue = object()
    view._secret_state = {"var_name": "BOLTZMANN_API_KEY", "prompt": "API key (hidden)",
                          "response_queue": queue}
    before = view._secret_state.copy()
    fragments = view._get_secret_display_fragments()
    text = "".join(value for _, value in fragments)
    assert "Boltzmann login" in text and "https://app.boltzmann.co/user-profile" in text
    assert view._secret_state == before
    result = AuthenticationResult(True, "Verified", "[bold]@example.invalid", 0, 12.5)
    summary = result.account_summary()
    styled = result_display(summary)
    assert styled.plain == summary
    assert "[bold]@example.invalid" in styled.plain and "Credits: 0" in styled.plain
    assert "Frozen credits: 12.5" in styled.plain
    assert styled.spans
    from rich.console import Console
    import os
    for width in (32, 100):
        monkeypatch.setattr("sci_cli.cli_render.shutil.get_terminal_size", lambda *args: os.terminal_size((width, 40)))
        fragments = view._get_secret_display_fragments()
        rows = "".join(value for _, value in fragments).splitlines()
        assert all(len(row) <= width for row in rows)
        assert "https://app.boltzmann.co/user-profile" in "".join(row.strip("│ ") for row in rows)
        assert any("secret-link" in style for style, _ in fragments)
    from sci_cli.skin_engine import get_active_skin
    index = styled.plain.index("Credits:")
    assert styled.get_style_at_offset(Console(), index).bgcolor is not None
    assert get_active_skin().get_color("account_bg")


def test_native_footer_renders_composer_before_status_at_narrow_and_wide_widths():
    from cli import SciCLI
    from prompt_toolkit.application import Application
    from prompt_toolkit.application.current import set_app
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.mouse_handlers import MouseHandlers
    from prompt_toolkit.layout.screen import Screen, WritePosition
    from prompt_toolkit.output import DummyOutput
    from sci_cli.cli_footer_split import FooterSplit

    stub = SciCLI.__new__(SciCLI)
    stub._get_extra_tui_widgets = lambda: []
    names = (
        "sudo_widget",
        "secret_widget",
        "connection_widget",
        "approval_widget",
        "slash_confirm_widget",
        "clarify_widget",
        "model_picker_widget",
        "command_palette_widget",
        "spinner_widget",
        "spacer",
        "status_bar",
        "input_rule_top",
        "image_bar",
        "input_area",
        "input_rule_bot",
        "voice_status_bar",
        "completions_menu",
    )
    widgets = {name: Window(height=0) for name in names}
    widgets["input_area"] = Window(FormattedTextControl("COMPOSER"), height=2)
    widgets["status_bar"] = Window(
        FormattedTextControl("[omics] STATUS"), height=1, wrap_lines=False
    )
    children = stub._build_tui_layout_children(**widgets)
    assert children.index(widgets["input_area"]) < children.index(widgets["status_bar"])
    for width in (30, 100):
        root = FooterSplit(children)
        app = Application(layout=Layout(root), output=DummyOutput())
        screen = Screen()
        with set_app(app):
            root.write_to_screen(
                screen, MouseHandlers(), WritePosition(0, 0, width, 4), "", True, None
            )
        rows = [
            "".join(screen.data_buffer[y][x].char for x in range(width))
            for y in range(4)
        ]
        composer = next(i for i, text in enumerate(rows) if "COMPOSER" in text)
        status = next(i for i, text in enumerate(rows) if "STATUS" in text)
        assert status > composer


def test_question_cards_fit_terminal_and_preserve_raw_selection(monkeypatch):
    import os
    from queue import Queue
    from unittest.mock import Mock
    from rich.cells import cell_len
    from cli import SciCLI

    view = SciCLI.__new__(SciCLI)
    view._clarify_freetext = False
    view._persist_prompt_summary = Mock()
    for width in (32, 110):
        monkeypatch.setattr('sci_cli.cli_render.shutil.get_terminal_size',
                            lambda *args: os.terminal_size((width, 40)))
        for choices in (["main — currently active", "omics", "Cancel"],
                        ["[selected] microscopy — 画像 analysis", "Done", "Clear selection"]):
            state = {"questions": [{"qid": "profile", "question": "Choose a profile or capability",
                                     "numbered_choices": True}],
                     "choices": choices, "selected": 0, "active": 0, "answers": {},
                     "allow_other": False, "response_queue": Queue()}
            view._clarify_state = state
            fragments = view._get_clarify_display_fragments()
            rows = ''.join(text for _, text in fragments).splitlines()
            assert all(cell_len(row) <= width for row in rows)
            import re
            assert not re.search(r'\b[1-9]\. ', '\n'.join(rows))
            selected = [text for style, text in fragments if style == 'class:clarify-selected']
            assert selected and all(cell_len(text) == cell_len(selected[0]) for text in selected)
            view._clarify_batch_enter(state)
            assert state['response_queue'].get_nowait() == {'profile': choices[0]}


def test_legacy_light_skin_cannot_restore_a_light_native_canvas():
    from sci_cli.skin_defaults import DEFAULT_COLORS
    from sci_cli.skin_engine import SkinConfig

    skin = SkinConfig('legacy-light', colors={'background': '#FFFFFF', 'banner_text': '#202020'})
    for key in ('background', 'terminal_bg', 'banner_text', 'completion_menu_current_bg'):
        assert skin.get_color(key) == DEFAULT_COLORS[key]
    skin.dark_colors = {'background': '#080408', 'banner_text': '#FFE3ED'}
    assert skin.get_color('banner_text') == skin.dark_colors['banner_text']
