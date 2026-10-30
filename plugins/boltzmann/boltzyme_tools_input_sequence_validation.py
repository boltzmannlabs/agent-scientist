"""Boltzyme tools' shared input molecule checks without execution or mutation."""


def validate_molecule(value, label, report, maximum_atoms_including_hydrogens=None):
    """Check original SMILES with an optional worker-backed hydrogen-inclusive cap."""
    if not isinstance(value, str) or not value.strip():
        report.errors.append(f"{label}: expected a valid nonempty molecule.")
        return
    try:
        from rdkit import Chem, rdBase
    except ImportError:
        reason = "SMILES validity is unchecked because RDKit is unavailable."
        if maximum_atoms_including_hydrogens is not None:
            reason += f" The {maximum_atoms_including_hydrogens}-atom hydrogen-inclusive limit is also unchecked."
        if not any(warning.endswith(reason) for warning in report.warnings):
            report.warnings.append(f"{label}: {reason}")
        return
    try:
        with rdBase.BlockLogs():
            molecule = Chem.MolFromSmiles(value)
            if molecule is None or not molecule.GetNumAtoms():
                report.errors.append(f"{label}: expected a valid nonempty molecule.")
            elif (maximum_atoms_including_hydrogens is not None
                  and Chem.AddHs(molecule).GetNumAtoms() > maximum_atoms_including_hydrogens):
                report.errors.append(f"{label}: molecule exceeds {maximum_atoms_including_hydrogens} atoms including hydrogens.")
    except (ValueError, RuntimeError, OverflowError):
        report.errors.append(f"{label}: molecule or hydrogen count could not be validated.")
