"""Bounded, non-executing file inspection. Unknown scientific checks stay explicit."""

import csv
import gzip
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import zlib

from .contracts import ValidationReport, validate_schema
from .boltzyme_tools_input_sequence_validation import validate_molecule

MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000
MAX_INVENTORY_BYTES = 256 * 1024


def _retain_inventory(report, kind, value):
    inventory = {"kind": kind, "data": value}
    if len(json.dumps(inventory, separators=(",", ":")).encode("utf-8")) > MAX_INVENTORY_BYTES:
        report.warnings.append("Input checks ran, but the local receipt inventory budget was exceeded; cross-file references remain unchecked.")
        return
    report.inventory = inventory


def _json(data, rule, report):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Nonfinite JSON constant")

    value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    validate_schema(value, rule.get("json_schema", {}), report, "file")
    if "json_schema" not in rule:
        report.warnings.append("JSON syntax checked; tool-specific content shape needs review.")
    if not report.errors and rule.get("content_checks"):
        from .enzyme_validation import validate_template
        validate_template(value, rule["json_schema"], report)
    if not report.errors and rule.get("inventory_kind"):
        _retain_inventory(report, rule["inventory_kind"], value)


def _finite(text):
    try:
        return math.isfinite(float(text))
    except (ValueError, TypeError):
        return False


def _sequence(value, spec, label, report):
    """Return only a temporary worker-equivalent view, never rewritten input data."""
    alphabet = spec.get("alphabet")
    whitespace = {"preserve": lambda s: s, "remove": lambda s: "".join(s.split()),
                  "strip_spaces": lambda s: s.strip().replace(" ", "")}
    if (not isinstance(alphabet, str) or not alphabet
            or spec.get("whitespace", "preserve") not in whitespace
            or not isinstance(spec.get("case_sensitive", True), bool)):
        report.warnings.append(f"{label}: sequence semantics unchecked; an explicit audited alphabet and normalization policy are required.")
        return None
    sequence = whitespace[spec.get("whitespace", "preserve")](value)
    if not spec.get("case_sensitive", True):
        sequence = sequence.upper()
    if not sequence or set(sequence) - set(alphabet):
        report.errors.append(f"{label}: sequence contains characters outside the documented alphabet or is empty.")
        return None
    return sequence


def _semantic_value(value, spec, label, report):
    if spec.get("smiles") is True:
        validate_molecule(value, label, report)
    elif "alphabet" in spec:
        _sequence(value, spec, label, report)
    else:
        report.warnings.append(f"{label}: unsupported semantic value kind remains unchecked.")


