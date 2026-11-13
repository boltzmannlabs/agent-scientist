"""Common local checks for this pair; no submission client or policy decisions.

Frozen observations/feedback_policy copies remain unmodified. Their host-supplied
facts still require actual chemistry, eligibility and pose/provenance checks.
"""

import math
import statistics

from feedback_policy import require
from observations import verified_file


def verified_packet_file(root, relative_path, manifest_rows):
    """Accept JSON integer or CSV decimal-text byte counts, retaining hash checks."""
    normalized = []
    for row in manifest_rows:
        size = row.get('bytes')
        require(type(size) is int or
                (isinstance(size, str) and size.isascii() and size.isdecimal()),
                'Manifest bytes must be an integer or decimal text')
        require(int(size) >= 0, 'Manifest bytes cannot be negative')
        normalized.append({**row, 'bytes': str(size)})
    return verified_file(root, relative_path, normalized)


def confirmed_panel_summary(identities, records):
    """Summarize ten committed slots using already verified final observations.

    Each record binds identity, role, status, score, pose_verified and
    joint_eligible. The calling workflow establishes those fields from evidence;
    this function does not validate a molecular pose or a predictor by itself.
    It deliberately does not use legacy summarize_final's measurement-only mean.
    """
    require(isinstance(identities, list) and len(identities) == 10,
            'Exactly ten committed slots are required')
    present = [identity for identity in identities if identity is not None]
    require(all(isinstance(identity, str) and identity for identity in present)
            and len(set(present)) == len(present), 'Unique nonempty committed identities required')
    indexed = {}
    for row in records:
        identity = row.get('identity')
        require(isinstance(identity, str) and identity and identity not in indexed,
                'Final records must have unique nonempty identities')
        indexed[identity] = row
    measured, eligible_scores = [], []
    for identity in identities:
        row = indexed.get(identity, {})
        score = row.get('score')
        valid = (row.get('role') == 'generated' and row.get('status') == 'SUCCESS'
                 and row.get('pose_verified') is True
                 and type(score) in (int, float) and math.isfinite(score))
        if valid:
            measured.append(score)
            if row.get('joint_eligible') is True:
                eligible_scores.append(score)
    complete = len(eligible_scores) == 10
    return {
        'status': 'COMPLETE_ELIGIBLE_PANEL' if complete else 'INCOMPLETE_EVALUATION',
        'committed_slots': len(present), 'successful_pose_score_slots': len(measured),
        'confirmed_eligible_final_slots': len(eligible_scores), 'all_eligible': complete,
        'mean_native_vina': statistics.mean(eligible_scores) if complete else None,
        'median_native_vina': statistics.median(eligible_scores) if complete else None,
        'sample_sd_native_vina': statistics.stdev(eligible_scores) if complete else None,
        'minimum_native_vina': min(eligible_scores) if complete else None,
        'maximum_native_vina': max(eligible_scores) if complete else None,
    }
