# Native runtime launch

`runtime_launch.py` embeds the existing Agent Scientist SDK using an actual Python
script, an explicit isolated `SCI_HOME`, and an already PM-prepared interpreter.
It does not provision dependencies, copy credentials or install a user profile.

The earlier startup failure had two causes:

- Native bootstrap treated an unprepared isolated installation as owing source
  dependency/build completion, so import triggered substantial preparation.
- Its restart path interprets a stdin script's `sys.argv[0] == "-"` as a file and
  attempted to execute `/tmp/-`.

Use a real `.py` file. The launcher sets the supported
`SCI_DISABLE_LAZY_INSTALLS=1` embedding option to prevent automatic installation
or source-update completion. It does not fabricate `__SCI_ACTIVATED`: inherited
activation/test-interpreter markers are removed when changing profile. The normal
SDK bootstrap still activates a committed dependency selection; a PM-built
independent venv retains its own dependencies when the isolated home has none.
If the prepared interpreter lacks requirements, repair through the SDK's supported
PM workflow separately; this launcher does not download or install anything.

```python
from workflow.runtime_launch import run_script

result = run_script(
    host_root="/path/to/agent-scientist-sdk",
    interpreter="/path/to/already-prepared/bin/python",
    sci_home="/private/existing/isolated-home",
    script="/private/path/actual_script.py",
    timeout_seconds=180,
)
```

Keep captured output private. Do not put API keys in command-line arguments.
Credentials, when needed, must be resolved through supported owning-profile APIs
and kept in memory. An isolated profile does not automatically inherit another
profile's authorization. The launcher itself does not resolve or transfer keys.
A process timeout does not cancel an accepted remote scientific job.

## Actual qualification on 4 November 2026

- Real SDK `AIAgent` construction succeeded in a new isolated home with empty
  tool grants, no inference and no automatic preparation output.
- A separate actual native `delegate_task(tasks=[{"specialist": ...}])` check ran
  one engineering-only named child using the existing configured
  `gpt-6.1-sol` / `openai-codex` route.
- The child completed with the requested ready JSON: one reported API call,
  934 input tokens, 21 output tokens, 6.01 seconds; no truncation.
- No scientific tools/jobs were used. No credential files were copied. The owning
  profile's `auth.json` hash was unchanged. The private runtime profile contained
  only the reviewed engineering role and nonsecret local configuration.
- This proves actual named-child startup/inference. It does not demonstrate
  molecular reasoning, skill integration or optimization improvement.

Private receipts are retained under the user's state directory, outside this
repository. Two portable behavioral tests verify isolated child environment,
real-script admission and literal argument transport without a shell.
