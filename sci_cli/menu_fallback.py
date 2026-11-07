"""Arrow-key menus for interactive terminals where native curses cannot initialize.

Uses the same actions, search and navigation contracts as the curses renderer.
No dependency installation or configuration changes happen while a menu is open.
"""
from __future__ import annotations


def run_keyboard_menu(*, title, labels, initial_cursor, render_row, on_action,
                      cancel_value, description='', searchable=False, search_labels=None,
                      status=None, multiple=False):
    from prompt_toolkit.application import Application
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from sci_cli.curses_ui import (
        _KEEP, _NUMBERED_BACK_ENABLED, MenuNavigationEvent, _filter_indices,
        _move_filtered_cursor, _notify_scoped_navigation, _reconcile_cursor,
    )
    from sci_cli.skin_engine import get_active_skin

    cursor = initial_cursor
    query = ''
    searching = False
    bindings = KeyBindings()

    def visible():
        return _filter_indices(search_labels or labels, query) if searchable else list(range(len(labels)))

    def reconcile():
        nonlocal cursor
        cursor, position = _reconcile_cursor(visible(), cursor)
        return position

    def rows():
        reconcile()
        result = []
        for index in visible():
            if result:
                result.append(('', '\n'))
            result.append(('class:selected' if index == cursor else '', render_row(index, index == cursor)))
        return result or [('', '  No matches')]

    def finish(event, action):
        try:
            if action == 'back':
                _notify_scoped_navigation(MenuNavigationEvent.BACK)
            elif action in {'cancel', 'interrupt'}:
                _notify_scoped_navigation(MenuNavigationEvent.CANCEL)
            outcome = on_action(action, cursor)
        except (Exception, KeyboardInterrupt) as exc:
            # Setup's back/cancel exceptions must leave the Application before
            # the owning wizard changes sections; never open PT's error prompt.
            event.app.exit(exception=exc)
            return
        if outcome is not _KEEP:
            event.app.exit(result=outcome)

    @bindings.add('up')
    @bindings.add('down')
    def move(event):
        nonlocal cursor
        position = reconcile()
        cursor = _move_filtered_cursor(visible(), cursor, position, -1 if event.key_sequence[0].key == 'up' else 1)

    @bindings.add('enter')
    def select(event):
        if visible():
            reconcile()
            finish(event, 'select')

    @bindings.add(' ')
    def toggle(event):
        nonlocal query
        if searching:
            query += ' '
        elif visible():
            reconcile()
            finish(event, 'toggle')

    @bindings.add('escape', eager=True)
    def cancel(event):
        nonlocal query, searching
        if searching:
            query, searching = '', False
        else:
            finish(event, 'cancel')

    @bindings.add('c-c')
    def interrupt(event):
        finish(event, 'interrupt')

    @bindings.add('left')
    def back(event):
        if _NUMBERED_BACK_ENABLED.get() and not searching:
            finish(event, 'back')

    @bindings.add('/')
    def search(event):
        nonlocal searching, query
        if searching:
            query += '/'
        elif searchable:
            searching = True

    @bindings.add('backspace')
    def erase(event):
        nonlocal query
        if searching:
            query = query[:-1]

    @bindings.add('c-u')
    def clear(event):
        nonlocal query
        if searching:
            query = ''

    @bindings.add('<any>')
    def text(event):
        nonlocal query, cursor
        value = event.data
        if searching:
            query += value
        elif value in {'j', 'k'}:
            position = reconcile()
            cursor = _move_filtered_cursor(visible(), cursor, position, 1 if value == 'j' else -1)
        elif value == 'q':
            finish(event, 'cancel')

    def header():
        hint = ('SPACE toggle  ENTER confirm' if multiple else 'ENTER/SPACE select')
        if searchable:
            hint += '  / search'
        hint += '  ESC cancel'
        if _NUMBERED_BACK_ENABLED.get():
            hint += '  ← previous'
        return [('class:title', title + '\n'), ('class:hint', '↑↓ navigate  ' + hint)]

    def footer():
        if searching:
            return 'Search: ' + query
        return status() if status else ''

    skin = get_active_skin()

    def style_color(role):
        from rich.color import Color
        value = skin.get_color(role)
        if not value or value == 'default':
            return ''
        rgb = Color.parse(value).get_truecolor()
        return f'#{rgb.red:02x}{rgb.green:02x}{rgb.blue:02x}'

    style = Style.from_dict({
        'title': 'bold ' + style_color('banner_title'),
        'hint': style_color('hint_text'),
        'selected': 'reverse',
    })
    control = FormattedTextControl(rows, focusable=True, get_cursor_position=lambda: Point(0, reconcile()))
    panes = [Window(FormattedTextControl(header), height=2)]
    if description:
        panes.append(Window(FormattedTextControl(description), height=min(3, len(description.splitlines()))))
    panes.extend([Window(control, wrap_lines=False), Window(FormattedTextControl(footer), height=1)])
    app = Application(layout=Layout(HSplit(panes), focused_element=control),
                      key_bindings=bindings, style=style, full_screen=True)
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        _notify_scoped_navigation(MenuNavigationEvent.CANCEL)
        return cancel_value
