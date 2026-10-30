"""Boltzyme tools' bounded input structure inspection, not quality prediction.

No filesystem, subprocess, network, or production-wrapper access. Gemmi is optional
at import time. Receipts must be stored by the caller in the owning profile.
"""

import gzip
import hashlib
import io
import json
import math
from pathlib import PurePosixPath
import re
import stat
import zipfile
import zlib


MIB = 1024 ** 2
# Connector inspection budgets, not universal tool or biological limits.
MAX_SUMMARY_BYTES = 256 * 1024
MAX_INPUT_BYTES = 256 * MIB
MAX_LOCAL_EXPANDED = 256 * MIB
MAX_LOCAL_CANDIDATES = 128
MAX_LOCAL_MODELS = 100
STANDARD = frozenset("ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL".split())
ENDINGS = (".mmcif.gz", ".cif.gz", ".pdb.gz", ".mmcif", ".cif", ".pdb")
# Each tuple is (decompressed bytes per structure, residues per model,
# atoms per model). Some entries are worker hard limits; others only bound
# local inspection. InspectionLimit below discloses the latter as unchecked.
# protein_structure is shared by the other opted-in enzyme structure utilities.
PROFILES = {
    "deepallo": (50 * MIB, 20000, 500000),
    "enzycontrol": (50 * MIB, 20000, 500000),
    "Enzyme_RFD3": (10 * MIB, 1024, 20000),
    "Mol_Probity": (50 * MIB, 20000, 500000),
    "Catalytic_Geometry": (50 * MIB, 20000, 500000),
    "protein_structure": (50 * MIB, 20000, 500000),
}


class InspectionLimit(ValueError):
    """Local work limit, not proof that a worker would reject the input."""


def _ending(name):
    return next((suffix for suffix in ENDINGS if name.lower().endswith(suffix)), None)


def _bounded_read(stream, limit, *, limit_error=ValueError):
    result = stream.read(limit + 1)
    if len(result) > limit:
        message = "Local decompressed member-byte inspection budget reached" if limit_error is InspectionLimit else "Structure exceeds the decompressed member byte limit"
        raise limit_error(message)
    return result


