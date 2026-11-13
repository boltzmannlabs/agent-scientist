"""Read a frozen p38 long-record archive; save a separate non-executable import."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from feedback_policy import decide, require
from observations import bundle_file, csv_records, import_long_records, sha256, verified_file


def import_p38_archive(run_directory):
    root = Path(run_directory).resolve()
    manifest_raw = bundle_file(root, "artifact_manifest.csv")
    manifest_rows = csv_records(manifest_raw, {"relative_path", "bytes", "sha256"})
    names = ("candidate_registry.csv", "comparison_metrics.csv", "run_manifest.json")
    sources = {name: verified_file(root, name, manifest_rows) for name in names}
    run = json.loads(sources["run_manifest.json"])
    scorer = run["scorer"]
    implementations = scorer["descriptor_implementations"]
    require(implementations.get("qed") == "rdkit.Chem.QED.qed"
            and implementations.get("logp") == "rdkit.Chem.Crippen.MolLogP",
            "Recorded descriptor definitions differ from this reviewed mapping")
    # This historical importer supports the recorded Smina producer only.
    require("smina" in scorer["version_stdout"].lower(), "Reviewed historical Smina setup required")
    metrics = csv_records(sources["comparison_metrics.csv"], {"case_id", "run_id", "candidate_id",
                         "canonical_identity", "phase", "metric_id", "unit", "method_version"})
    cases = {r["case_id"] for r in metrics}
    require(len(cases) == 1 and cases == {"p38_1a9u"}, "One reviewed p38 case required")
    context = {"case_id": "p38_1a9u", "run_id": run["run_id"]}
    controls = {r["canonical_identity"] for r in metrics
                if r["candidate_id"] == "control" and r["phase"] == "control"}
    require(len(controls) == 1, "One explicit recorded control identity required")
    control = next(iter(controls))
    rdkit_method = f"RDKit {scorer['rdkit_version']}; pinned descriptor implementations/models"
    method_map = {"qed": ("qed", rdkit_method, "dimensionless"),
                  "logp": ("crippen_logp", rdkit_method, "dimensionless"),
                  "sa": ("sa", rdkit_method, "dimensionless"),
                  "np_likeness": ("np_likeness", rdkit_method, "dimensionless"),
                  "smina_raw": ("smina_raw", "Smina 2020.12.10", "native Smina energy scale (kcal/mol convention)"),
                  "smina_score": ("smina_score", "Smina 2020.12.10", "negative native Smina energy scale")}
    bindings = [{"source_metric": key, "target_metric": target, "producer_method": method,
                 "unit": unit, "qualified": True} for key, (target, method, unit) in method_map.items()]
    imported = import_long_records(
        sources["candidate_registry.csv"], sources["comparison_metrics.csv"], bindings=bindings,
        expected_context=context, reference_roles={control: "control"}, reference_candidates=[{
            "candidate_id": "control", "canonical_identity": control, "status": "VALID_CONNECTED_COMPLETE"}])
    # Missing methods stay explicit. These names/configuration do not qualify a
    # model or evaluator and are never used to generate an action in this replay.
    config = {"seed": 0, "panel_size": 10, "reference_roles": {control: "control"},
              "constraints": {
                  "solubility": {"min": -4, "method": "UNQUALIFIED_SOLUBILITY", "unit": "UNVERIFIED"},
                  "qed": {"min": .5, "method": rdkit_method, "unit": "dimensionless"},
                  "crippen_logp": {"min": 0, "max": 5, "method": rdkit_method, "unit": "dimensionless"}},
              "quality": {"metric": "vina", "direction": "min", "method": "UNQUALIFIED_PLATFORM_VINA",
                          "unit": "UNVERIFIED"},
              "objective_models": {"global_models": [{"name": "Solubility", "min_threshold": -6,
                                                       "max_threshold": -4}]}}
    archive = {"state": "frozen", "jobs": [], "candidates": imported["phase_candidates"]["search"]}
    decision = decide(archive, [], config)
    phases = Counter(r["source"]["phase"] for r in imported["observations"])
    coverage = {phase: {key: sum(row["measurements"][key]["status"] == "ok" for row in rows)
                       for key in ("qed", "crippen_logp", "solubility", "vina")}
                for phase, rows in imported["phase_candidates"].items()}
    # Verify the exact source bytes again; never rewrite or follow pose paths.
    for name, raw in sources.items():
        require(verified_file(root, name, manifest_rows) == raw, "Source changed during import")
    require(bundle_file(root, "artifact_manifest.csv") == manifest_raw, "Source manifest changed during import")
    receipt = {"created_utc": datetime.now(timezone.utc).isoformat(), "source_directory": str(root),
               "source_hashes": {**{name: sha256(raw) for name, raw in sources.items()},
                                 "artifact_manifest.csv": sha256(manifest_raw)},
               "verified_manifest_members": list(names), "source_records_unchanged": True,
               "registry_rows": len(imported["registry"]), "measurement_rows": len(imported["observations"]),
               "phase_measurement_counts": dict(phases), "qualified_record_coverage": coverage,
               "conflicts": imported["conflicts"], "archive_decision": decision,
               "source_identity_status": "host-recorded; molecular semantics not revalidated",
               "source_authenticity": "hash consistency checked; not independent authentication",
               "comparison_ready": False, "missing_new_case_methods": ["Solubility", "platform Vina"],
               "scientific_execution": "none", "allowances_restored": False}
    return imported, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    root, output = Path(args.run_dir).resolve(), Path(args.out_dir).resolve()
    require(not output.is_relative_to(root), "Output must be outside the frozen source bundle")
    require(not output.exists(), "Choose a new output directory; no overwrite")
    imported, receipt = import_p38_archive(root)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("observations.json", imported), ("import_receipt.json", receipt)):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output_directory": str(output), "registry_rows": receipt["registry_rows"],
                      "measurement_rows": receipt["measurement_rows"],
                      "phase_measurement_counts": receipt["phase_measurement_counts"],
                      "qualified_record_coverage": receipt["qualified_record_coverage"],
                      "archive_disposition": receipt["archive_decision"]["disposition"],
                      "source_records_unchanged": True, "scientific_execution": "none"}, indent=2))


if __name__ == "__main__":
    main()
