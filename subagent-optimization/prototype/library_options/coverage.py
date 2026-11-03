"""Standard greedy maximum-coverage PLANNING baseline; not scientific advice.

Coverage counts potential context/replacement lookup tuples. Including a library
in this abstract plan does not establish generated, valid or evaluated products.
The allowance is a number of library additions, not matched compute or money.
"""
from collections import Counter


def plan(index, initially_included=(), additions=1, strategy="new_coverage"):
    if strategy not in {"new_coverage", "largest_library", "fixed_order"}:
        raise ValueError("Unknown planning strategy")
    if type(additions) is not int or additions < 0:
        raise ValueError("Library-addition allowance must be a nonnegative integer")
    if not isinstance(index, dict) or type(index.get("schema_version")) is not int or index["schema_version"] != 1:
        raise ValueError("Versioned lookup index required")
    if not isinstance(index.get("scope_id"), str) or not index["scope_id"]:
        raise ValueError("Reference/preparation scope binding required")
    libraries = index.get("libraries")
    if not isinstance(libraries, list) or not libraries:
        raise ValueError("Nonempty library index required")
    lookup, order = {}, []
    for lib in libraries:
        if not isinstance(lib, dict):
            raise ValueError("Library record must be an object")
        lid, ids = lib.get("id"), lib.get("lookup_ids")
        if not isinstance(lid, str) or not lid or lid in lookup:
            raise ValueError("Unique nonempty library IDs required")
        if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
            raise ValueError("Explicit lookup-key lists required")
        if len(ids) != len(set(ids)):
            raise ValueError("Lookup lists must already be deduplicated")
        lookup[lid] = set(ids)
        order.append(lid)
    if (not isinstance(initially_included, (list, tuple))
            or any(not isinstance(x, str) for x in initially_included)
            or len(initially_included) != len(set(initially_included))
            or not set(initially_included) <= set(lookup)):
        raise ValueError("Initial plan contains duplicate or unknown libraries")
    dimensions = index.get("lookup_dimensions", {})
    universe = set().union(*lookup.values())
    if not isinstance(dimensions, dict) or set(dimensions) != universe:
        raise ValueError("Every indexed key needs an explicit radius/operation dimension")
    for dimension in dimensions.values():
        if (not isinstance(dimension, dict) or type(dimension.get("radius")) is not int
                or dimension["radius"] not in {1, 2, 3} or not isinstance(dimension.get("mode"), str)
                or dimension["mode"] not in {"GROW", "MUTATE"}):
            raise ValueError("Invalid lookup dimension")
    included = list(initially_included)
    covered = set().union(*(lookup[lid] for lid in included)) if included else set()
    initial_count, rounds = len(covered), []
    for _ in range(additions):
        rows = []
        for ordinal, lid in enumerate(order):
            if lid in included:
                continue
            new = lookup[lid] - covered
            layers = Counter(f"radius{dimensions[key]['radius']}:{dimensions[key]['mode']}" for key in new)
            rows.append({"library_id": lid, "total_lookup_tuples": len(lookup[lid]),
                         "overlap_with_included": len(lookup[lid] & covered),
                         "additional_lookup_tuples": len(new),
                         "additional_by_radius_operation": dict(sorted(layers.items())), "ordinal": ordinal})
        eligible = [r for r in rows if r["additional_lookup_tuples"] > 0]
        if not eligible:
            break
        if strategy == "new_coverage":
            selected = max(eligible, key=lambda r: (r["additional_lookup_tuples"], -r["ordinal"]))
        elif strategy == "largest_library":
            selected = max(eligible, key=lambda r: (r["total_lookup_tuples"], -r["ordinal"]))
        else:
            selected = eligible[0]
        included.append(selected["library_id"])
        covered.update(lookup[selected["library_id"]])
        rounds.append({"options": [{k: v for k, v in r.items() if k != "ordinal"} for r in rows],
                       "selected_library": selected["library_id"],
                       "additional_lookup_tuples": selected["additional_lookup_tuples"],
                       "planned_union_lookup_count": len(covered)})
    return {"scope": "Structural lookup-coverage plan only; no invocation or execution authority",
            "scope_id": index["scope_id"], "strategy": strategy,
            "initially_included": list(initially_included), "addition_allowance": additions,
            "initial_union_lookup_count": initial_count, "rounds": rounds,
            "selected_additions": included[len(initially_included):],
            "planned_union_lookup_count": len(covered),
            "stop_reason": "addition_allowance_used" if len(rounds) == additions else "no_additional_indexed_material",
            "scientific_benefit": "not_assessed", "actual_compute": "unknown",
            "execution": "not_performed", "execution_approved": False}
