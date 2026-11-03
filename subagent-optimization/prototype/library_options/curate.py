"""Outcome-blind ChEMBL source cohorts for a structural feasibility study.

Not an approval step, predictor or fragment-generation tool. Use only the bounded
snapshot and protocol recorded before acquisition. Data retain ChEMBL's terms.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

from rdkit import Chem, rdBase
from rdkit.Chem import rdMolDescriptors
from prototype.library_audit.audit import audit_bytes, normalization_policy_id, _parser


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def select_pairs(groups, maximum):
    """Same source heavy-atom/ring distribution, deterministic structure ordering."""
    bins = sorted(set(groups[0]) & set(groups[1]))
    offsets = Counter()
    pairs = []
    while len(pairs) < maximum:
        added = False
        for key in bins:
            offset = offsets[key]
            if offset < min(len(g[key]) for g in groups):
                pairs.append((groups[0][key][offset], groups[1][key][offset]))
                offsets[key] += 1
                added = True
                if len(pairs) == maximum:
                    break
        if not added:
            break
    return pairs[:len(pairs) // 2 * 2]


def run(raw_path, acquisition_path, protocol_path, output):
    protocol_raw = protocol_path.read_bytes()
    protocol = json.loads(protocol_raw)
    acquisition = json.loads(acquisition_path.read_text())
    raw = raw_path.read_bytes()
    assert sha(raw) == acquisition["sha256"], "Acquisition bytes changed"
    assert sha(protocol_raw) == acquisition["protocol_sha256_before_acquisition"], "Protocol changed after acquisition"
    assert acquisition["source_release_status"]["chembl_db_version"] == protocol["expected_release"]
    data = json.loads(raw)["molecules"]
    assert len(data) <= protocol["acquisition"]["max_records"]
    assert not output.exists(), "Use a fresh output directory to preserve prior attempts"
    output.mkdir(parents=True)
    groups = [defaultdict(list), defaultdict(list)]
    excluded, seen, intermediate = Counter(), set(), 0
    allowed = set(protocol["source_filters"]["elements"])
    low, high = protocol["acquisition"]["heavy_atoms_range"]
    for record in data:
        structure = record.get("molecule_structures") or {}
        value = structure.get("canonical_smiles")
        if not isinstance(value, str) or not value or "|" in value:
            excluded["missing_or_extended_representation"] += 1
            continue
        stream = io.StringIO(); writer = csv.writer(stream)
        writer.writerow(["SMILES"]); writer.writerow([value])
        audited = audit_bytes(stream.getvalue().encode())
        if not audited["normalized_identity_complete"] or audited["structure_scope_needs_review"]:
            excluded["incomplete_or_out_of_scope_identity"] += 1
            continue
        with rdBase.BlockLogs():
            mol = Chem.MolFromSmiles(value, _parser())
        if (Chem.GetFormalCharge(mol) != 0 or len(Chem.GetMolFrags(mol)) != 1
                or not all(a.GetSymbol() in allowed for a in mol.GetAtoms())):
            excluded["charge_component_or_element_scope"] += 1
            continue
        heavy = mol.GetNumHeavyAtoms()
        if not low <= heavy <= high:
            excluded["heavy_atom_scope"] += 1
            continue
        canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
        if canonical in seen:
            excluded["duplicate_parsed_structure"] += 1
            continue
        seen.add(canonical)
        hetero = sum(a.GetSymbol() in {"N", "O", "S"} for a in mol.GetAtoms())
        rings = rdMolDescriptors.CalcNumRings(mol)
        item = {"SMILES": canonical, "ChEMBL_ID": record["molecule_chembl_id"],
                "heavy_atoms": heavy, "rings": rings, "nos_atoms": hetero}
        if hetero >= 4:
            groups[0][(heavy, rings)].append(item)
        elif hetero <= 2:
            groups[1][(heavy, rings)].append(item)
        else:
            intermediate += 1
    for group in groups:
        for rows in group.values():
            rows.sort(key=lambda r: (sha(r["SMILES"].encode()), r["ChEMBL_ID"]))
    pairs = select_pairs(groups, protocol["cohorts"]["source_molecules_per_focused_library_max"])
    assert len(pairs) >= 8, "Insufficient exact-matched source pairs; retain this failed design"
    cohorts = {"hetero_rich_sources": [a for a, b in pairs],
               "carbon_rich_sources": [b for a, b in pairs],
               "mixed_reference": [pair[i % 2] for i, pair in enumerate(pairs)]}
    records = []
    for name, rows in cohorts.items():
        csv_path = output / (name + ".csv")
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["SMILES", "ChEMBL_ID"], extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows)
        smi_path = output / (name + ".smi")
        smi_path.write_text("".join(r["SMILES"] + "\n" for r in rows))
        audited = audit_bytes(csv_path.read_bytes())
        assert audited["normalized_identity_complete"]
        records.append({"id": name, "csv": csv_path.name, "smi": smi_path.name,
                        "source_ids": [r["ChEMBL_ID"] for r in rows],
                        "source_descriptor_rows": [{k: v for k, v in r.items() if k != "SMILES"} for r in rows],
                        "source_bins": {str(k): n for k, n in sorted(Counter((r["heavy_atoms"], r["rings"]) for r in rows).items())},
                        "intake_audit": audited, "scientific_review": "not_received",
                        "capability_card_reviewed": False, "available_for_policy": False})
    sets = {name: {r["SMILES"] for r in rows} for name, rows in cohorts.items()}
    comparisons = [{"first": a, "second": b, "intersection": len(sets[a] & sets[b]),
                    "union": len(sets[a] | sets[b])}
                   for i, a in enumerate(cohorts) for b in list(cohorts)[i + 1:]]
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Actual source-molecule curation; no fragment/material or molecular-outcome qualification yet",
              "protocol_sha256": sha(protocol_raw), "normalization_policy_id": normalization_policy_id(),
              "acquisition": acquisition, "input_records": len(data),
              "excluded": dict(excluded), "eligible_intermediate_nos_count_3": intermediate,
              "group_pool_counts": [sum(len(x) for x in g.values()) for g in groups],
              "libraries": records, "normalized_source_overlap": comparisons,
              "approved_asset_count": 0, "scientific_jobs_submitted": 0,
              "property_model_calls": 0}
    (output / "curation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), "cohort_size": len(pairs),
                      "group_pool_counts": report["group_pool_counts"], "approved_asset_count": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--acquisition", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.raw, args.acquisition, args.protocol, args.output)
