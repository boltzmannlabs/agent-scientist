# Process study reporting and delivery

Save a Markdown report in `build/report.md`, upstream validation JSON in
`build/validation.json`, and the actual stream JSON in `build/streams.json`.
Capture structured output from the successful commands; do not reconstruct it
from memory or claim files were saved when they were not. Preserve failed-run
diagnostics too, identifying which case and command produced them.

Use this order, omitting empty comparison tables when no comparison was run:

1. **Run summary** — objective, study boundary, cases, model and version,
   operations actually performed, key finding and evidence status.
2. **Inputs and assumptions** — parameter, value, unit, source and provenance;
   missing information shown as `Not Available`.
3. **Process and results** — explain each unit operation and calculated quantity;
   map streams by ID, from/to equipment, case, flow and composition. State
   the balance tolerance and residuals, with purpose and interpretation beside
   the numerical output. Separate mass balance from energy/phase calculations.
4. **Comparison**, if requested — parameter, baseline, candidate, raw percentage
   change, direction of benefit and interpretation. A decrease in cost or energy
   demand is an improvement if the other constraints are met; purity or recovery
   generally benefits from increases. Compare operating-range parameters against
   their target range. When baseline is zero, percentage change is undefined;
   use an absolute difference. Do not rank candidates on unavailable metrics.
5. **Limitations and next validation** — model scope, convergence, uncertainty
   actually quantified, missing data and suggested validation. Keep calculated,
   assumed, measured and literature evidence distinct. Use `Experimental
   validation pending` for predictions awaiting experiments.
6. **Final outcome** — answer the user's objective, present the final process
   values and comparisons, justify any recommended candidate, and attach outputs.

In chat, explain the diagrams and put each deliverable image on its own line:

```text
MEDIA:/actual/project/build/BFD-chat.png
MEDIA:/actual/project/build/PFD-chat.png
MEDIA:/actual/project/build/PFD-streams.png
```

Generate these with `sci cheme --project PROJECT --chat-diagrams` after process
build. It exports focused vector-derived PNGs with enlarged labels and a separate
stream table. Use these for chat rather than shrinking a full engineering sheet.
Full-sheet PNG/SVG/XML remain available as downloads. For a large flowsheet,
provide upstream `render --tiles` detail views if the overview is still too dense.

Use actual generated paths. Supply a Markdown report link and optional SVG/XML
download links alongside the preview. If the runtime cannot render an image,
report its error and preserve usable outputs; a text path alone is not an image
preview. Never state that a browser or terminal displayed an image based only on
file creation. The UI controls its own display support.
