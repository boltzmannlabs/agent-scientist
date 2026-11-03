"""Controlled artificial decision comparison, NOT molecular performance."""
import json
from fixtures import controlled_histories
from policy import choose_library

t, libs, favourable, counterexamples = controlled_histories()
out = {"scope": "Same IDs/counts/timing, only artificial metric values differ",
       "scientific_gain_measured": False}
for name, history in (("favourable_history", favourable), ("counterexample_history", counterexamples)):
    out[name] = {strategy: {k: v for k, v in choose_library(t, libs, history, strategy).items()
                           if k in {"library_id", "reason", "coverage_front", "qualifying_ids"}}
                 for strategy in ("context_coverage", "round_robin")}
print(json.dumps(out, indent=2))
