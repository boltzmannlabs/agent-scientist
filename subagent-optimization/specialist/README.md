# Molecular Investigation Specialist — local development version

One reasoning role recommends the next approved, untried CReM library from a
supplied small-molecule investigation. It explains the hypothesis, supporting
pairs, counterexamples, competing interpretation and what would reverse its
choice. It may agree with the simple baseline or abstain.

This is a **conditional first study**, requiring at least two scientifically
meaningful approved choices. It does not curate a library for every target.
General fragment sources may support different tasks; target-specific evaluation
remains separate. Different filenames, hashes or parsed sets do not alone establish
a useful scientific distinction. If only one sensible choice remains, the adapter
does not spend a model call on this role. Scientific usefulness is untested.

## Components

- [definition.json](definition.json): native saved-specialist definition, disabled
  pending destination review. Instructions are stored once in this file. No tools,
  skills, source locations, child grants or credentials are selected.
- [advisor.py](advisor.py): host-side packet preparation and response checks. It
  reuses the existing baseline's admission checks, eligible menu and arithmetic.
- [fixtures.py](fixtures.py) and [demo.py](demo.py): artificial records and a canned
  answer, explicitly representing no molecules, predictions or model reasoning.
- [test_native.py](test_native.py): separate real-host integration canary with
  temporary profile state and a loopback HTTP response fixture.

## Flow and ownership

```text
Authoritative task + admitted results + reviewed chemistry/library notes
    -> host checks stopping state, pending attempts and remaining choices
    -> focused, immutable JSON packet with all supplied cohort evidence
    -> native delegate_task(tasks=[assignment["request"]], parent_agent=parent)
    -> named child returns an advisory JSON object
    -> host refreshes source and checks citations, shape and selected action
    -> main agent decides whether to execute through its existing connector
    -> environment imports actual results and evaluates the unchanged task
```

The specialist receives no scientific execution tools. The native saved-specialist
runtime applies an exact empty tool grant in the inspected checkout; ordinary
temporary delegation has different inheritance semantics. This is not an OS-level
sandbox claim. The specialist maintains no campaign state, submits no jobs and
does not implement another property model, parser or scoring function.

## Context and repeated work

`prepare(source)` accepts exactly five host-owned sections: `task`, `libraries`,
`batches`, `chemistry`, `resource_summary`. The baseline input schema is reused.
Chemical notes add reference/context descriptions, versioned family descriptions,
pair descriptions bound to exact row hashes, and library rationales/limitations
bound to action signatures. Read [data-readiness.md](../research/data-readiness.md)
for the actual SME inputs. Review references are host assertions, not authenticated
approval. Do not provide holdout answers, credentials or unrelated private data.

The packet retains exact task rules, all supplied batches including negative and
multi-edit records, resource unknowns, all current library entries, reviewed notes,
admissible pair IDs and the two deterministic baselines. It does not send the
parent's whole conversation or install a second memory system. Oversized input
returns a blocker; it never silently removes counterexamples to fit.

Unchanged input can skip a new call using `previous_input_digest`; the caller must
supply it from its own valid advice records. This helper has no persistent cache
or automatic launch hook. Terminal/successful tasks, unresolved attempts, missing
notes and fewer than two choices are gated before delegation. Poor but complete
results can still be investigated even when the heuristic finds no prior feasible
example. The model remains responsible for justifying that investigation.

The character limit is technical, not evidence of token savings. The definition's
iteration/time settings are engineering safeguards, not an exact spending cap.
The host must enforce actual access, request/cost limits and advice reuse.

## Return validation and its limits

`parse_answer(text)` accepts one plain JSON object with no duplicate keys.
`accept(assignment, answer, current_source)` rebuilds the packet from current
records, checks eligible selection and qualified citation IDs, and rejects extra
fields, stale advice, invented references and scientific-success labels. For a
recommendation it requires a question, hypothesis, competing explanation, baseline
comparison, expected observation, reversal condition and explicit limitations.

The returned receipt says `mechanically_valid_advice`, `scientific_validity:
not_assessed` and `execution: not_performed`. Those checks cannot establish that
prose correctly interprets evidence, supplies adequate counterexamples or avoids
overclaiming. Independent scientific review and measured comparisons remain needed.
One row-hash note per chemical ID is deliberately conservative: differing
row-level provenance currently requires reconciliation rather than automatic merging.

## Run the portable checks

From `subagent-optimization/`:

```bash
python3 -B -m unittest -v specialist.test_advisor
python3 -B -m specialist.demo
```

These run no model. The combined software runner also records these checks.

## Native setup and integration check

The current supplied Agent Scientist checkout supports saved specialists through
`/subagent import`, `/Update_subagent`, `/new`, and `tasks[].specialist`. These are
Agent Scientist interfaces, not a claim that every base Hermes release has them.
Source identity is recorded in [source-inspection.json](../research/source-inspection.json).
Nothing has been installed into a real user profile by this work.

For later user-profile setup, review the definition first, then use the existing
interactive interface in the intended profile:

```text
/subagent import "/absolute/path/to/subagent-optimization/specialist/definition.json"
/Update_subagent smallmol-investigation
/new
```

Keep the tools/skills/child selections empty. Before delegation, the host adapter
must have returned `status: invoke`; import alone does not wire the adapter into
every natural-language turn. Native automatic matching is model-driven. We do not
claim that purpose text enforces the adapter gates or guarantees timely selection.
For a controlled experiment, the harness should prepare and dispatch the exact
request, then validate the returned JSON against fresh source records.

Run the separate native canary through the host's official test runner, with its
existing test interpreter and the absolute path to `specialist/test_native.py`.
The canary imports this exact definition, checks disabled import, constructs a
real named child, uses only a loopback canned response, checks zero child tool
schemas and runtime denial, validates the returned advice, preserves parent
prompt/tools and confirms revocation prevents another request. It does not test
actual LLM reasoning, production chemistry services or scientific superiority.

The [recorded native run](../results/specialist-native-validation.json) passes both
checks. Its earlier sandbox failure and combined-run timeout are retained; an
isolated diagnostic passed, followed by a two-test pass with explicit temporary
profile isolation. No production timeout was changed and no cause or speed gain
is inferred. The portable combined suite separately records 105 checks, including
10 advisor checks. These dated validation records describe the pre-migration local
state; the bundle is included in the authorized repository migration.
See the [migration record](../research/repository-migration.md).
