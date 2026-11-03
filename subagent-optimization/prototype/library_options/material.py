"""Compare actual supplied CReM fragment material and lead-context lookup options.

Builds temporary databases with one worker. No candidate assembly, predictions,
platform submissions, specialist launch, scientific approval or campaign edits.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from rdkit import Chem, rdBase
from prototype.library_audit.audit import audit_bytes


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(tool, smi, destination, timeout):
    assert not destination.exists(), "Do not overwrite a prior material attempt"
    destination.mkdir(parents=True)
    env = {**os.environ, "PYTHONPATH": str(tool), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    def stage(name, arguments):
        completed = subprocess.run([sys.executable, "-B", *map(str, arguments)], cwd=tool, env=env,
                                   capture_output=True, text=True, timeout=timeout)
        (destination / (name + ".log")).write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError("Supplied CReM stage failed: " + name + "; inspect retained log")
    frags = destination / "frags.txt"
    stage("fragmentation", [tool / "crem/fragmentation.py", "-i", smi, "-o", frags, "-c", 1])
    for radius in (1, 2, 3):
        rows, counts = destination / f"r{radius}.txt", destination / f"r{radius}_counts.txt"
        stage(f"context-{radius}", [tool / "crem/frag_to_env_mp.py", "-i", frags, "-o", rows, "-r", radius, "-c", 1])
        frequency = Counter(rows.read_text().splitlines())
        counts.write_text("".join(f"{n} {line}\n" for line, n in sorted(frequency.items())))
        stage(f"database-{radius}", [tool / "crem/import_env_to_db.py", "-i", counts,
                                     "-o", destination / "fragments.db", "-r", radius, "-c", "-n", 1])
    return destination / "fragments.db"


def core_features(smi):
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smi)
    assert mol is not None, "Unreadable fragment core"
    return {"heavy_atoms": mol.GetNumHeavyAtoms(),
            "attachments": sum(a.GetAtomicNum() == 0 for a in mol.GetAtoms()),
            "nos_atoms": sum(a.GetSymbol() in {"N", "O", "S"} for a in mol.GetAtoms())}


def inspect_database(db, lead, implementation):
    logical, lookup, per_operation = [], set(), []
    features = {}
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        for radius in (1, 2, 3):
            table_rows = conn.execute(f"SELECT * FROM radius{radius} ORDER BY env,core_smi,core_num_atoms,core_sma,dist2,freq").fetchall()
            logical.extend((radius, *row) for row in table_rows)
            for mode in ("GROW", "MUTATE"):
                mol = Chem.AddHs(Chem.Mol(lead)) if mode == "GROW" else Chem.Mol(lead)
                settings = ({"min_size": 0, "max_size": 0, "min_inc": 2, "max_inc": 25} if mode == "GROW"
                            else {"min_size": 2, "max_size": 25, "min_inc": -1, "max_inc": 5})
                matched = set()
                for context, outgoing, ids in implementation.__fragment_mol(mol, radius):
                    old_size = Chem.MolFromSmiles(outgoing).GetNumHeavyAtoms()
                    if not settings["min_size"] <= old_size <= settings["max_size"]:
                        continue
                    rows = conn.execute(f"SELECT core_smi FROM radius{radius} WHERE env=? AND freq>=0 AND core_num_atoms BETWEEN ? AND ?",
                                        (context, old_size + settings["min_inc"], old_size + settings["max_inc"])).fetchall()
                    for (incoming,) in rows:
                        if incoming != outgoing:
                            matched.add((radius, mode, context, outgoing, incoming))
                            if incoming not in features:
                                features[incoming] = core_features(incoming)
                # Cross-check against the supplied lookup function, not merely
                # our SQL reconstruction. Neither route assembles candidates.
                native = set(implementation.get_replacements(mol, str(db), radius, min_freq=0, **settings))
                assert native == {r[-1] for r in matched}, "Lookup reconstruction differs from supplied CReM"
                lookup.update(matched)
                per_operation.append({"radius": radius, "mode": mode,
                                      "database_rows": len(table_rows),
                                      "matched_reference_contexts": len({r[2] for r in matched}),
                                      "distinct_lookup_pairs": len(matched), "lookup_parity": True})
    return {"database_sha256": file_sha(db), "logical_rows_sha256": digest(logical),
            "logical_row_count": len(logical), "per_operation": per_operation,
            "lookup_pairs_sha256": digest(sorted(lookup)),
            "lookup_pair_count": len(lookup)}, set(logical), lookup, features


def run(tool, cohort_dir, scratch, lead_path, output):
    tool, cohort_dir, scratch = tool.resolve(), cohort_dir.resolve(), scratch.resolve()
    assert not scratch.exists() and not output.exists(), "Preserve prior study output"
    curation = json.loads((cohort_dir / "curation.json").read_text())
    scratch.mkdir(parents=True)
    sys.path.insert(0, str(tool))
    from crem import crem_sub
    assert Path(crem_sub.__file__).resolve() == tool / "crem/crem_sub.py"
    spec = importlib.util.spec_from_file_location("supplied_rdkit_funcs", tool / "utils/rdkit_funcs.py")
    helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    lead_record = json.loads(lead_path.read_text())
    # Use the worker's preparation on a copy. Original source form stays intact.
    lead = helpers.get_normal_mol(Chem.MolFromSmiles(lead_record["representation"]))
    results, materials, options, all_features = {}, {}, {}, {}
    for entry in curation["libraries"]:
        name = entry["id"]
        print("Building and inspecting:", name, flush=True)
        assert file_sha(cohort_dir / entry["csv"]) == entry["intake_audit"]["content_sha256"]
        smi_audit = audit_bytes((cohort_dir / entry["smi"]).read_bytes(), "smi")
        for key in ("normalized_sequence_sha256", "normalized_multiset_sha256"):
            assert smi_audit[key] == entry["intake_audit"][key], "CSV/SMI preparation differs"
        db = build(tool, cohort_dir / entry["smi"], scratch / name, 120)
        results[name], materials[name], options[name], feature = inspect_database(db, lead, crem_sub)
        all_features.update(feature)
    first, second = "hetero_rich_sources", "carbon_rich_sources"
    def slots(items):
        grouped = defaultdict(set)
        for radius, mode, context, outgoing, incoming in items:
            f = all_features[incoming]
            if f["attachments"] == 1 and 2 <= f["heavy_atoms"] <= 6:
                grouped[(radius, mode, context, outgoing, f["heavy_atoms"], f["attachments"])].add(incoming)
        return grouped
    aa, bb = slots(options[first]), slots(options[second])
    common = sorted(set(aa) & set(bb))
    contrasts = []
    for key in common:
        aonly, bonly = aa[key] - bb[key], bb[key] - aa[key]
        hetero = sorted(s for s in aonly if all_features[s]["nos_atoms"] > 0)
        carbon = sorted(s for s in bonly if all_features[s]["nos_atoms"] == 0)
        if hetero and carbon:
            contrasts.append({"radius": key[0], "mode": key[1], "context": key[2], "outgoing_core": key[3],
                              "incoming_heavy_atoms": key[4], "attachments": key[5],
                              "hetero_rich_exclusive_example": hetero[0], "carbon_rich_exclusive_example": carbon[0]})
    comparisons = []
    names = list(options)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            comparisons.append({"first": a, "second": b,
                                "shared_logical_rows_including_frequency": len(materials[a] & materials[b]),
                                "shared_lookup_pairs": len(options[a] & options[b]),
                                "first_exclusive_lookup_pairs": len(options[a] - options[b]),
                                "second_exclusive_lookup_pairs": len(options[b] - options[a])})
    paths = ("crem/fragmentation.py", "crem/frag_to_env_mp.py", "crem/import_env_to_db.py",
             "crem/crem_sub.py", "crem/mol_context.py", "utils/rdkit_funcs.py")
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Actual source-level fragment-database and lookup qualification; no candidate generation or scoring",
              "rdkit_version": rdBase.rdkitVersion, "curation_sha256": file_sha(cohort_dir / "curation.json"),
              "lead": lead_record, "lead_file_sha256": file_sha(lead_path),
              "source_sha256": {p: file_sha(tool / p) for p in paths},
              "library_material": results, "comparisons": comparisons,
              "shared_compact_single_attachment_slots": len(common),
              "matched_size_hetero_vs_no_nos_contrast_slots": len(contrasts),
              "contrast_examples": contrasts[:12], "meaningfulness_status": "structural_contrast_observed" if contrasts else "intended_contrast_not_established",
              "limitations": ["Lookup-eligible fragments are not validated assembled products.",
                             "A matched context can occur at multiple sites; examples do not guarantee a unique site.",
                             "Library-source enrichment is not controlled candidate chemistry or target potency.",
                             "Equal source counts do not imply equal enumerations or compute.",
                             "No guarantee of DRD2, QED, similarity, synthesis or task success.",
                             "SME chemical review and real deployment parity remain outstanding."],
              "approved_asset_count": 0, "candidate_generation": False, "property_model_calls": 0,
              "scientific_jobs_submitted": 0, "specialist_launched": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"meaningfulness_status": report["meaningfulness_status"],
                      "contrast_slots": len(contrasts), "output": str(output)}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("tool-root", "cohort-dir", "scratch", "lead", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    a = p.parse_args()
    run(a.tool_root, a.cohort_dir, a.scratch, a.lead, a.output)
