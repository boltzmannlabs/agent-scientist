"""Inspect three explicitly selected existing files; emit metadata, never structures.

Run with an explicit source checkout. Does not scan arbitrary libraries, approve
an asset, prepare service inputs, fragment molecules, or run a scientific model.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from audit import audit_bytes, compare_bytes, read_asset


ASSETS = (
    ("crem-example-csv", "v5/Molecule Optimzation/crem/api_data/input_library.csv", "csv", "quarantined_example"),
    ("crem-example-smi", "v5/Molecule Optimzation/crem/api_data/input_library.smi", "smi", "quarantined_example"),
    ("zinc-named-1000", "v5/Molecule Optimzation/Graph_GA/data/ZINC_first_1000.smi", "smi", "candidate_only"),
)


def inspect(root):
    records, raw = [], {}
    for asset_id, relative, input_format, status in ASSETS:
        content = read_asset(root / relative)
        raw[asset_id] = content
        records.append({"asset_id": asset_id, "source_relative_path": relative,
                        "intake_status": status,
                        "provenance": "unverified; filename is not source/release evidence",
                        "data_use_terms": "not_established",
                        "sme_family_context_review": "not_received",
                        "audit": audit_bytes(content, input_format)})
    return {"schema_version": 1, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source": "User-supplied local BOLTCHEM-FEATURES v5 working files",
            "scope": "Metadata-only intake of three explicit files; no approved policy actions",
            "assets": records,
            "comparisons": [{"first": "crem-example-csv", "second": "crem-example-smi",
                             **compare_bytes(raw["crem-example-csv"], raw["crem-example-smi"], "csv", "smi")}],
            "approved_asset_count": 0, "scientific_jobs_submitted": 0,
            "scoring_or_model_execution": False,
            "fragment_database_built": False,
            "raw_structures_exported": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.source_root), indent=2))
