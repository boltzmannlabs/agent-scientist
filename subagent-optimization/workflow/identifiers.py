"""Reversible typed identifier presentation; scientific facts remain canonical.

Only declared identity fields/tables are rewritten. Molecular strings, prose,
source columns, library identifiers and arbitrary user labels are never globally
replaced. Alias maps and raw wire outcomes belong in private execution evidence.
"""
from copy import deepcopy
import hashlib
import json
import re


PATTERNS = {"M": re.compile(r"candidate-[a-f0-9]{64}\Z"),
            "F": re.compile(r"canonical-isomeric-[a-f0-9]{64}\Z"),
            "E": re.compile(r"obs-[a-f0-9]{64}\Z"), "A": re.compile(r"[a-f0-9]{64}\Z")}
ALIAS = re.compile(r"[MFEA][0-9]{3,}\Z")
SCALARS = {"candidate_id": "M", "parent_id": "M", "parent_candidate_id": "M",
           "baseline_id": "M", "reference_id": "M", "form_id": "F", "parent_form_id": "F",
           "form_id_override": "F", "action_key": "A", "action_id": "A", "attempt_id": "A"}
LISTS = {"candidate_ids": "M", "final_candidate_ids": "M", "qualified_candidate_ids": "M",
         "pareto_parent_ids": "M", "diversity_representative_ids": "M", "alias_candidate_ids": "M",
         "evidence_ids": "evidence", "observation_ids": "E", "supporting_ids": "evidence",
         "counterexample_ids": "evidence", "points": "M"}
CANDIDATES = {"reference", "original_reference", "starting_candidates", "candidates", "parent_options"}
OBSERVATIONS = {"initial_observations", "observations"}
RAW = {"source_columns", "notes", "annotations", "metadata", "source", "provenance"}
DERIVED_RULE = "For candidate-<digest>, absent form_id_override means canonical-isomeric-<same digest>; other identities always include an override"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _kind(kind, value):
    if not isinstance(value, str):
        return None
    if kind == "evidence":
        return next((k for k in ("M", "E") if PATTERNS[k].fullmatch(value)), None)
    return kind if kind in PATTERNS and PATTERNS[kind].fullmatch(value) else None


def _walk(node, mapper, context=None):
    if isinstance(node, list):
        return [_walk(v, mapper, context) for v in node]
    if not isinstance(node, dict):
        return deepcopy(node)
    if context is None and "id" in node:
        if "candidate_id" in node and "endpoint" in node:
            context = "observation"
        elif "form_id" in node and ("representation" in node or "canonical_form" in node):
            context = "candidate"
    result = {}
    columns = node.get("columns")
    for key, value in node.items():
        if key in RAW:
            result[key] = deepcopy(value)
        elif key in SCALARS:
            result[key] = mapper(SCALARS[key], value)
        elif key == "id" and context in {"candidate", "observation"}:
            result[key] = mapper("M" if context == "candidate" else "E", value)
        elif key in LISTS and isinstance(value, list):
            result[key] = [mapper(LISTS[key], v) for v in value]
        elif key in CANDIDATES:
            result[key] = _walk(value, mapper, "candidate")
        elif key in OBSERVATIONS:
            result[key] = _walk(value, mapper, "observation")
        elif key == "candidate_forms" and isinstance(value, dict):
            result[key] = {mapper("M", cid): _walk(record, mapper, "candidate") for cid, record in value.items()}
        elif key == "nonparent_identities" and isinstance(value, list):
            fields = node.get("nonparent_identity_columns", [])
            result[key] = _table(value, fields, mapper)
        elif key in {"rows", "records"} and isinstance(columns, list) and all(isinstance(c, str) for c in columns) and isinstance(value, list) and all(isinstance(r, list) for r in value):
            result[key] = _table(value, columns, mapper)
        else:
            inferred = "observation" if isinstance(value, dict) and "candidate_id" in value and "endpoint" in value else None
            result[key] = _walk(value, mapper, inferred)
    return result


def _table(rows, columns, mapper):
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("Identity table dimensions disagree with declared columns")
    return [[mapper(SCALARS.get(field, LISTS.get(field)), cell) if field in SCALARS else
             [mapper(LISTS[field], x) for x in cell] if field in LISTS and isinstance(cell, list) else
             deepcopy(cell) for field, cell in zip(columns, row)] for row in rows]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)


def _derived_forms(helper):
    if helper.get("nonparent_form_rule") != DERIVED_RULE:
        return []
    fields = helper.get("nonparent_identity_columns", [])
    if "candidate_id" not in fields or "form_id_override" not in fields:
        return []
    cid_index, override_index = fields.index("candidate_id"), fields.index("form_id_override")
    result = []
    for row in helper.get("nonparent_identities", []):
        cid = row[cid_index]
        if row[override_index] is None and isinstance(cid, str) and PATTERNS["M"].fullmatch(cid):
            result.append((cid, "canonical-isomeric-" + cid.removeprefix("candidate-")))
    return result


def _checked_map(manifest):
    mapping = manifest["alias_to_canonical"]
    if digest(mapping) != manifest["mapping_sha256"] or len(set(mapping.values())) != len(mapping):
        raise ValueError("Identifier presentation map is changed or not bijective")
    for alias, original in mapping.items():
        if not ALIAS.fullmatch(alias) or not PATTERNS[alias[0]].fullmatch(original):
            raise ValueError("Invalid typed identifier alias")
    return mapping


