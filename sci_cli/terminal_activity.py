"""Activity in the terminal title, without repainting the idle conversation."""

import os
import time


class TerminalActivity:
    def __init__(self):
        self.title = None
        self.progress = None
        self.attachment = None
        self.viewer_owned = False
        self.saved_title = False

    def update(self, cli):
        app = cli._app
        output = app.output
        if not app.is_running or not output.stdout or not output.stdout.isatty():
            return
        # A persistent worker can outlive several different terminal viewers.
        # Use attachment metadata without changing its environment or prompt.
        self.viewer_owned = (getattr(cli, '_background_managed', False)
                             and hasattr(cli, '_background_terminal_activity'))
        terminal = getattr(cli, '_background_terminal_activity', None) if self.viewer_owned else None
        if self.viewer_owned and terminal is None:
            self.title = self.progress = self.attachment = None
            return
        if terminal is not None and terminal['id'] != self.attachment:
            self.attachment = terminal['id']
            self.title = self.progress = None  # Reassert even an unchanged busy/idle state.
        waiting = any(getattr(cli, name, None) for name in (
            '_approval_state', '_clarify_state', '_secret_state', '_sudo_state',
        ))
        side = getattr(cli, '_side_controller', None)
        busy = (getattr(cli, '_agent_running', False) or getattr(cli, '_command_running', False)
                or bool(side and side.running))
        frames = ('●··', '·●·', '··●', '·●·')
        marker = '?' if waiting else frames[int(time.monotonic() / 0.6) % len(frames)] if busy else '·'
        # VS Code's native tab spinner listens to progress, not window-title text.
        program = terminal['program'] if terminal is not None else os.environ.get('TERM_PROGRAM')
        native_progress = program == 'vscode'
        if native_progress:
            progress = 3 if busy and not waiting else 0
            if progress != self.progress:
                output.write_raw(f'\033]9;4;{progress};\007')
                output.flush()
                self.progress = progress
        # VS Code already displays the native spinner beside the title.
        title = 'Agent Scientist' if native_progress else f'{marker} Agent Scientist'
        if title == self.title:
            return
        if not self.viewer_owned and not self.saved_title:
            output.write_raw('\033[22;2t')  # Save the shell's window title where supported.
            self.saved_title = True
        output.set_title(title)
        output.flush()
        self.title = title

    def restore(self, output):
        if self.progress is not None and not self.viewer_owned:
            output.write_raw('\033]9;4;0;\007')
            output.flush()
        if self.saved_title:
            output.write_raw('\033[23;2t')
            output.flush()
        self.title = self.progress = self.attachment = None
        self.saved_title = False