def _unpack(data, ending, limit, *, limit_error=ValueError):
    if ending.endswith(".gz"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
                contents = _bounded_read(stream, limit, limit_error=limit_error)
        except (OSError, EOFError, zlib.error) as exc:
            raise ValueError("Structure is not a valid gzip file") from exc
        if not contents:
            raise ValueError("Decompressed structure is empty")
        return contents, ending[:-3]
    if not data:
        raise ValueError("Structure is empty")
    if len(data) > limit:
        message = "Local member-byte inspection budget reached" if limit_error is InspectionLimit else "Structure exceeds the member byte limit"
        raise limit_error(message)
    return data, ending


def _candidate_id(name, profile):
    ending = _ending(name)
    if ending is None:
        raise ValueError("Unsupported structure filename")
    candidate = PurePosixPath(name).name[:-len(ending)]
    if profile == "Mol_Probity":
        candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._-")[:180]
    if not candidate:
        raise ValueError("Structure candidate ID is empty")
    if len(candidate) > 256:
        raise InspectionLimit("Structure candidate ID exceeds local 256-character inventory budget")
    return candidate


def _ligand_bundle(archive, infos, requirements, summary):
    """Inspect the versioned ZIP protocol, not CCTBX restraint chemistry."""
    from .contracts import ContractStore, ValidationReport, validate_schema

    store = ContractStore()
    schema = requirements.get("zip_manifest_schema") or store.file_rule("Mol_Probity", "input_path")["zip_manifest_schema"]
    limits = store.limits["Mol_Probity"]["ligand_bundle"]
    members = {info.filename: info for info in infos if not info.is_dir()}
    def read(name, maximum):
        if name not in members:
            raise ValueError("Ligand manifest references a missing ZIP member")
        if not 0 < members[name].file_size <= maximum:
            raise ValueError("Ligand manifest/dictionary is empty or exceeds its byte limit")
        with archive.open(members[name]) as stream:
            return _bounded_read(stream, maximum)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate ligand manifest JSON key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("Nonfinite ligand manifest JSON constant")
    document = json.loads(read("ligand_manifest.json", limits["maximum_manifest_bytes"]).decode("utf-8-sig"),
                          object_pairs_hook=pairs, parse_constant=invalid_constant)
    report = ValidationReport()
    validate_schema(document, schema, report, "ligand_manifest")
    if report.errors:
        raise ValueError("Invalid ligand manifest: " + report.errors[0])
    def member(name):
        path = PurePosixPath(name)
        if (len(name) > 1024 or path.is_absolute() or str(path) != name or ".." in path.parts or "\\" in name
                or ":" in name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
            raise ValueError("Unsafe or noncanonical ligand manifest member path")
        if name not in members:
            raise ValueError("Ligand manifest references a missing ZIP member")
        return name
    entries, dictionaries = {}, {}
    protected = STANDARD | {"MSE", "HOH", "WAT", "DOD", "A", "C", "G", "U", "T", "DA", "DC", "DG", "DT", "DU"}
    for entry in document["structures"]:
        name = member(entry["path"])
        if name in entries or _ending(name) is None:
            raise ValueError("Repeated or unsupported ligand manifest structure path")
        selectors, components = set(), {}
        for binding in entry["ligands"]:
            dictionary = member(binding["dictionary"])
            if dictionary not in dictionaries:
                if len(dictionaries) >= limits["maximum_dictionaries"]:
                    raise ValueError("Too many distinct ligand dictionary paths")
                contents = read(dictionary, limits["maximum_dictionary_bytes"])
                dictionaries[dictionary] = hashlib.sha256(contents).hexdigest()
                if dictionaries[dictionary] != binding["sha256"]:
                    raise ValueError("Ligand dictionary SHA-256 mismatch")
                try:
                    import gemmi
                except ImportError:
                    summary["ligand_dictionary_syntax_unchecked"] = True
                else:
                    cif = gemmi.cif.read_string(contents.decode("utf-8-sig"))
                    atom_count = sum(len(block.find_values("_chem_comp_atom.atom_id")) for block in cif)
                    if not 0 < atom_count <= limits["maximum_dictionary_atoms"]:
                        raise ValueError("Ligand dictionary atom table is empty or exceeds its atom limit")
            if dictionaries[dictionary] != binding["sha256"]:
                raise ValueError("Ligand dictionary SHA-256 mismatch")
            component = binding["component_id"]
            if component in protected:
                raise ValueError("Custom dictionary cannot replace a protected polymer/water component")
            if component in components and components[component] != binding["sha256"]:
                raise ValueError("Conflicting dictionaries for one candidate component")
            components[component] = binding["sha256"]
            chain, insertion = binding["chain_id"], binding.get("insertion_code", "")
            if (not chain.strip() or any(ord(c) < 32 for c in chain)
                    or insertion and (insertion.isspace() or ord(insertion) < 32)):
                raise ValueError("Invalid custom ligand chain or insertion code")
            selector = (chain, binding["residue_number"], insertion)
            if selector in selectors:
                raise ValueError("Repeated or conflicting custom ligand residue selector")
            selectors.add(selector)
            mapping = binding["atom_mapping"]
            if len(set(mapping.values())) != len(mapping):
                raise ValueError("Ligand atom_mapping indices must be unique")
            try:
                from rdkit import Chem, rdBase
            except ImportError:
                summary["ligand_reference_unchecked"] = True
            else:
                with rdBase.BlockLogs():
                    molecule = Chem.MolFromSmiles(binding["smiles"])
                if molecule is None or not molecule.GetNumAtoms() or any(a.GetAtomicNum() == 1 for a in molecule.GetAtoms()):
                    raise ValueError("Custom ligand reference SMILES must describe a nonempty heavy-atom molecule")
                if (any(a.GetIsotope() or a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for a in molecule.GetAtoms())
                        or any(b.GetStereo() != Chem.BondStereo.STEREONONE for b in molecule.GetBonds())):
                    raise ValueError("Custom ligand bundle v1 does not support specified stereo/isotopes; do not strip labels to bypass this")
                if set(mapping.values()) != set(range(molecule.GetNumAtoms())):
                    raise ValueError("Ligand atom_mapping must cover every reference SMILES atom index")
        entries[name] = entry["ligands"]
    if set(entries) & dictionaries.keys():
        raise ValueError("Dictionary files must not also be candidate structures")
    if any(_ending(name) and name not in entries and name not in dictionaries for name in members):
        raise ValueError("Every structure/dictionary CIF must be declared in ligand_manifest.json")
    return entries


def _bound_ligands(structure, bindings):
    """Check selectors and atom-name mappings without registering dictionaries."""
    if not bindings:
        return
    if len(structure) != 1:
        raise ValueError("Custom ligand bundles require single-model candidates")
    declared = {(b["component_id"], b["chain_id"], b["residue_number"], b.get("insertion_code", "")) for b in bindings}
    for binding in bindings:
        matches = [residue for chain in structure[0] if chain.name == binding["chain_id"]
                   for residue in chain if residue.seqid.num == binding["residue_number"]
                   and residue.seqid.icode.strip() == binding.get("insertion_code", "")]
        if len(matches) != 1 or matches[0].name != binding["component_id"]:
            raise ValueError("Custom ligand residue/component selector is missing or ambiguous")
        residue = matches[0]
        if any(atom.altloc.strip("\x00 ") for atom in residue):
            raise ValueError("Custom ligand has ambiguous alternate locations")
        if {atom.name for atom in residue if atom.element.atomic_number > 1} != set(binding["atom_mapping"]):
            raise ValueError("Custom ligand atom_mapping does not match structure heavy-atom names")
        if any(atom.element.name == "D" for atom in residue):
            raise ValueError("Custom isotopic ligand hydrogens are unsupported by bundle v1")
        for chain in structure[0]:
            for other in chain:
                if other.name == binding["component_id"] and (other.name, chain.name, other.seqid.num, other.seqid.icode.strip()) not in declared:
                    raise ValueError("Every instance of a custom ligand component must be bound explicitly")


def _candidates(data, extension, profile, summary, filename, requirements):
    """Yield bytes, format, candidate ID; never extract archive members."""
    member_limit = PROFILES[profile][0]
    if extension != ".zip":
        ending = _ending(extension)
        if ending is None:
            raise ValueError("Unsupported structure extension")
        yield data, ending, _candidate_id(filename, profile) if filename else None, []
        return
    if profile not in {"Mol_Probity", "Catalytic_Geometry", "protein_structure"}:
        raise ValueError("This structure profile does not support ZIP input")
    entry_limit = 1000 if profile == "Mol_Probity" else 100000
    expanded_limit = 2 * 1024 ** 3 if profile == "Mol_Probity" else 100 * 1024 ** 3
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > entry_limit:
            raise ValueError(f"ZIP exceeds {entry_limit} entries")
        total = 0
        identifiers = set()
        selected = []
        # Check *all* metadata before consuming any member, including ignored files.
        for info in infos:
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in info.filename
                    or ":" in info.filename or any(ord(c) < 32 or ord(c) == 127 for c in info.filename)
                    or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1
                    or profile == "Mol_Probity" and (str(path) != info.filename.rstrip("/")
                        or stat.S_IFMT(info.external_attr >> 16) not in {0, stat.S_IFREG, stat.S_IFDIR}
                        or path.suffix.lower() in {".py", ".sh", ".exe"})):
                raise ValueError("Unsafe or encrypted ZIP member")
            total += info.file_size
            if total > expanded_limit:
                raise ValueError("ZIP exceeds expanded byte limit")
            if profile != "protein_structure" and info.file_size > 200 * max(1, info.compress_size):
                raise ValueError("ZIP member compression ratio exceeds 200")
        bindings = None
        if profile == "Mol_Probity" and any(info.filename == "ligand_manifest.json" and not info.is_dir() for info in infos):
            bindings = _ligand_bundle(archive, infos, requirements, summary)
            summary["ligand_bundle_schema"] = "molprobity-ligand-bundle.v1"
        for info in infos:
            if bindings is not None and info.filename not in bindings:
                continue
            ending = _ending(info.filename)
            if info.is_dir() or ending is None:
                continue
            candidate = _candidate_id(info.filename, profile)
            if candidate in identifiers:
                raise ValueError("Duplicate structure candidate IDs in ZIP")
            identifiers.add(candidate)
            if info.file_size > member_limit:
                limit_error = InspectionLimit if profile == "protein_structure" else ValueError
                raise limit_error("ZIP structure exceeds member byte limit" if limit_error is ValueError
                                  else "ZIP structure exceeds local member inspection budget")
            selected.append((info, ending, candidate))
        if not selected:
            raise ValueError("ZIP contains no supported structures")
        metadata = [info for info in infos if not info.is_dir() and _ending(info.filename) is None]
        summary["mapping_inventory_complete"] = not any(
            "mapping" in info.filename.lower() or PurePosixPath(info.filename).suffix.lower()
            in {".json", ".csv", ".trb", ".npz", ".pkl", ".pickle", ".pt", ".yaml", ".yml"}
            for info in metadata)
        if profile == "Catalytic_Geometry" and any(
                PurePosixPath(info.filename).parts[:1] == ("backbones",) for info in infos):
            summary["mapping_inventory_complete"] = False
        expanded = 0
        for index, (info, ending, candidate) in enumerate(selected):
            if index >= MAX_LOCAL_CANDIDATES:
                raise InspectionLimit("Local structure inspection candidate budget reached")
            if expanded + info.file_size > MAX_LOCAL_EXPANDED:
                raise InspectionLimit("Local structure inspection expanded-byte budget reached")
            with archive.open(info) as stream:
                contents = _bounded_read(stream, member_limit)
            if (profile == "Mol_Probity" and bindings is None and ending in {".cif", ".mmcif"}
                    and b"_chem_comp_atom." in contents[:MIB] and b"_atom_site." not in contents[:MIB]):
                raise ValueError("Ligand restraint CIFs require a root ligand_manifest.json; they are not candidate structures")
            expanded += len(contents)
            if expanded > MAX_LOCAL_EXPANDED:
                raise InspectionLimit("Local structure inspection expanded-byte budget reached")
            yield contents, ending, candidate, bindings[info.filename] if bindings is not None else []


def _parse(data, ending, gemmi):
    text = data.decode("utf-8-sig")
    if ending == ".pdb":
        # Gemmi permissively fills absent numeric fields with zero. Missing
        # coordinates must not become a finite, apparently usable structure.
        for number, line in enumerate(text.splitlines(), 1):
            if line[:6].strip() not in {"ATOM", "HETATM"}:
                continue
            if len(line) < 54:
                raise ValueError(f"PDB atom record {number} is shorter than 54 columns")
            if not line[22:26].strip():
                raise ValueError(f"PDB atom record {number} requires an explicit residue number")
            try:
                xyz = [float(line[start:start + 8]) for start in (30, 38, 46)]
            except ValueError as exc:
                raise ValueError(f"PDB atom record {number} requires explicit numeric XYZ coordinates") from exc
            if not all(math.isfinite(value) for value in xyz):
                raise ValueError(f"PDB atom record {number} contains nonfinite coordinates")
        return gemmi.read_pdb_string(text)
    document = gemmi.cif.read_string(text)
    if len(document) != 1:
        raise ValueError("Structure CIF must contain exactly one data block")
    return gemmi.make_structure_from_block(document.sole_block())


def _inventory(structure, profile, allow_ensemble, gemmi):
    if not len(structure):
        raise ValueError("Structure contains no models or atoms")
    if len(structure) != 1 and not allow_ensemble:
        raise ValueError("Structure must contain exactly one model; ensembles require contextual rules")
    if len(structure) > MAX_LOCAL_MODELS:
        raise InspectionLimit("Local model inspection budget reached")
    models = []
    total_atoms = 0
    for index, model in enumerate(structure):
        rows, chains = [], set()
        atom_count = 0
        for chain in model:
            if chain.name in chains and profile != "protein_structure":
                raise ValueError("Structure has duplicate/disordered chain IDs")
            chains.add(chain.name)
            seen = set()
            for residue in chain:
                insertion = residue.seqid.icode.strip()
                key = (residue.seqid.num, insertion, residue.het_flag, residue.name)
                if key in seen:
                    raise ValueError("Structure has duplicate/disordered residue IDs")
                seen.add(key)
                atoms = {}
                for atom in residue:
                    altloc = atom.altloc.strip("\x00 ")
                    if not atom.name.strip():
                        raise ValueError("Structure contains an empty atom name")
                    atom_key = (atom.name, altloc)
                    if atom_key in atoms:
                        raise ValueError("Structure has duplicate atom IDs including alternate location")
                    xyz = (atom.pos.x, atom.pos.y, atom.pos.z)
                    if not all(math.isfinite(v) for v in xyz):
                        raise ValueError("Structure contains nonfinite coordinates")
                    atoms[atom_key] = xyz
                    atom_count += 1
                    total_atoms += 1
                    if atom_count > PROFILES[profile][2] and profile in {"Mol_Probity", "deepallo", "enzycontrol", "protein_structure"}:
                        raise InspectionLimit("Local per-model atom inspection budget reached")
                    if atom_count > PROFILES[profile][2]:
                        raise ValueError("Structure exceeds per-model atom limit")
                    if total_atoms > 500000:
                        raise InspectionLimit("Local total-atom inspection budget reached")
                rows.append({"chain_id": chain.name, "residue_number": key[0],
                             "insertion_code": insertion, "residue_name": residue.name,
                             "protein": residue.het_flag == "A",
                             "amino_acid": gemmi.find_tabulated_residue(residue.name).is_amino_acid(),
                             "_atoms": atoms})
                if len(rows) > PROFILES[profile][1] and profile in {"Mol_Probity", "deepallo", "enzycontrol", "protein_structure"}:
                    raise InspectionLimit("Local per-model residue inspection budget reached")
                if len(rows) > PROFILES[profile][1]:
                    raise ValueError("Structure exceeds per-model residue limit")
        if not atom_count:
            raise ValueError("Structure model contains no atoms")
        models.append({"model_index": index, "residues": rows, "atom_count": atom_count})
    return models


def _atom(row, name):
    matches = [xyz for (atom, alt), xyz in row["_atoms"].items() if atom == name]
    if len(matches) != 1:
        raise ValueError(f"Residue {row['chain_id']}{row['residue_number']} atom {name} is missing or ambiguous")
    return matches[0]


def _selected_chain(models, payload):
    chain = payload.get("chain_id")
    if chain is None:
        raise InspectionLimit("Selected chain_id is unavailable; chain-dependent inspection unchecked")
    rows = [r for r in models[0]["residues"] if r["chain_id"] == chain]
    if not rows:
        raise ValueError(f"Selected chain {chain!r} is missing")
    return rows


def _unambiguous(rows):
    if any(alt for row in rows for _, alt in row["_atoms"]):
        raise ValueError("Selected structure has ambiguous alternate locations")
    protein_ids = [(row["chain_id"], row["residue_number"], row["insertion_code"]) for row in rows if row["protein"]]
    if len(set(protein_ids)) != len(protein_ids):
        raise ValueError("Selected structure has duplicate/disordered protein residue IDs")


def _deepallo(models, payload):
    rows = [r for r in _selected_chain(models, payload) if r["protein"]]
    _unambiguous(rows)
    if len(rows) <= 10 or any(r["residue_name"] not in STANDARD for r in rows):
        raise ValueError("Selected chain must contain more than 10 standard amino-acid residues")
    if len({r["residue_number"] for r in rows}) != len(rows):
        raise ValueError("DeepAllo does not support duplicate residue numbering with insertion codes")
    for row in rows:
        _atom(row, "CA")


def _enzycontrol(models, payload):
    selected = _selected_chain(models, payload)
    if any(not r["protein"] and r["amino_acid"] for r in selected):
        raise ValueError("Selected chain contains a nonstandard protein residue")
    rows = [r for r in selected if r["protein"]]
    _unambiguous(rows)
    if not 2 <= len(rows) <= 2000 or any(r["residue_name"] not in STANDARD for r in rows):
        raise ValueError("Selected chain must contain 2 to 2000 standard amino-acid residues")
    labels = {str(r["residue_number"]) + r["insertion_code"] for r in rows}
    motifs = payload.get("motif_residues")
    if motifs is None:
        raise InspectionLimit("motif_residues unavailable; motif existence unchecked")
    if set(motifs) - labels:
        raise ValueError("Motif residues are absent from the selected chain")
    if len(set(motifs)) >= len(rows):
        raise ValueError("At least one non-motif residue must remain")
    for row in rows:
        n, ca, c = (_atom(row, name) for name in ("N", "CA", "C"))
        u, v = [a - b for a, b in zip(n, ca)], [a - b for a, b in zip(c, ca)]
        cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        if math.sqrt(sum(x*x for x in cross)) < 1e-3:
            raise ValueError("Selected residue has degenerate N/CA/C backbone geometry")


def _rfd3_advanced(payload):
    # Uploads use the request-preparation default: absent flag means disabled.
    enabled = payload.get("advanced_settings_enabled", False)
    if enabled is not True and not (isinstance(enabled, str) and enabled.strip().lower() == "true"):
        return {}
    raw = payload.get("advanced_settings")
    if isinstance(raw, str) and raw.strip().lower() == "false":
        return {}
    if raw is None or raw == [] or (isinstance(raw, str) and raw.strip().lower() in {"", "true"}):
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("advanced_settings must be an object")
    advanced = dict(raw)
    for field in ("select_fixed_atoms", "redesign_motif_sidechains", "geometry_constraints", "partial_t"):
        if field in payload and payload[field] not in (None, "", {}, []):
            advanced[field] = payload[field]
    fixed = advanced.get("select_fixed_atoms")
    if isinstance(fixed, str) and fixed.strip().lower() in {"true", "false"}:
        fixed = fixed.strip().lower() == "true"
    if fixed is True:
        advanced["select_fixed_atoms"] = True
    elif fixed is None or fixed is False or fixed == "" or fixed == []:
        advanced.pop("select_fixed_atoms", None)
    elif not isinstance(fixed, dict):
        raise ValueError("select_fixed_atoms must be a dictionary or a true/false selection flag")
    if isinstance(advanced.get("redesign_motif_sidechains"), str):
        advanced["redesign_motif_sidechains"] = advanced["redesign_motif_sidechains"].strip().lower() == "true"
    for field in ("partial_t", "geometry_constraints"):
        if isinstance(advanced.get(field), str) and advanced[field].strip().lower() in {"", "false"}:
            advanced.pop(field)
    return advanced


def _rfd3(models, payload):
    rows = models[0]["residues"]
    _unambiguous(rows)
    advanced = _rfd3_advanced(payload)
    fixed = advanced.get("select_fixed_atoms", {})
    selections = {}
    motifs = payload.get("motif_residues")
    ligands = payload.get("ligand")
    if motifs is None or ligands is None:
        raise InspectionLimit("RFD3 motif/ligand selections unavailable; reference checks unchecked")
    for label in motifs:
        match = re.fullmatch(r"([A-Za-z0-9])(-?\d+)", label)
        matches = [] if match is None else [r for r in rows if r["protein"]
                   and r["chain_id"] == match[1] and r["residue_number"] == int(match[2])
                   and not r["insertion_code"] and r["residue_name"] in STANDARD]
        if len(matches) != 1:
            raise ValueError(f"Motif {label} must uniquely identify a standard amino-acid residue")
        selections[label] = matches[0]
    for ligand in ligands.split(","):
        matches = [r for r in rows if r["residue_name"] == ligand]
        if len(matches) != 1:
            raise ValueError(f"Ligand {ligand} must occur exactly once")
        selections[ligand] = matches[0]
    for label, row in selections.items():
        default = "BKBN" if label in motifs and advanced.get("redesign_motif_sidechains") is True else "ALL"
        spec = "ALL" if fixed is True else fixed.get(label, default)
        if not isinstance(spec, str) or not spec:
            raise ValueError("Fixed atom selections must be nonempty atom-name strings")
        names = {"ALL": (), "TIP": (), "BKBN": ("N", "CA", "C", "O")}.get(spec)
        if names is None:
            names = spec.split(",")
        # The worker imposes BKBN only on motif residues, not ligand components.
        if spec == "BKBN" and label not in motifs:
            names = ()
        for name in names:
            _atom(row, name)
    for rule in advanced.get("geometry_constraints", []) or []:
        for ref in rule.get("atoms", []):
            row = selections.get(ref.get("residue", ref.get("ligand")))
            if row is None:
                raise ValueError("Geometry constraint references an unselected residue/ligand")
            _atom(row, ref["atom"])
    if advanced.get("partial_t") is not None:
        protein = [r for r in rows if r["protein"] and r["residue_name"] in STANDARD]
        if len(protein) > 512 or not payload.get("min_length", 0) <= len(protein) <= payload.get("max_length", 512):
            raise ValueError("partial_t input protein length is outside the supported/requested range")
        previous = None
        for row in protein:
            if row["insertion_code"]:
                raise ValueError("partial_t does not support insertion codes")
            for name in ("N", "CA", "C"):
                _atom(row, name)
            if previous is not None and previous["chain_id"] == row["chain_id"]:
                distance = math.dist(_atom(previous, "C"), _atom(row, "N"))
                if not 0.5 <= distance <= 2.5:
                    raise ValueError("partial_t requires a connected input backbone (C-N 0.5..2.5 A)")
            previous = row


def _syntax_only(models, payload):
    return None


CHECKS = {"deepallo": _deepallo, "enzycontrol": _enzycontrol, "Enzyme_RFD3": _rfd3,
          "Mol_Probity": _syntax_only, "Catalytic_Geometry": _syntax_only,
          "protein_structure": _syntax_only}


def _requirements(models, requirements, payload, *, ending=None):
    """Only opt-in, worker-documented selections; no quality thresholds."""
    rows = models[0]["residues"]
    if requirements.get("pdb_separate_ligand_chains") and ending == ".pdb":
        chain_rows = [row for model in models for row in model["residues"]]
        protein = {row["chain_id"] for row in chain_rows if row["protein"]}
        ligands = {row["chain_id"] for row in chain_rows if not row["protein"] and row["residue_name"] != "HOH"}
        if protein & ligands:
            raise ValueError("PLACER PDB input requires separate protein and ligand chain IDs; prepare a reviewed copy and update predict_ligand without changing coordinates.")
    chain_field = requirements.get("chains_field")
    if chain_field and payload.get(chain_field):
        chains = payload[chain_field]
        if requirements.get("chain_scalar"):
            chains = [chains]
        if not isinstance(chains, list) or any(not any(row["chain_id"] == chain for row in rows) for chain in chains):
            raise ValueError(f"{chain_field}: selected chain is missing")
    residue_field = requirements.get("residues_field")
    if residue_field:
        sites = payload.get(residue_field)
        if not isinstance(sites, str) or not sites:
            raise InspectionLimit(f"{residue_field}: residue selection is unavailable")
        for site in sites.split(","):
            match = re.fullmatch(r"(-?\d+)_([A-Za-z0-9])", site)
            if not match:
                raise ValueError(f"{residue_field}: expected residue_chain entries")
            number, chain = match.groups()
            selected = [row for row in rows if row["protein"] and row["chain_id"] == chain
                        and row["residue_number"] == int(number) and not row["insertion_code"]]
            if len(selected) != 1:
                raise ValueError(f"{residue_field}: residue {site} is missing or ambiguous")
            _atom(selected[0], "CA")
    if requirements.get("backbone_atoms"):
        if not any(all(any(atom == name for atom, _ in row["_atoms"])
                       for name in requirements["backbone_atoms"]) for row in rows if row["protein"] or row["residue_name"] == "MSE"):
            raise ValueError("Input has no usable protein backbone with the required atoms")
    ligand_field = requirements.get("ligand_field")
    if ligand_field:
        label = payload.get(ligand_field)
        if label is None:
            raise InspectionLimit(f"{ligand_field}: ligand selection is unavailable")
        match = re.fullmatch(r"([A-Z]+)-([A-Z]+)-(\d+)", label)
        selected = [] if not match else [row for row in rows if row["chain_id"] == match[1]
            and row["residue_name"] == match[2] and row["residue_number"] == int(match[3])]
        if len(selected) != 1:
            raise ValueError(f"{ligand_field}: requested ligand is missing or ambiguous")


def _ensemble_allowed(payload):
    template = payload.get("reaction_template")
    checks = template.get("checks") if isinstance(template, dict) else None
    return (isinstance(checks, list) and any(isinstance(rule, dict) and rule.get("type") == "ensemble_occupancy"
            for rule in checks))


def _compact(models):
    return [{"model_index": model["model_index"], "atom_count": model["atom_count"],
             "residues": [{**{k: v for k, v in row.items() if k != "_atoms"},
                           "atoms": [[name, alt] for name, alt in row["_atoms"]]}
                          for row in model["residues"]]} for model in models]


def inspect_structure(data: bytes, extension: str, profile: str, payload: dict, report, *, filename=None, requirements=None) -> dict:
    """Append diagnostics and return a JSON receipt <= MAX_SUMMARY_BYTES.

    ``complete`` covers implemented checks AND retained inventory, not native
    worker readiness. ``truncated`` prohibits assuming absent inventory is absent
    in the input. Single-file candidate IDs use filename if supplied, else None.
    Batch member failures are candidate-local; all-invalid batches fail overall.
    Coordinates are checked in memory but never persisted in the receipt.
    """
    summary = {"profile": profile, "complete": False, "truncated": False,
               "mapping_inventory_complete": False, "candidates": []}
    if profile not in PROFILES:
        report.errors.append("Unknown semantic structure profile")
        return summary
    if not data:
        report.errors.append("Structure input is empty")
        return summary
    if len(data) > MAX_INPUT_BYTES:
        report.warnings.append("Structure exceeds the local 256 MiB input budget; inspection unchecked")
        return summary
    extension = "." + extension.lower().lstrip(".")
    batch = extension == ".zip"
    summary["mapping_inventory_complete"] = not batch
    source = payload.get("input_source") or "auto"
    if (profile == "Catalytic_Geometry" and batch and isinstance(source, str)
            and source.strip().lower() not in {"auto", "generic"}):
        report.warnings.append("Native adapter/output-kind eligibility is unchecked for this explicit ZIP input_source; required source-specific mappings and bundle contents were not validated.")
    information = {
        "Enzyme_RFD3": "Lightweight structure checks only; native RFD3/chemical-component processing was not executed.",
        "Mol_Probity": "Structure syntax/inventory only; MolProbity quality predictions are not performed.",
        "Catalytic_Geometry": "Structure inventory does not establish catalytic activity or evaluate catalytic geometry.",
    }
    if profile in information and hasattr(report, "info"):
        report.info.append(information[profile])
    if profile == "Enzyme_RFD3":
        try:
            advanced = _rfd3_advanced(payload)
        except ValueError as exc:
            report.errors.append(str(exc))
            return summary
        fixed = advanced.get("select_fixed_atoms", {})
        if isinstance(fixed, dict) and "TIP" in fixed.values():
            report.warnings.append("RFD3 TIP selected-atom semantics require native chemical-component processing and are unchecked.")
    if profile == "Catalytic_Geometry" and _ensemble_allowed(payload):
        report.warnings.append("Ensemble geometry checks are not implemented; only multimodel inventory was inspected.")
    try:
        import gemmi
    except ImportError:
        report.warnings.append("Gemmi is unavailable: PDB/CIF/mmCIF semantic structure inspection and dependent reference checks are unchecked.")
        gemmi = None
    valid = 0
    all_checked = True
    expanded = 0
    try:
        for contents, ending, candidate_id, bindings in _candidates(data, extension, profile, summary, filename, requirements or {}):
            # Worker discovery/decompression failures abort the batch; only
            # semantic parsing of successfully discovered bytes is per-candidate.
            limit_error = InspectionLimit if profile in {"deepallo", "enzycontrol", "protein_structure"} else ValueError
            contents, ending = _unpack(contents, ending, PROFILES[profile][0], limit_error=limit_error)
            expanded += len(contents)
            if expanded > MAX_LOCAL_EXPANDED:
                raise InspectionLimit("Local decompressed structure inspection budget reached")
            item = {"candidate_id": candidate_id, "valid": False, "models": []}
            try:
                if gemmi is None:
                    all_checked = False
                    continue
                structure = _parse(contents, ending, gemmi)
                if bindings:
                    _bound_ligands(structure, bindings)
                    report.warnings.append("Custom ligand dictionary/reference graph agreement, charges/hydrogens, CCTBX energy types and restraint targets remain unchecked locally; the worker must validate them. Bundle validity is not chemistry validity.")
                unknown_template = profile == "Catalytic_Geometry" and not isinstance(payload.get("reaction_template"), dict)
                models = _inventory(structure, profile, profile == "protein_structure" or unknown_template or
                                    (profile == "Catalytic_Geometry" and _ensemble_allowed(payload)), gemmi)
                item["models"] = _compact(models)
                if unknown_template and len(models) > 1 and hasattr(report, "info"):
                    report.info.append("Multimodel eligibility is deferred to joint reaction-template validation.")
                CHECKS[profile](models, payload)
                if profile == "protein_structure":
                    _requirements(models, requirements or {}, payload, ending=ending)
                item["valid"] = True
                valid += 1
            except InspectionLimit as exc:
                report.warnings.append(str(exc))
                all_checked = False
            except (ValueError, RuntimeError, UnicodeError, TypeError, KeyError, AttributeError, OSError, EOFError) as exc:
                # Parser exceptions may quote whole records; keep diagnostics bounded.
                item["error"] = str(exc)[:300]
                if batch and profile != "protein_structure" and not bindings:
                    report.warnings.append(f"Candidate {candidate_id!r} is invalid: {item['error']}")
                else:
                    report.errors.append(item["error"])
            summary["candidates"].append(item)
            if len(json.dumps(summary, ensure_ascii=True).encode("utf-8")) > MAX_SUMMARY_BYTES:
                summary["candidates"].clear()
                summary["truncated"] = True
                all_checked = False
                report.warnings.append("Structure inventory exceeds 256 KiB receipt budget; inventory cleared and cross-file validation unchecked.")
                break
        if batch and not valid and all_checked:
            report.errors.append("No valid structure candidates were found")
        summary["complete"] = all_checked and not report.errors
    except InspectionLimit as exc:
        summary["truncated"] = True
        report.warnings.append(str(exc) + "; remaining structures unchecked")
    except (ValueError, OSError, EOFError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        report.errors.append(str(exc)[:300])
    if profile == "Catalytic_Geometry" and batch and not summary["mapping_inventory_complete"]:
        report.warnings.append("ZIP mapping metadata/adapters are uninspected (mapping_inventory_complete=false); mapping-key reference checks remain unchecked.")
    if summary.get("ligand_bundle_schema"):
        report.warnings.append("Custom-ligand ZIP forwarding, declared-structure billing and deployment of the dictionary-aware worker remain unverified through Node; local inspection is not a live integration check.")
    if summary.get("ligand_dictionary_syntax_unchecked"):
        report.warnings.append("Gemmi is unavailable: custom dictionary CIF syntax and atom-count checks remain unchecked.")
    if summary.get("ligand_reference_unchecked"):
        report.warnings.append("RDKit is unavailable: custom reference SMILES syntax, atom-index coverage and unsupported stereo/isotope checks remain unchecked.")
    return summary