def _csv(data, rule, payload, report):
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), strict=True)
    headers = next(reader, [])
    forbidden = {name.strip().casefold() for name in rule.get("forbidden_columns", [])}
    if any(name.strip().casefold() in forbidden for name in headers):
        report.errors.append("CSV contains a column forbidden by this tool's documented input rules.")
        return
    normalize = (lambda s: s) if rule.get("header_case_sensitive", True) else str.casefold
    names = [normalize(h) for h in headers]
    if not names or any(not h.strip() for h in headers) or len(set(names)) != len(names):
        report.errors.append("CSV requires nonempty, unambiguous column headers.")
        return
    variants = rule.get("csv_variants", [rule])
    selected = None
    for variant in variants:
        expected = variant.get("columns", [])
        mapping = {}
        for column in expected:
            choices = [column, *variant.get("aliases", {}).get(column, [])]
            matches = [i for i, name in enumerate(names) if name in {normalize(c) for c in choices}]
            if len(matches) == 1:
                mapping[column] = matches[0]
        if len(mapping) == len(expected) and (rule.get("extra_columns", True) or len(names) == len(expected)):
            selected = variant, mapping
            break
    if selected is None:
        layouts = " or ".join(", ".join(v.get("columns", [])) for v in variants)
        report.errors.append("CSV columns do not match a documented layout (including case, aliases and extra-column rules). "
                             f"Expected required columns: {layouts}.")
        return
    variant, mapping = selected
    semantics = dict(variant.get("semantic_values", rule.get("semantic_values", {})))
    for selector, choices in rule.get("semantic_values_by_field", {}).items():
        if selector not in payload:
            report.warnings.append(f"CSV semantic checks depend on {selector}; supply it before upload.")
            continue
        selections = payload[selector] if isinstance(payload[selector], list) else [payload[selector]]
        for selection in selections:
            semantics.update(choices.get(str(selection), {}))
    for column in semantics.keys() - mapping.keys():
        choices = [column, *variant.get("aliases", rule.get("aliases", {})).get(column, [])]
        matches = [i for i, name in enumerate(names) if name in {normalize(c) for c in choices}]
        if len(matches) != 1:
            report.errors.append(f"CSV requires one unambiguous {column} column for the selected semantic checks.")
            return
        mapping[column] = matches[0]
    values = dict(variant.get("values", rule.get("values", {})))
    for selector, choices in rule.get("values_by_field", {}).items():
        if selector not in payload:
            report.warnings.append(f"CSV value rules depend on {selector}; supply it before upload.")
        else:
            values.update(choices.get(str(payload[selector]), {}))
    checks = {"number": _finite, "binary": lambda s: s in {"0", "1"},
              "integer": lambda s: _finite(s) and float(s).is_integer()}
    for column, kind in values.items():
        if not isinstance(kind, dict) and kind not in checks and column not in semantics:
            report.warnings.append(f"{column}: {kind} semantics are not verified by the generic CSV parser.")
    count = 0
    for row in reader:
        count += 1
        if len(row) != len(headers):
            report.errors.append(f"CSV row {count + 1}: column count differs from header.")
            break
        for column, index in mapping.items():
            value = row[index]
            if not value.strip():
                report.errors.append(f"CSV row {count + 1}: required column {column} is empty.")
            kind = values.get(column)
            if isinstance(kind, dict):
                # Reuse canonical scalar-schema checks; never coerce or rewrite cells.
                validate_schema(value, kind, report, f"CSV row {count + 1}: {column}")
            else:
                check = checks.get(kind) if isinstance(kind, str) else None
                if check and not check(value):
                    report.errors.append(f"CSV row {count + 1}: {column} violates its documented value type.")
            if column in semantics and value.strip():
                _semantic_value(value, semantics[column], f"CSV row {count + 1}: {column}", report)
        if report.errors:
            break
    if not count:
        report.errors.append("CSV has no data rows.")
    if not variant.get("columns"):
        report.warnings.append("CSV syntax checked; tool-specific columns are not documented.")


def _xyz(data, report):
    lines = data.decode("utf-8-sig").splitlines()
    try:
        count = int(lines[0])
        atoms = [line.split() for line in lines[2:] if line.strip()]
        valid = count > 0 and len(atoms) == count and all(
            len(a) >= 4 and a[0].isalpha() and all(_finite(v) for v in a[1:4]) for a in atoms)
    except (IndexError, ValueError):
        valid = False
    if not valid:
        report.errors.append("XYZ must contain its declared atom count and finite x/y/z coordinates.")
    report.warnings.append("Geometry syntax only; chemical identity and electronic-state suitability are not verified.")


def _sdf(data, report):
    text = data.decode("utf-8-sig")
    records = [part for part in text.split("$$$$") if part.strip()]
    if not records or "$$$$" not in text:
        report.errors.append("SDF must contain a terminated molecular record.")
        return
    for record in records:
        lines = record.lstrip("\r\n").splitlines()
        # A complete toolkit is not required to check the record delimiters.
        if "M  END" not in record or not any("V2000" in line or "V3000" in line for line in lines):
            report.errors.append("SDF record is missing its molfile version/counts or M  END marker.")
    report.warnings.append("SDF record structure checked; atom/bond chemistry and electronic-state suitability are not verified.")


