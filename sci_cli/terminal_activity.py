"""Activity in the terminal title, without repainting the idle conversation."""

import os
import time


class TerminalActivity:
    def __init__(self):
        self.title = None
        self.progress = None

    def update(self, cli):
        app = cli._app
        output = app.output
        if not app.is_running or not output.stdout or not output.stdout.isatty():
            return
        waiting = any(getattr(cli, name, None) for name in (
            '_approval_state', '_clarify_state', '_secret_state', '_sudo_state',
        ))
        side = getattr(cli, '_side_controller', None)
        busy = (getattr(cli, '_agent_running', False) or getattr(cli, '_command_running', False)
                or bool(side and side.running))
        frames = ('●··', '·●·', '··●', '·●·')
        marker = '?' if waiting else frames[int(time.monotonic() / 0.6) % len(frames)] if busy else '·'
        # VS Code's native tab spinner listens to progress, not window-title text.
        native_progress = os.environ.get('TERM_PROGRAM') == 'vscode'
        if native_progress:
            progress = 3 if busy and not waiting else 0
            if progress != self.progress:
                output.write_raw(f'\033]9;4;{progress};\007')
                output.flush()
                self.progress = progress
        title = 'Agent Scientist' if native_progress else f'{marker} Agent Scientist'
        if title == self.title:
            return
        if self.title is None:
            output.write_raw('\033[22;2t')  # Save the shell's window title where supported.
        output.set_title(title)
        output.flush()
        self.title = title

    def restore(self, output):
        if self.progress is not None:
            output.write_raw('\033]9;4;0;\007')
            output.flush()
            self.progress = None
        if self.title is not None:
            output.write_raw('\033[23;2t')
            output.flush()
            self.title = None