def _decoder(manifest):
    mapping = _checked_map(manifest)
    literals = set(manifest["literal_alias_like_ids"])
    def decode(kind, value):
        if not isinstance(value, str):
            return deepcopy(value)
        if value in mapping:
            actual = value[0]
            permitted = {"M", "E"} if kind == "evidence" else {kind}
            if actual not in permitted:
                raise ValueError("Identifier alias has the wrong semantic type")
            return mapping[value]
        if ALIAS.fullmatch(value) and value not in literals:
            raise ValueError("Unknown identifier alias")
        return value
    return decode


def present_assignment(canonical):
    """Create shared model-facing aliases and a private reversible manifest."""
    if canonical.get("input_digest") != digest({k: v for k, v in canonical.items() if k != "input_digest"}):
        raise ValueError("Canonical assignment digest mismatch")
    if canonical.get("task_digest") != digest(canonical["task"]):
        raise ValueError("Canonical task digest mismatch")
    originals = {kind: set() for kind in PATTERNS}
    literals = set()
    def collect(kind, value):
        selected = _kind(kind, value)
        if selected:
            originals[selected].add(value)
        elif isinstance(value, str) and ALIAS.fullmatch(value):
            literals.add(value)
        return value
    _walk(canonical, collect)
    pairs = _derived_forms(canonical["helper_summaries"])
    for cid, form in pairs:
        collect("M", cid); collect("F", form)
    reserved = {s for s in _strings(canonical) if ALIAS.fullmatch(s)}
    mapping = {}
    for kind in PATTERNS:
        number = 1
        for original in sorted(originals[kind]):
            while f"{kind}{number:03d}" in reserved:
                number += 1
            mapping[f"{kind}{number:03d}"] = original
            number += 1
    reverse = {original: alias for alias, original in mapping.items()}
    def encode(kind, value):
        return reverse[value] if _kind(kind, value) else deepcopy(value)
    wire = _walk(canonical, encode)
    helper = wire["helper_summaries"]
    previous = deepcopy(canonical["helper_summaries"].get("presentation"))
    if previous is not None and not isinstance(previous, dict):
        raise ValueError("Existing presentation metadata must be an object")
    presentation = deepcopy(previous or {})
    if "identifier_aliases" in presentation:
        raise ValueError("Assignment already has an identifier presentation")
    presentation["identifier_aliases"] = {
        "method": "typed-short-identifiers-v1", "canonical_input_digest": canonical["input_digest"],
        "mapping_sha256": digest(mapping), "counts": {k: len(v) for k, v in originals.items()},
        "rules": "Use the supplied short IDs in structured answers. M=molecule, F=form, E=observation, A=action. Other identifiers and all scientific values are unchanged. Remaining evidence/objective digests refer to canonical host records.",
        "derived_nonparent_form_aliases": [[reverse[cid], reverse[form]] for cid, form in pairs],
        "form_note": "Canonical ID reconstruction text refers to canonical host IDs; the pairs above give corresponding short form IDs for compressed nonparent records."}
    helper["presentation"] = presentation
    wire["task_digest"] = digest(wire["task"])
    wire["input_digest"] = digest({k: v for k, v in wire.items() if k != "input_digest"})
    manifest = {"method": "typed-short-identifiers-v1", "alias_to_canonical": mapping,
                "mapping_sha256": digest(mapping), "literal_alias_like_ids": sorted(literals),
                "canonical_input_digest": canonical["input_digest"], "canonical_task_digest": canonical["task_digest"],
                "wire_input_digest": wire["input_digest"], "original_presentation": previous,
                "had_presentation": "presentation" in canonical["helper_summaries"],
                "canonical_chars": len(json.dumps(canonical, separators=(",", ":"))),
                "wire_chars": len(json.dumps(wire, separators=(",", ":")))}
    if restore_assignment(wire, manifest) != canonical:
        raise ValueError("Identifier presentation changed canonical scientific evidence")
    return wire, manifest


def restore_assignment(wire, manifest):
    if wire.get("input_digest") != manifest["wire_input_digest"] or wire["input_digest"] != digest({k: v for k, v in wire.items() if k != "input_digest"}):
        raise ValueError("Wire assignment digest mismatch")
    value = deepcopy(wire)
    if manifest["had_presentation"]:
        value["helper_summaries"]["presentation"] = deepcopy(manifest["original_presentation"])
    else:
        value["helper_summaries"].pop("presentation", None)
    result = _walk(value, _decoder(manifest))
    result["task_digest"] = manifest["canonical_task_digest"]
    result["input_digest"] = manifest["canonical_input_digest"]
    if digest(result["task"]) != result["task_digest"] or digest({k: v for k, v in result.items() if k != "input_digest"}) != result["input_digest"]:
        raise ValueError("Presentation restoration differs from canonical evidence")
    return result


def expand_outcome(wire_outcome, manifest):
    if wire_outcome.get("input_digest") != manifest["wire_input_digest"]:
        raise ValueError("Outcome refers to another wire assignment")
    result = _walk(wire_outcome, _decoder(manifest))
    result["input_digest"] = manifest["canonical_input_digest"]
    return result


def wire_outcome_schema(canonical_schema):
    """Only action_key string constraints change; canonical schema stays untouched."""
    def walk(value, action=False):
        if isinstance(value, list):
            return [walk(item, action) for item in value]
        if not isinstance(value, dict):
            return deepcopy(value)
        result = {}
        for key, item in value.items():
            if action and key == "pattern":
                result[key] = r"^A[0-9]{3,}$"
            elif key == "properties" and isinstance(item, dict):
                result[key] = {name: walk(rule, name == "action_key") for name, rule in item.items()}
            else:
                result[key] = walk(item, action)
        return result
    return walk(canonical_schema)
