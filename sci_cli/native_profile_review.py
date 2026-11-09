"""Temporary profile setup resources, separate from the live profile's runtime."""

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile


@contextmanager
def review_workspace(ui, *, prefix):
    from sci_constants import sci_home_key
    from sci_cli.skill_add import Cancelled
    from sci_cli.skill_add_status import WizardInputTimeout
    from tools.mcp_tool_config import _close_mcp_stderr_logs

    scratch = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield scratch
    finally:
        # Discovery has already stopped its probe transport, but the parent log
        # handle is cached by profile. Windows cannot unlink that open file.
        _close_mcp_stderr_logs(scope=sci_home_key(scratch))
        while True:
            try:
                shutil.rmtree(scratch)
                break
            except OSError:
                ui.show(f"Temporary setup cleanup could not remove {scratch}. "
                        "This does not undo a saved profile or change the setup outcome. "
                        "The folder may contain staged credentials. Close any process using it "
                        "before retrying cleanup, or remove it manually later.")
                try:
                    action = ui.choose("Clean up temporary setup files?",
                                       ["Retry cleanup", "Keep temporary files for now"])
                except (Cancelled, KeyboardInterrupt, EOFError, WizardInputTimeout):
                    # Cleanup must not replace the original cancellation/error.
                    break
                if action != "Retry cleanup":
                    break
