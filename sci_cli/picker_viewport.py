"""Bound menu overlays by rendered rows, including wrapped choice descriptions."""


def visible_panel_rows(state, rows, selected_row, *, panel_chrome=4):
    from prompt_toolkit.application import get_app_or_none, get_app_session
    from sci_cli.cli_model_switch_mixin import CLIModelSwitchMixin

    app = get_app_or_none()
    output = app.output if app is not None else get_app_session().output
    offset, count = CLIModelSwitchMixin._compute_model_picker_viewport(
        selected_row, state.get('_row_scroll_offset', 0), len(rows), output.get_size().rows,
        reserved_below=6, panel_chrome=panel_chrome, min_visible=1)
    state['_row_scroll_offset'] = offset
    return rows[offset:offset + count]
