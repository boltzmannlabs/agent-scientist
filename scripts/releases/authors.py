"""Map commit authors to GitHub logins for release notes and attribution checks.

SCI-specific mappings live as one file per email under ``contributors/emails/``.
GitHub noreply identities resolve directly; unknown authors retain their git name.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ──────────────────────────────────────────────────────────────────────
# Directory-based mappings: contributors/emails/<email> → login
# ──────────────────────────────────────────────────────────────────────
CONTRIBUTORS_EMAILS_DIR = REPO_ROOT / "contributors" / "emails"


def _load_contributor_dir(directory: "Path | None" = None) -> dict:
    """Load one-file-per-email mappings from contributors/emails/.

    Filename = commit-author email, first non-comment line = GitHub login.
    Each mapping is a distinct file so additions do not conflict.
    """
    directory = directory or CONTRIBUTORS_EMAILS_DIR
    mapping = {}
    if not directory.is_dir():
        return mapping
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    mapping[path.name] = line.lstrip("@")
                    break
        except OSError:
            continue
    return mapping


# SCI contributor mappings; commit identity remains the fallback.
AUTHOR_MAP = _load_contributor_dir()


def resolve_author(name: str, email: str) -> str:
    """Resolve a git author to a GitHub @mention."""
    # Try email lookup first
    gh_user = AUTHOR_MAP.get(email)
    if gh_user:
        return f"@{gh_user}"

    # Try noreply pattern
    noreply_match = re.match(r"(\d+)\+(.+)@users\.noreply\.github\.com", email)
    if noreply_match:
        return f"@{noreply_match.group(2)}"

    # Try username@users.noreply.github.com
    noreply_match2 = re.match(r"(.+)@users\.noreply\.github\.com", email)
    if noreply_match2:
        return f"@{noreply_match2.group(1)}"

    # Fallback to git name
    return name
