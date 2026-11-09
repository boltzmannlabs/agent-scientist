"""Native question cards, shared by profile, capability, and setup workflows."""

def render_questions(self):
    """Batch (multi-question) clarify panel: "N questions" header, one status line per question
    (✓ answered → answer / ▸ active / · pending), and the active question's numbered choices
    (+ Other) expanded beneath its status line."""
    from cli import _panel_box_width, _wrap_panel_text
    from sci_cli.cli_tui_mixin import _Panel, _agent_name, _tn, _term_rows
    from agent.i18n import t
    state = self._clarify_state
    if not state:
        return []
    questions_list = state.get("questions") or []
    answers = state.get("answers") or {}
    answer_meta = state.get("answer_meta") or {}
    active = state.get("active", 0)
    choices = state.get("choices") or []
    selected = state.get("selected", 0)
    multi_select = state.get("multi_select", False)
    selected_indices = state.get("selected_indices", set()) if multi_select else set()
    freetext = self._clarify_freetext
    title = t("cli.tui.clarify_title", agent_name=_agent_name())
    header = _tn("cli.tui.clarify_question_count", len(questions_list))

    catalog = "Clear selection" in choices or "Clear matching" in choices
    spacious = not getattr(self, "compact", False) and _term_rows() >= 32

    def _status_rows(width):
        rows = []
        for idx, entry in enumerate(questions_list):
            answered = entry["qid"] in answers
            marker = "✓" if answered else ("" if len(questions_list) == 1 else ("▸" if idx == active else "·"))
            row_style = 'class:clarify-question' if idx == active else 'class:clarify-choice'
            for wrapped in _wrap_panel_text(f"{marker} {entry['question']}".strip(), width, subsequent_indent="  "):
                rows.append((row_style, wrapped))
            if answered:
                # Locked answer on its own line/color so it stays readable while Tab-walking.
                locked = answers[entry['qid']]
                answer = f"    {'—' if locked is None else locked}"
                for wrapped in _wrap_panel_text(answer, width, subsequent_indent="    "):
                    rows.append(('class:clarify-answer', wrapped))
            if idx != active:
                continue
            if spacious:
                rows.append(('class:clarify-choice', ""))
            for i, choice in enumerate(choices):
                cursor = ("❯" if i == selected and not freetext else " ") if multi_select else ("◉" if i == selected and not freetext else "○")
                cb = ("[x] " if i in selected_indices else "[ ] ") if multi_select else ""
                style = 'class:clarify-selected' if i == selected and not freetext else 'class:clarify-choice'
                display_choice = choice
                if catalog and " — " in choice:
                    checked = choice.startswith("[selected] ")
                    display_choice = choice.removeprefix("[selected] ")
                    cb = "[x] " if checked else "[ ] "
                    cursor = "❯" if i == selected else " "
                label = f"  {cursor} {cb}{display_choice}"
                for wrapped in _wrap_panel_text(label, width, subsequent_indent="      "):
                    rows.append((style, wrapped))
            if choices and state.get("allow_other", True):
                other_idx = len(choices)
                mid = ""
                if multi_select:
                    mid = f"{'[x]' if other_idx in selected_indices else '[ ]'} {mid}"
                # An earlier typed answer stays visible next to Other; Enter on it edits
                # (the composer is prefilled).
                other_text = (answer_meta.get(entry["qid"]) or {}).get("other_text") or ""
                other_suffix = t("cli.tui.clarify_other_answer", text=other_text) if other_text else None
                if freetext:
                    other_label = f"  ❯ {mid}" + (other_suffix or t("cli.tui.clarify_other_type_below"))
                    other_style = 'class:clarify-active-other'
                elif selected == other_idx:
                    other_label = f"  ❯ {mid}" + (other_suffix or t("cli.tui.clarify_other_type_answer"))
                    other_style = 'class:clarify-selected'
                else:
                    other_label = f"    {mid}" + (other_suffix or t("cli.tui.clarify_other_type_answer"))
                    other_style = 'class:clarify-choice'
                for wrapped in _wrap_panel_text(other_label, width, subsequent_indent="      "):
                    rows.append((other_style, wrapped))
            elif freetext:
                guidance = "  " + t("cli.tui.clarify_guidance")
                for wrapped in _wrap_panel_text(guidance, width):
                    rows.append(('class:clarify-active-other', wrapped))
        return rows

    preview_rows = _status_rows(60)
    box_width = _panel_box_width(title, [header] + [text for _, text in preview_rows], min_width=74, max_width=104)
    rows = _status_rows(max(8, box_width - 2))
    from sci_cli.picker_viewport import visible_panel_rows
    selected_row = next((i for i, (style, _) in enumerate(rows) if style == 'class:clarify-selected'), 0)
    rows = visible_panel_rows(state, rows, selected_row, panel_chrome=7 if spacious else 4)

    panel = _Panel('class:clarify-border', box_width, title, 'class:clarify-title')
    if spacious:
        panel.blank()
    panel.row('class:clarify-hint', header)
    if spacious:
        panel.blank()
    for style, text in rows:
        panel.row(style, text)
    if spacious:
        panel.blank()
    hint = '↑/↓ navigate · Space toggle · Enter confirm · Esc cancel' if multi_select else '↑/↓ choose · Enter confirm · Esc cancel'
    panel.row('class:clarify-hint', hint)
    return panel.close()
