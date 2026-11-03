"""Plan over real structural data with HYPOTHETICAL inclusion history; no agent/job runs."""
import argparse
import json
from pathlib import Path

from prototype.library_options.coverage import plan


def demonstration(index):
    initial = ["mixed_reference"]
    return {"scope": "Real lookup data with hypothetical prior inclusion; no scientific campaign has run",
            "scientific_benefit": "not_evaluated", "actual_candidate_evaluations": 0,
            "comparisons": {s: plan(index, initial, additions=1, strategy=s)
                            for s in ("new_coverage", "largest_library", "fixed_order")}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = demonstration(json.loads(args.index.read_text()))
    if args.output:
        with args.output.open("x") as f:
            f.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({s: {"selected": r["selected_additions"],
                         "additional_lookup_tuples": r["rounds"][0]["additional_lookup_tuples"],
                         "planned_union_lookup_count": r["planned_union_lookup_count"]}
                      for s, r in result["comparisons"].items()}, indent=2))