def _positions(parent, field, payload, report):
    if field not in payload:
        report.warnings.append(f"{field}: parent-residue position checks require request context and remain unchecked.")
        return
    tokens = payload[field].split() if isinstance(payload[field], str) else payload[field]
    if not isinstance(tokens, list) or not tokens:
        report.errors.append(f"{field}: expected nonempty AA1 residue-position tokens.")
        return
    seen = set()
    for token in tokens:
        match = re.fullmatch(r"([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)", str(token))
        if match is None:
            report.errors.append(f"{field}: expected canonical uppercase amino acid followed by a one-based position.")
            return
        position = int(match[2])
        if position > len(parent) or position in seen or parent[position - 1] != match[1]:
            report.errors.append(f"{field}: a position is duplicate, out of range or does not match the parent residue.")
            return
        seen.add(position)


def _fasta(data, rule, report, payload=None):
    """Syntax plus explicitly opted-in worker sequence and parent checks."""
    records = 0
    parts = []
    identifiers = set()
    semantics = rule.get("sequence_validation")
    constraints = semantics or {}

    def finish():
        if not parts:
            report.errors.append("FASTA requires named records with nonempty sequences.")
            return
        if semantics:
            parent = _sequence("".join(parts), semantics, f"FASTA record {records}", report)
            if parent is not None and constraints.get("positions_field"):
                _positions(parent, constraints["positions_field"], payload or {}, report)

    for line in data.decode("utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if not line[1:].strip():
                report.errors.append("FASTA requires named records with nonempty sequences.")
                return
            if records:
                finish()
                if report.errors:
                    return
            if constraints.get("unique_ids") and line[1:] in identifiers:
                report.errors.append("FASTA contains duplicate record identifiers.")
                return
            if constraints.get("unique_ids"):
                identifiers.add(line[1:])
            records += 1
            if records > constraints.get("max_records", math.inf):
                report.errors.append(f"FASTA exceeds the documented maximum of {constraints['max_records']} records.")
                return
            parts = []
        elif not records or not semantics and not all(c.isascii() and (c.isalpha() or c in "*.-") for c in line):
            report.errors.append("FASTA has sequence data before a header or invalid sequence-line characters.")
            return
        else:
            parts.append(line)
    if not records:
        report.errors.append("FASTA requires at least one named, nonempty sequence record.")
    else:
        finish()
    if not semantics:
        report.warnings.append("FASTA record syntax checked; biological sequence suitability is not established by this check.")
    elif not report.errors:
        report.info.append("Documented FASTA sequence constraints checked; this is not a prediction of biological function.")


def _pdb(data, report):
    count = 0
    for line in data.decode("utf-8-sig").splitlines():
        if line[:6].strip() not in {"ATOM", "HETATM"}:
            continue
        count += 1
        if len(line) < 54 or not all(_finite(line[a:b]) for a, b in [(30, 38), (38, 46), (46, 54)]):
            report.errors.append("PDB atom records require finite fixed-column x/y/z coordinates.")
            return
    if not count:
        report.errors.append("PDB has no ATOM or HETATM coordinate records.")
    report.warnings.append("PDB coordinate syntax checked; chain selection and scientific suitability require input review.")


def _zip(data, rule, report, *, warn_contents=True):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS or sum(m.file_size for m in members) > MAX_EXPANDED_BYTES:
            report.errors.append("ZIP exceeds the connector's archive inspection security budget.")
            return
        seen = set()
        allowed = {f.lower().lstrip(".") for f in rule.get("member_formats", [])}
        for member in members:
            name = member.filename.replace("\\", "/")
            path = PurePosixPath(name)
            mode = member.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or ":" in name or name in seen or
                    stat.S_ISLNK(mode) or member.flag_bits & 1 or
                    (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)))):
                report.errors.append("ZIP contains an unsafe, duplicate, linked or encrypted member.")
                return
            seen.add(name)
            if member.is_dir():
                continue
            if path.suffix.lower() in {".pt", ".pkl", ".pickle"}:
                report.errors.append("ZIP contains serialized model inputs without an approved safe validator.")
                return
            if allowed and path.suffix.lower().lstrip(".") not in allowed:
                report.errors.append("ZIP contains a member with an unsupported file format.")
            # Read in bounded chunks to check integrity without extraction or execution.
            with archive.open(member) as handle:
                size = 0
                while chunk := handle.read(1024 * 1024):
                    size += len(chunk)
                    if size > member.file_size or size > MAX_EXPANDED_BYTES:
                        report.errors.append("ZIP expanded content exceeds declared bounds.")
                        return
        if not any(not m.is_dir() and m.file_size for m in members):
            report.errors.append("ZIP has no nonempty input files.")
        if warn_contents:
            report.warnings.append("ZIP safety/integrity checked; member scientific contents and tool-specific layout need review.")


