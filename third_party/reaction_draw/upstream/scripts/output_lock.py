# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Gopi Krishna; Agent Scientist portable output locking.
"""Native nonblocking output-file lock; closing the handle releases ownership."""
from __future__ import annotations

import os


def acquire(handle):
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
