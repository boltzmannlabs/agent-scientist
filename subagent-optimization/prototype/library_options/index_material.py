"""Index existing study databases read-only; do not rebuild them or generate products."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

from rdkit import Chem, rdBase
from prototype.library_audit.audit import normalization_policy_id
from prototype.library_options.material import inspect_database, file_sha, digest


def extract(tool, cohort, databases, output):
    tool, cohort, databases = tool.resolve(), cohort.resolve(), databases.resolve()
    if output.exists():
        raise FileExistsError("Preserve prior index")
    material = json.loads((cohort / "material.json").read_text())
    curation = json.loads((cohort / "curation.json").read_text())
    assert file_sha(cohort / "curation.json") == material["curation_sha256"]
    assert material["rdkit_version"] == rdBase.rdkitVersion
    assert curation["normalization_policy_id"] == normalization_policy_id()
    for path, sha in material["source_sha256"].items():
        assert file_sha(tool / path) == sha, "Supplied source changed after qualification"
    basis = {"lead_sha256": material["lead_file_sha256"],
             "rdkit_version": rdBase.rdkitVersion,
             "normalization_policy_id": normalization_policy_id(),
             "preparation_and_lookup_source": material["source_sha256"],
             "query": "actual grow-2..25/mutate-2..25-inc(-1,+5), radii1..3,min_freq0"}
    scope = digest(basis)
    sys.path.insert(0, str(tool))
    from crem import crem_sub
    assert Path(crem_sub.__file__).resolve() == tool / "crem/crem_sub.py"
    spec = importlib.util.spec_from_file_location("supplied_rdkit_funcs", tool / "utils/rdkit_funcs.py")
    helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    lead = helpers.get_normal_mol(Chem.MolFromSmiles(material["lead"]["representation"]))
    libraries, dimensions = [], {}
    for lib in curation["libraries"]:
        name = lib["id"]
        assert file_sha(cohort / lib["csv"]) == lib["intake_audit"]["content_sha256"]
        db = databases / name / "fragments.db"
        assert file_sha(db) == material["library_material"][name]["database_sha256"]
        with rdBase.BlockLogs():
            fresh, _, pairs, _ = inspect_database(db, lead, crem_sub)
        assert fresh == material["library_material"][name], "Read-only reinspection differs from saved study"
        ids = []
        for row in sorted(pairs):
            key = digest({"scope_id": scope, "lookup_tuple": row})
            ids.append(key)
            dimensions[key] = {"radius": row[0], "mode": row[1]}
        libraries.append({"id": name, "content_sha256": lib["intake_audit"]["content_sha256"],
                          "normalized_input_set_sha256": lib["intake_audit"]["normalized_input_set_sha256"],
                          "lookup_ids": sorted(ids), "scientific_review": "not_received",
                          "available_for_policy": False})
    index = {"schema_version": 1, "scope_id": scope, "basis": basis,
             "material_report_sha256": file_sha(cohort / "material.json"),
             "libraries": libraries, "lookup_dimensions": dimensions,
             "units": "Potential context-replacement lookup tuples, not independent products or evaluations",
             "approved_asset_count": 0, "execution_approved": False}
    output.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"output": str(output), "indexed_union_tuples": len(dimensions),
                      "approved_asset_count": 0}))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("tool-root", "cohort-dir", "databases", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    a = p.parse_args()
    extract(a.tool_root, a.cohort_dir, a.databases, a.output)
