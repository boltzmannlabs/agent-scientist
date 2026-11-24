"""Verify exact, bounded text artifacts assigned to a workflow review."""
import hashlib
import json
from pathlib import Path
import re

HEX = re.compile("[0-9a-f]{64}")
EVIDENCE_FORMATS = {".csv", ".json", ".jsonl", ".md", ".pdb", ".sdf", ".tsv", ".txt"}
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def non_finite(value):
        raise ValueError(f"Non-finite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=non_finite)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def texts(values):
    return all(isinstance(value, str) and value.strip() for value in values)


def validate_packet(packet, root):
    if not isinstance(packet, dict) or set(packet) != {"case_id", "baseline_sha256", "evidence"}:
        raise ValueError("Malformed packet manifest.")
    if not texts((packet["case_id"], packet["baseline_sha256"])) or not HEX.fullmatch(packet["baseline_sha256"]):
        raise ValueError("Packet must identify a case and its frozen comparator digest.")
    root = root.resolve(strict=True)
    evidence = packet["evidence"]
    if not isinstance(evidence, dict) or not evidence or not texts(evidence):
        raise ValueError("A packet needs named evidence records.")
    paths = {}
    for key, value in evidence.items():
        if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
            raise ValueError(f"Malformed evidence record: {key}")
        if not texts(value.values()) or not HEX.fullmatch(value["sha256"]):
            raise ValueError(f"Invalid evidence path or checksum: {key}")
        relative = Path(value["path"])
        if relative.is_absolute() or any(part == ".." for part in relative.parts):
            raise ValueError(f"Evidence path must be package-relative: {key}")
        path = root / relative
        if path.resolve(strict=True) != path or not path.is_file():
            raise ValueError(f"Evidence must be a regular file with no symbolic aliases: {key}")
        if path.suffix.lower() not in EVIDENCE_FORMATS or path.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError(f"Use bounded, reviewed text evidence for {key}.")
        contents = path.read_bytes()
        try:
            contents.decode("utf-8")
        except UnicodeError as error:
            raise ValueError(f"Evidence must be UTF-8 text: {key}") from error
        if b"\x00" in contents or hashlib.sha256(contents).hexdigest() != value["sha256"]:
            raise ValueError(f"Frozen evidence is binary or changed: {key}")
        if path in paths.values():
            raise ValueError("Each evidence ID must point to a different file.")
        paths[key] = path
    return paths