def validate_file(path, rule, payload):
    report = ValidationReport()
    path = Path(path)
    if rule.get("execution_blocked"):
        report.errors.append("This file input is explicitly blocked pending an approved validator.")
        return report
    if path.is_symlink() or not path.is_file():
        report.errors.append("Input must be an existing regular file, not a symlink.")
        return report
    size = path.stat().st_size
    if not 0 < size <= MAX_FILE_BYTES:
        report.errors.append("Input is empty or exceeds the connector's 256 MiB inspection budget (not a service limit).")
        return report
    if size > rule.get("max_bytes", MAX_FILE_BYTES):
        report.errors.append("Input exceeds this field's documented maximum byte size.")
        return report
    extension = path.suffix.lower().lstrip(".")
    if extension == "gz":
        extension = "".join(path.suffixes[-2:]).lower().lstrip(".")
    formats = {f.lower().lstrip(".") for f in rule.get("formats", [])}
    if formats and extension not in formats:
        report.errors.append("File extension is not supported by this input field.")
    if extension in {"pt", "pkl", "pickle"}:
        report.errors.append("Serialized executable/model inputs require an approved safe validator; they are not unpickled here.")
    if report.errors:
        return report
    data = path.read_bytes()
    if extension.endswith(".gz"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                data = compressed.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                report.errors.append("Gzip expansion exceeds the connector's inspection budget.")
                return report
        except (OSError, EOFError, zlib.error):
            report.errors.append("Invalid gzip content.")
            return report
        extension = extension.removesuffix(".gz")
    parsers = {"csv": lambda: _csv(data, rule, payload, report),
               "json": lambda: _json(data, rule, report),
               "zip": lambda: _zip(data, rule, report),
               "xyz": lambda: _xyz(data, report), "sdf": lambda: _sdf(data, report),
               "pdb": lambda: _pdb(data, report),
               "fa": lambda: _fasta(data, rule, report, payload), "fasta": lambda: _fasta(data, rule, report, payload)}
    try:
        if rule.get("structure_profile"):
            if extension == "zip":
                _zip(data, rule, report, warn_contents=False)
            if not report.errors:
                from .boltzyme_tools_input_structure_validation import inspect_structure
                summary = inspect_structure(data, extension, rule["structure_profile"], payload, report,
                                            filename=path.name, requirements=rule)
                if not report.errors:
                    _retain_inventory(report, "structure", summary)
        elif extension in parsers:
            parsers[extension]()
        else:
            report.warnings.append(f"No content parser for .{extension}; only file existence, size and declared extension checked.")
    except (UnicodeError, ValueError, csv.Error, zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, RecursionError):
        report.errors.append("Input could not be decoded or its archive integrity check failed.")
    unsupported = {"alphabet", "chains_field", "chain_scalar", "required_chains", "residues_field", "content_format"} & rule.keys()
    if rule.get("structure_profile") or rule.get("json_schema"):
        unsupported.discard("content_format")
    if rule.get("structure_profile") == "protein_structure":
        unsupported -= {"chains_field", "chain_scalar", "residues_field"}
    if unsupported:
        report.warnings.append("Additional documented checks need review: " + ", ".join(sorted(unsupported)) + ".")
    if rule.get("coverage") in {"partial", "unknown"}:
        report.warnings.append("Tool-specific file validation is incomplete; server-side rejection remains possible and may incur charges.")
    return report
