"""Bounded, non-executing file inspection. Unknown scientific checks stay explicit."""

import csv
import gzip
import io
import json
import math
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .contracts import ValidationReport, validate_schema

MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000


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


def _finite(text):
    try:
        return math.isfinite(float(text))
    except (ValueError, TypeError):
        return False


def _csv(data, rule, payload, report):
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), strict=True)
    headers = next(reader, [])
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
    values = dict(variant.get("values", rule.get("values", {})))
    for selector, choices in rule.get("values_by_field", {}).items():
        if selector not in payload:
            report.warnings.append(f"CSV value rules depend on {selector}; supply it before upload.")
        else:
            values.update(choices.get(str(payload[selector]), {}))
    checks = {"number": _finite, "binary": lambda s: s in {"0", "1"},
              "integer": lambda s: _finite(s) and float(s).is_integer()}
    for column, kind in values.items():
        if kind not in checks:
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
            check = checks.get(values.get(column))
            if check and not check(value):
                report.errors.append(f"CSV row {count + 1}: {column} violates its documented value type.")
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


def _fasta(data, rule, report):
    """Check record structure without interpreting or designing sequences."""
    records = 0
    residues = 0
    for line in data.decode("utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if not line[1:].strip() or (records and not residues):
                report.errors.append("FASTA requires named records with nonempty sequences.")
                return
            records += 1
            residues = 0
        elif not records or not all(c.isascii() and (c.isalpha() or c in "*.-") for c in line):
            report.errors.append("FASTA has sequence data before a header or invalid sequence-line characters.")
            return
        else:
            residues += len(line)
    if not records or not residues:
        report.errors.append("FASTA requires at least one named, nonempty sequence record.")
    report.warnings.append("FASTA record syntax checked; biological sequence suitability is not established by this check.")


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


def _zip(data, rule, report):
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
        except (OSError, EOFError):
            report.errors.append("Invalid gzip content.")
            return report
        extension = extension.removesuffix(".gz")
    parsers = {"csv": lambda: _csv(data, rule, payload, report),
               "json": lambda: _json(data, rule, report),
               "zip": lambda: _zip(data, rule, report),
               "xyz": lambda: _xyz(data, report), "sdf": lambda: _sdf(data, report),
               "pdb": lambda: _pdb(data, report),
               "fa": lambda: _fasta(data, rule, report), "fasta": lambda: _fasta(data, rule, report)}
    try:
        if extension in parsers:
            parsers[extension]()
        else:
            report.warnings.append(f"No content parser for .{extension}; only file existence, size and declared extension checked.")
    except (UnicodeError, ValueError, csv.Error, zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, RecursionError):
        report.errors.append("Input could not be decoded or its archive integrity check failed.")
    unsupported = {"alphabet", "chains_field", "chain_scalar", "required_chains", "residues_field", "content_format"} & rule.keys()
    if unsupported:
        report.warnings.append("Additional documented checks need review: " + ", ".join(sorted(unsupported)) + ".")
    if rule.get("coverage") in {"partial", "unknown"}:
        report.warnings.append("Tool-specific file validation is incomplete; server-side rejection remains possible and may incur charges.")
    return report
