"""Output-pattern failure hints for terminal and Python execution.

Extends the exit-code semantics table in ``terminal_tool`` with a bounded scan of failed-command
output mapped to ONE short, actionable recovery hint. Rules: only fires on non-zero exit; first
match wins. Terminal-specific rules scan the first ``_SCAN_CHARS``; shared schema rules
scan a bounded head and tail so a final traceback survives verbose stdout. Hints state
the next action without changing the failure result; pure functions, no I/O or config reads.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

_SCAN_CHARS = 4000

# Shared with execute_code's local and remote result builders. A script can
# fail after writing valid outputs: guide inspection/repair, never replay it.
_SCHEMA_FAILURE_HINTS = (
    (re.compile(r"(?m)^KeyError:"),
     "Inspect the actual record's keys, schema and required field types before correcting the reader. "
     "Use canonical fields; do not replace missing required data with zero or an empty collection."),
    (re.compile(r"(?m)^(?:sqlite3\.)?OperationalError: no such (?:column|table):"),
     "Use the application's existing history/status/usage interfaces when available. Otherwise inspect "
     "the actual database schema read-only before correcting the query; do not rename database columns to fit it."),
    (re.compile(r"(?m)^(?:\w+(?:\.\w+)*Error:\s*)?New fields require existing final field anchor in changes"),
     "Inspect the update helper and current record, validate its insertion/anchor contract before writing, "
     "and preserve required unchanged bytes. Use an atomic update with a current-revision check."),
    (re.compile(r"(?m)^AssertionError(?::|\r?$)"),
     "Inspect the assertion's expected and actual values. For message bookkeeping, prefer persisted session "
     "and message/event identities; if text matching is necessary, normalize only permitted line-ending "
     "differences and reject ambiguous matches. Do not normalize scientific inputs to make an assertion pass."),
)
_EXECUTION_RECOVERY = (
    " A failed operation may already have completed earlier steps. Inspect existing artifacts, receipts "
    "and job outcomes first; do not replay the whole script or repeat accepted/uncertain scientific jobs. "
    "Repair only the failed or unfinished step, verify it, then continue the user's authorized task without "
    "asking them to debug the script or type Continue. Do not repeat unchanged failures; respect existing "
    "retry and iteration limits. Count each execution once; unavailable usage stays unknown. Existing "
    "permissions still apply: do not bypass approval, change providers, or install software without required "
    "authorization. Report a specific blocker if evidence, access or authorization is missing."
)


def schema_failure_hint(output: str) -> Optional[str]:
    """Bounded, evidence-neutral guidance for data/metadata script exceptions."""
    text = output or ""
    window = text if len(text) <= _SCAN_CHARS else text[:_SCAN_CHARS // 2] + "\n" + text[-_SCAN_CHARS // 2:]
    for pattern, message in _SCHEMA_FAILURE_HINTS:
        if pattern.search(window):
            return message + _EXECUTION_RECOVERY
    return None


def execution_failure_hint(output: str, *, detail: Optional[str] = None) -> str:
    """General recovery when no known signature matches; never guess the cause."""
    if detail:
        return detail + _EXECUTION_RECOVERY
    return schema_failure_hint(output) or (
        "Inspect the actual error, relevant code, inputs and execution environment before making a "
        "targeted correction. If diagnostic output is absent, inspect the exit status and available logs; "
        "do not invent an error cause." + _EXECUTION_RECOVERY
    )


def _regex_hint(pattern: str, message: str | Callable[[str], str], flags: int = 0) -> Callable[[str, str], Optional[str]]:
    """Hint firing when ``pattern`` matches; ``{0}`` = first group, or ``message(group1)``."""
    rx = re.compile(pattern, flags)

    def hint(command: str, output: str) -> Optional[str]:
        m = rx.search(output)
        if m:
            return message(m.group(1)) if callable(message) else message.format(*m.groups())
        return None

    return hint


# Most `command not found` hits are bare `python` on python3-only distros.
_MISSING_COMMAND_HINTS = {
    "python": "This system has no bare `python` — use `python3`, or the project venv's "
              "interpreter (e.g. .venv/bin/python).",
    "pip": "This system has no bare `pip` — use `pip3`, `python3 -m pip`, or the project venv's "
           "pip (e.g. .venv/bin/pip).",
}


def _missing_command_hint(missing: str) -> str:
    return _MISSING_COMMAND_HINTS.get(missing) or (
        f"`{missing}` is not installed or not on PATH. Verify with `which {missing}`; install it "
        "or use an absolute path instead of retrying the same command.")


# Ordered by production frequency — first match wins.
_OUTPUT_HINTS: list[Callable[[str, str], Optional[str]]] = [
    # gh version drift; gh already prints the valid field list.
    _regex_hint(r'Unknown JSON field: "?(\w+)',
                "The installed gh does not support the JSON field '{0}'. The valid field list is "
                "printed in the output above — retry using only fields from that list."),
    _regex_hint(r"^CONFLICT |Automatic merge failed|needs merge",
                "Git merge conflict. Do not retry this command. Resolve the conflicted files "
                "listed above (edit, then `git add`), then continue (`git rebase --continue` / "
                "commit the merge) — or abort with `--abort`.", re.M),
    _regex_hint(r"(?:bash: line \d+: |bash: |sh: \d*:? ?)?([\w.+-]+): command not found",
                _missing_command_hint),
    # Almost always a venv-activation slip, not a missing dependency.
    _regex_hint(r"(?:ModuleNotFoundError|ImportError): No module named '?([\w.]+)",
                "Python cannot import '{0}'. Most often the wrong interpreter is running: "
                "activate the project venv (e.g. `source .venv/bin/activate`) or invoke its python "
                "directly. Only pip install if the package is genuinely absent from that venv."),
    _regex_hint(r"(?:fatal|error):.*?'([^']+)' already exists",
                "'{0}' already exists — retrying unchanged will keep failing. Reuse it, choose "
                "another name, or delete it first if it is genuinely stale."),
    _regex_hint(r"API rate limit|was submitted too quickly",
                "GitHub API rate limit hit — immediate retries will keep failing. Continue with "
                "other work and retry this operation later."),
    _regex_hint(r"Permission denied|EACCES",
                "Permission denied. Check ownership/mode of the target path (`ls -la`); prefer a "
                "user-writable location. Only escalate to sudo if the task genuinely requires it."),
]

# Exit-code-only hints for codes the terminal_tool semantics table does not
# cover per-command. Checked after output patterns.
_EXIT_CODE_HINTS: dict[int, str] = {
    126: "Exit 126: the file was found but is not executable — `chmod +x` it or invoke it via its interpreter (e.g. `bash script.sh`).",
    137: "Exit 137: the process was SIGKILLed — usually out-of-memory or an external kill. Reduce memory use or check `dmesg | tail` before retrying.",
    124: "Exit 124: the command hit its timeout. Raise timeout= for a longer foreground wait. Only use background=true when the user requests independent background work.",
}


# Masked-success detection: `cargo build 2>&1 | tail -20` exits with tail's 0
# (no pipefail) and `cargo build || echo FAILED` with echo's 0, so the model can
# conclude a build passed while the output says it failed. Conservative: BOTH a
# masking command shape AND a strong tool-specific failure shape must hold, and
# read-only heads (`grep ... | head`) are excluded because their output
# legitimately contains error text. Advisory only — exit_code is never changed.

# Consumers whose exit status says nothing about the upstream command.
_PASSTHROUGH_CONSUMERS = r"(?:tail|head|cat|tee|less|more|wc|sort|uniq)"

# Command shapes that swallow an upstream status -> warning, checked in order.
_MASKING_SHAPES: list[tuple[re.Pattern[str], str]] = [
    # Top-level `... | tail -20` (not `||`); consumer must be the LAST segment.
    (re.compile(r"(?<!\|)\|(?!\|)\s*" + _PASSTHROUGH_CONSUMERS + r"\b[^|]*$"),
     "exit_code 0 here is the status of the last pipeline command (tail/head/cat/...), NOT of "
     "the command before the pipe — and the output contains failure indicators. Treat this run "
     "as FAILED until proven otherwise: re-run the command WITHOUT the pipe (output is "
     "auto-truncated and the full text is saved to a file, so piping through tail/head is never "
     "needed) to get the real exit code."),
    # `cmd || echo ...` / `cmd || true` — fallback swallows the failure status.
    (re.compile(r"\|\|\s*(?:echo\b|printf\b|true\b|:\s|:$)"),
     "exit_code 0 here is the status of the `||` fallback (echo/true), NOT of the command before "
     "it — and the output contains failure indicators. Treat this run as FAILED until proven "
     "otherwise: re-run the command bare to get its real exit code."),
]

_READONLY_HEADS = frozenset({
    "grep", "rg", "ag", "find", "ls", "cat", "head", "tail", "jq", "awk",
    "sed", "strings", "zcat", "journalctl", "dmesg", "echo", "printf"})

# Strong failure shapes keyed to specific tools so that error-mentioning
# *content* (diffs, logs, commit messages) rarely matches.
_FAILURE_SHAPES = re.compile(
    r"(?:"
    r"error\[E\d+\]"                          # rustc
    r"|error: could not compile"              # cargo
    r"|error: aborting due to"                # rustc summary
    r"|Traceback \(most recent call last\)"   # python
    r"|(?m:^(?:=+ )?\d+ failed)"              # pytest summary
    r"|(?m:^FAILED (?:\S+::|\S+\.py))"        # pytest per-test lines
    r"|compilation terminated\."              # gcc/clang
    r"|npm ERR!"                              # npm
    r"|BUILD FAILED|Build FAILED"             # gradle/msbuild/echoed fallbacks
    r"|FAILED: "                              # ninja
    r"|(?m:^make(?:\[\d+\])?: \*\*\*)"        # make
    r")")


def _first_token(command: str) -> str:
    """Basename of the command head, skipping leading env-var assignments."""
    for tok in (command or "").strip().split():
        if "=" not in tok or tok.startswith(("=", "./", "/")):
            return tok.rsplit("/", 1)[-1]
    return ""


def annotate_masked_success(command: str, output: str) -> Optional[str]:
    """Warning note when an exit-0 result likely masks a failure (caller gates on exit 0)."""
    cmd = command or ""
    window = (output or "")[:_SCAN_CHARS]
    if (not cmd or not window or _first_token(cmd) in _READONLY_HEADS
            or not _FAILURE_SHAPES.search(window)):
        return None
    return next((note for rx, note in _MASKING_SHAPES if rx.search(cmd)), None)


def annotate_failure(command: str, exit_code: int, output: str) -> Optional[str]:
    """Return one short recovery hint for a failed command, or None (exit 0)."""
    if exit_code <= 0 or exit_code == 130:
        return None
    if recovery := schema_failure_hint(output):
        return recovery
    window = (output or "")[:_SCAN_CHARS]
    for fn in _OUTPUT_HINTS if window else ():
        try:
            if hint := fn(command or "", window):
                return execution_failure_hint(output, detail=hint)
        except Exception:
            continue
    return _EXIT_CODE_HINTS.get(exit_code) or execution_failure_hint(output)
