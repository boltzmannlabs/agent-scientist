"""Artificial fixtures only: IDs are NOT molecules; values are NOT predictions."""
from copy import deepcopy
if __package__:
    from .policy import signature, action_signature
else:
    from policy import signature, action_signature


def task():
    return {"task_id": "ARTIFICIAL_TASK", "reference_id": "ARTIFICIAL_REFERENCE",
            "context_id": "FIXTURE_CONTEXT", "assessor_id": "NO_MODEL_EXECUTED",
            "filter_protocol": "FIXTURE_PROTOCOL", "family_definition_id": "FIXTURE_EDIT_ONTOLOGY_V1",
            "library_identity_policy_id": "FIXTURE_NORMALIZATION_V1",
            "generation_settings": {"fixture": "FIXED_SETTINGS"},
            "state": "active", "stop_on_first_success": True,
            "objectives": [{"metric": "objective_a", "operator": "gt", "threshold": .6},
                           {"metric": "objective_b", "operator": "gt", "threshold": .7}],
            "constraints": [{"metric": "similarity", "operator": "gt", "threshold": .7}]}


def libraries():
    return [{"id": "LIBRARY_" + letter.upper(), "asset_ref": "fixture://" + letter,
             "content_sha256": letter * 64, "context_id": "FIXTURE_CONTEXT",
             "normalized_input_set_sha256": letter * 64,
             "normalization_policy_id": "FIXTURE_NORMALIZATION_V1",
             "target_family": family, "family_definition_id": "FIXTURE_EDIT_ONTOLOGY_V1",
             "capability_card_reviewed": True, "approved": True, "available_for_analysis": True}
            for letter, family in (("a", "FAMILY_F"), ("b", "FAMILY_G"),
                                   ("c", "FAMILY_F"), ("d", "FAMILY_G"))]


def row(identity, a, b, similarity=.8, family="FAMILY_F"):
    return {"chemical_id": "ARTIFICIAL_ID_" + identity, "valid": True,
            "values": {"objective_a": a, "objective_b": b, "similarity": similarity},
            "edit_family": family, "single_edit": True, "annotation_reviewed": True,
            "family_definition_id": "FIXTURE_EDIT_ONTOLOGY_V1",
            "parent_id": "ARTIFICIAL_REFERENCE", "context_id": "FIXTURE_CONTEXT"}


def batch(t, lib, number, rows, **changes):
    d = {"id": f"FIXTURE_BATCH_{number}", "sequence": number, "library_id": lib["id"],
         "signature": signature(t), "action_signature": action_signature(lib),
         "evidence_admissible": True, "status": "complete", "complete_output_coverage": True,
         "rows": deepcopy(rows)}
    d.update(changes)
    return d


def controlled_histories():
    """Alternative histories, SAME IDs/counts/timing; ONLY metric values differ."""
    t, libs = task(), libraries()
    f = [row("f1", .8, .5), row("f2", .4, .8), row("f3", .8, .5), row("f4", .4, .8)]
    g = [row("g1", .8, .5, family="FAMILY_G"), row("g2", .4, .8, family="FAMILY_G"),
         row("g3", .4, .5, family="FAMILY_G")]
    favourable = [batch(t, libs[0], 1, f), batch(t, libs[1], 2, g)]
    counterexamples = deepcopy(favourable)
    for r in counterexamples[0]["rows"][2:]:
        r["values"].update(objective_a=.4, objective_b=.5)
    return t, libs, favourable, counterexamples
