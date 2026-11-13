"""Entirely artificial records: no molecules, predictions or qualified services.

The invalid fixture-smiles/file identifiers deliberately cannot be run as science.
True admission flags simulate host decisions only for testing the pure component.
"""
from copy import deepcopy


def config():
    return {
        "seed": 17, "panel_size": 10,
        "reference_roles": {"FIXTURE_LEAD": "lead", "FIXTURE_CONTROL": "control"},
        "constraints": {
            "solubility": {"min": -4, "method": "FIXTURE_SOL", "unit": "log10(mol/L)"},
            "qed": {"min": .5, "method": "FIXTURE_QED", "unit": "dimensionless"},
            "crippen_logp": {"min": 0, "max": 5, "method": "FIXTURE_CRIPPEN", "unit": "dimensionless"},
        },
        "quality": {"metric": "vina", "direction": "min", "method": "FIXTURE_VINA", "unit": "kcal/mol"},
        "constraint_priorities": [],
        "objective_models": {"global_models": [
            {"name": "Solubility", "min_threshold": -6, "max_threshold": -4}]},
    }


def candidate(identity="FIXTURE_LEAD", *, role="lead", sol=-3, qed=.8, logp=2, vina=-8):
    c = config()
    values = {"solubility": sol, "qed": qed, "crippen_logp": logp, "vina": vina}
    measurements = {}
    for name, value in values.items():
        rule = c["quality"] if name == "vina" else c["constraints"][name]
        measurements[name] = {"value": value, "status": "ok" if value is not None else "unavailable",
                              "method": rule["method"], "unit": rule["unit"]}
    return {"identity": identity, "smiles": "fixture-smiles:" + identity,
            "valid": True, "role": role, "measurements": measurements}


def snapshot(rows=None):
    return {"state": "active", "jobs": [], "candidates": [candidate()] if rows is None else rows,
            "resources": {"generation_remaining": 2, "search_remaining": 100, "final_remaining": 10},
            "attempted_action_keys": []}


def action(route="crem", parent="FIXTURE_LEAD"):
    models = deepcopy(config()["objective_models"])
    if route == "assess":
        payload = {"identities": [parent]}
        targets = ["missing_evidence"]
    elif route == "crem":
        payload = {"ref_mol": "fixture-smiles:" + parent,
                   "library_path": "fixture://not-a-platform-file", **models}
        targets = ["docking"]
    else:
        payload = {"smiles": "fixture-smiles:" + parent,
                   "n_mols": 10, "n_steps": 2, **models}
        targets = ["solubility"]
    return {"route": route, "parent_identity": parent, "payload": payload,
            "profile_id": "FIXTURE_ONLY_DO_NOT_EXECUTE", "qualified": True,
            "objective_qualified": True, "targets": targets,
            "search_allocation": 1 if route == "assess" else 10,
            "hypothesis": "Artificial test hypothesis for " + route,
            "counterevidence": "Artificial observed gap remains or constraints worsen",
            "evidence_refs": ["fixture://synthetic-evidence"],
            **({"library_identity": "FIXTURE_LIBRARY_SET"} if route == "crem" else {})}


def panel_rows():
    return [candidate("FIXTURE_%02d" % i, role="generated", vina=-10 + i / 10)
            for i in range(10)]
