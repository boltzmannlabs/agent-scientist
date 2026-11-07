"""Select an existing CLI view without replacing either conversation's writer."""

import time


def open_views(cli):
    from sci_cli.side_commands import current

    views = [cli.session_id]
    side = current(cli)
    if side and not side.conversation.closed.is_set() and side.conversation.saved:
        views.append(side.conversation.id)
    return views


def select_view(cli, session_id):
    if session_id not in open_views(cli):
        return False
    from sci_cli.side_commands import current

    side = current(cli)
    if side and not side.conversation.closed.is_set():
        side.select(session_id == side.conversation.id)
    return True


def receive_selection(cli, selection):
    """Heartbeat delivery; acknowledge only after the UI loop selected the view."""
    if not selection or selection['id'] == getattr(cli, '_background_view_pending', None):
        return
    cli._background_view_pending = selection['id']

    def apply():
        selected = (time.monotonic() < selection['expires']
                    and select_view(cli, selection['session_id']))
        cli._background_view_ack = {'id': selection['id'], 'selected': bool(selected)}

    app = getattr(cli, '_app', None)
    if app and app.is_running:
        app.loop.call_soon_threadsafe(apply)
    else:
        cli._background_view_ack = {'id': selection['id'], 'selected': False}
