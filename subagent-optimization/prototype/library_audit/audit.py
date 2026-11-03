"""Bounded local structure/asset audit. No prediction, generation or approval.

CSV uses the public exact SMILES header. SMI is inspection-only and needs CSV
conversion before the public CReM route. No raw/canonical structures are emitted.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re

try:
    from rdkit import Chem, rdBase
except ImportError:
    Chem = rdBase = None

MAX_BYTES = 16 * 1024 * 1024  # File-inspection bound, not a scientific budget.


class AuditError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def normalization_policy_id():
    if Chem is None:
        raise AuditError("Existing RDKit required; no string-only chemistry fallback")
    return ("strict-canonical-isomeric-no-standardization-v2@rdkit-" + rdBase.rdkitVersion
            + ";legacy-stereo=" + str(int(Chem.GetUseLegacyStereoPerception()))
            + ";non-tetrahedral=" + str(int(Chem.GetAllowNontetrahedralChirality())))


def _parser(sanitize=True):
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.allowCXSMILES = False
    params.sanitize = sanitize
    params.removeHs = sanitize
    return params


def _records(raw, input_format):
    if not raw or len(raw) > MAX_BYTES:
        raise AuditError("Input must be nonempty and within the inspection size bound")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AuditError("UTF-8 input required") from exc
    if input_format == "smi":
        return text.splitlines(), []
    if input_format != "csv":
        raise AuditError("Only CSV and inspection-only SMI supported")
    try:
        records = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise AuditError("Malformed CSV") from exc
    if not records:
        raise AuditError("CSV header required")
    header = records[0]
    if len(set(header)) != len(header) or header.count("SMILES") != 1:
        raise AuditError("Exactly one unambiguous, case-sensitive SMILES header required")
    index = header.index("SMILES")
    if any(len(row) != len(header) for row in records[1:]):
        raise AuditError("Every CSV record must match the header width")
    return [row[index] for row in records[1:]], header


def _analyse(raw, input_format):
    policy = normalization_policy_id()
    records, header = _records(raw, input_format)
    canonical, invalid, unsupported, multicomponent = [], [], [], []
    for number, value in enumerate(records, 1):
        if not value.strip():
            invalid.append(number)
            continue
        if "|" in value:
            unsupported.append({"row": number, "reason": "CXSMILES_requires_review"})
            continue
        if re.search(r"@(?:SP|TB|OH|AL|TH)", value):
            unsupported.append({"row": number, "reason": "extended_stereo_requires_review"})
            continue
        with rdBase.BlockLogs():
            try:
                mol = Chem.MolFromSmiles(value, _parser())
                if mol is None:
                    invalid.append(number)
                    continue
                # Narrow first identity protocol. Never silently erase features.
                reasons = []
                if any(a.GetAtomicNum() == 0 or a.HasQuery() for a in mol.GetAtoms()):
                    reasons.append("query_or_dummy_atom")
                if any(a.GetNumRadicalElectrons() for a in mol.GetAtoms()):
                    reasons.append("radical")
                if any(str(b.GetBondType()) not in {"SINGLE", "DOUBLE", "TRIPLE", "AROMATIC"}
                       for b in mol.GetBonds()):
                    reasons.append("unsupported_bond")
                if mol.GetStereoGroups():
                    reasons.append("enhanced_stereo")
                # RDKit can silently discard impossible tetrahedral tags. Do
                # not qualify that loss as a complete input representation.
                raw_mol = Chem.MolFromSmiles(value, _parser(sanitize=False))
                tags = lambda m: sum(a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED
                                     for a in m.GetAtoms())
                if raw_mol is None or tags(raw_mol) != tags(mol):
                    reasons.append("discarded_chiral_annotation")
                if reasons:
                    unsupported.append({"row": number, "reason": ",".join(reasons)})
                    continue
                if len(Chem.GetMolFrags(mol)) > 1:
                    multicomponent.append(number)
                canonical.append(Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True))
            except Exception:
                invalid.append(number)  # Never include original structure/error text.
    ordered_unique = list(dict.fromkeys(canonical))
    complete = bool(records) and not invalid and not unsupported
    hash_values = lambda values: digest({"normalization_policy_id": policy, "values": values})
    report = {
        "schema_version": 1, "content_sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw), "input_format": input_format, "header": header,
        "row_count": len(records), "canonicalized_rows": len(canonical),
        "canonical_unique_count": len(ordered_unique),
        "duplicate_rows": len(canonical) - len(ordered_unique),
        "invalid_rows": invalid, "unsupported_rows": unsupported,
        "multicomponent_rows": multicomponent,
        "normalization_policy_id": policy, "rdkit_version": rdBase.rdkitVersion,
        "parser_settings": {"parseName": False, "allowCXSMILES": False,
                            "canonical": True, "isomericSmiles": True,
                            "sanitize": True, "removeHs": True,
                            "legacy_stereo": Chem.GetUseLegacyStereoPerception(),
                            "allow_nontetrahedral_chirality": Chem.GetAllowNontetrahedralChirality()},
        "normalized_identity_complete": complete,
        "normalized_input_set_sha256": hash_values(sorted(set(canonical))) if complete else None,
        "normalized_sequence_sha256": hash_values(ordered_unique) if complete else None,
        "normalized_multiset_sha256": hash_values(sorted(canonical)) if complete else None,
        "public_input_format_ready": input_format == "csv",
        "structure_scope_needs_review": bool(multicomponent or unsupported or invalid or not records),
        "approval_status": "not_reviewed", "capability_card_reviewed": False,
        "available_for_policy": False, "fragment_material_identity": "not_calculated",
        "scoring_or_model_execution": False,
    }
    return report, set(canonical) if complete else None


def audit_bytes(raw, input_format="csv"):
    return _analyse(raw, input_format)[0]


def read_asset(path):
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise AuditError("Explicit regular local file required")
    with source.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise AuditError("Asset exceeds the bounded inspection size")
    return raw


def compare_bytes(first, second, first_format="csv", second_format="csv"):
    a, aa = _analyse(first, first_format)
    b, bb = _analyse(second, second_format)
    complete = aa is not None and bb is not None
    return {"byte_identical": a["content_sha256"] == b["content_sha256"],
            "normalized_set_equal": aa == bb if complete else None,
            "normalized_sequence_equal": a["normalized_sequence_sha256"] == b["normalized_sequence_sha256"] if complete else None,
            "intersection_count": len(aa & bb) if complete else None,
            "first_unique_count": len(aa) if complete else None,
            "second_unique_count": len(bb) if complete else None,
            "actual_fragment_equivalence": "not_established"}


def verify_review_binding(subject, review):
    """Verify content binding only; never authenticate or manufacture approval."""
    required = {"asset_content_sha256", "normalized_input_set_sha256", "normalization_policy_id",
                "family_definition_sha256", "context_definition_sha256", "annotation_mapping_sha256"}
    if not required <= set(subject) or any(not isinstance(subject[k], str) or not subject[k] for k in required):
        return {"status": "needs_review", "reason": "incomplete_immutable_subject", "available_for_policy": False}
    expected = digest(subject)
    if review is None:
        return {"status": "needs_review", "reason": "no_review_record", "subject_sha256": expected,
                "available_for_policy": False}
    if review.get("subject_sha256") != expected:
        return {"status": "rejected", "reason": "stale_or_different_subject", "available_for_policy": False}
    if review.get("decision") != "approved" or not review.get("reviewer_identity"):
        return {"status": "needs_review", "reason": "no_positive_identified_review", "available_for_policy": False}
    return {"status": "binding_matches", "reason": "review_authority_not_authenticated",
            "subject_sha256": expected, "available_for_policy": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Explicit existing local library file")
    parser.add_argument("--format", required=True, choices=("csv", "smi"))
    args = parser.parse_args()
    try:
        print(json.dumps(audit_bytes(read_asset(args.input), args.format), indent=2))
    except (AuditError, OSError) as exc:
        parser.exit(2, "Audit unavailable: " + str(exc) + "\n")
