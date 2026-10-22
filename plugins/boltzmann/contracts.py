"""Read-only, per-plugin contract loading and deterministic request checks."""

from dataclasses import dataclass, field
import json
import math
import operator
import re
from pathlib import Path


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self):
        return {"level": "invalid" if self.errors else "partial" if self.warnings else "checked",
                "errors": list(dict.fromkeys(self.errors)),
                "warnings": list(dict.fromkeys(self.warnings))}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


_TYPES = {"string": lambda v: isinstance(v, str), "object": lambda v: isinstance(v, dict),
          "array": lambda v: isinstance(v, list), "integer": lambda v: type(v) is int,
          "number": _number, "boolean": lambda v: type(v) is bool,
          "null": lambda v: v is None}
_BOUNDS = {"minimum": operator.ge, "maximum": operator.le,
           "exclusiveMinimum": operator.gt, "exclusiveMaximum": operator.lt}


def validate_schema(value, schema, report, path="payload"):
    for keyword in ("allOf", "oneOf"):
        if keyword in schema:
            branches = []
            for alternative in schema[keyword]:
                candidate = ValidationReport()
                validate_schema(value, alternative, candidate, path)
                branches.append(candidate)
            if keyword == "allOf":
                for candidate in branches:
                    report.errors.extend(candidate.errors)
                    report.warnings.extend(candidate.warnings)
            elif sum(not candidate.errors for candidate in branches) != 1:
                report.errors.append(f"{path}: must match exactly one documented input mode.")
    if "if" in schema:
        condition = ValidationReport()
        validate_schema(value, schema["if"], condition, path)
        validate_schema(value, schema.get("then" if not condition.errors else "else", {}), report, path)
    if "not" in schema:
        forbidden = ValidationReport()
        validate_schema(value, schema["not"], forbidden, path)
        if not forbidden.errors:
            report.errors.append(f"{path}: contains a combination forbidden in this input mode.")
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        report.errors.append(f"{path}: does not match the documented constant.")
    if "anyOf" in schema:
        branches = []
        for alternative in schema["anyOf"]:
            candidate = ValidationReport()
            validate_schema(value, alternative, candidate, path)
            branches.append(candidate)
        if not any(not candidate.errors for candidate in branches):
            report.errors.append(f"{path}: none of the documented input modes has its required fields.")
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind] if kind else []
    if kinds and not any(_TYPES.get(k, lambda _: False)(value) for k in kinds):
        report.errors.append(f"{path}: expected {' or '.join(kinds)}.")
        return
    if "enum" in schema and value not in schema["enum"]:
        report.errors.append(f"{path}: value is outside the documented choices.")
    if isinstance(value, dict):
        for bound, compare in (("minProperties", operator.ge), ("maxProperties", operator.le)):
            if bound in schema and not compare(len(value), schema[bound]):
                report.errors.append(f"{path}: violates {bound} {schema[bound]}.")
        for name in value:
            if "propertyNames" in schema:
                validate_schema(name, schema["propertyNames"], report, f"{path} key")
        for condition in schema.get("x-required-if", []):
            if all(name in value and value[name] == expected for name, expected in condition["when"].items()):
                for name in condition["required"]:
                    if name not in value or value[name] is None or value[name] == "":
                        report.errors.append(f"{path}.{name}: required by the selected input mode.")
        for left, right in schema.get("x-equal-fields", []):
            if left in value and right in value and value[left] != value[right]:
                report.errors.append(f"{path}.{left} and {right} must contain the same documented input value.")
        for name in schema.get("required", []):
            prop = schema.get("properties", {}).get(name, {})
            if name not in value or value[name] is None or (value[name] == "" and not prop.get("x-allow-empty")):
                report.errors.append(f"{path}.{name}: required value missing.")
        props = schema.get("properties", {})
        for name, item in value.items():
            if name in props:
                validate_schema(item, props[name], report, f"{path}.{name}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(item, schema["additionalProperties"], report, f"{path}.{name}")
            elif schema.get("additionalProperties") is False:
                report.errors.append(f"{path}.{name}: undocumented field.")
            elif "properties" in schema:
                report.warnings.append(f"{path}.{name}: no documented field rule; review before submission.")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            report.errors.append(f"{path}: too few items.")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            report.errors.append(f"{path}: too many items.")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            report.errors.append(f"{path}: duplicate items are not allowed.")
        if value and "items" not in schema and schema.get("type") == "array":
            report.warnings.append(f"{path}: item structure is not documented; confirm supplied values before submission.")
        for index, item in enumerate(value):
            if "items" in schema:
                validate_schema(item, schema["items"], report, f"{path}[{index}]")
    if _number(value):
        for bound, check in _BOUNDS.items():
            if bound in schema and not check(value, schema[bound]):
                report.errors.append(f"{path}: violates documented {bound} {schema[bound]}.")
    if isinstance(value, str):
        for bound, compare in (("minLength", operator.ge), ("maxLength", operator.le)):
            if bound in schema and not compare(len(value), schema[bound]):
                report.errors.append(f"{path}: violates {bound} {schema[bound]}.")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            report.errors.append(f"{path}: does not match the documented format.")
    if isinstance(value, str) and schema.get("x-numeric-string"):
        if value == "" and schema.get("x-allow-empty"):
            return
        try:
            valid = math.isfinite(float(value))
        except ValueError:
            valid = False
        if not valid:
            report.errors.append(f"{path}: expected a finite numeric string.")


class ContractStore:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path(__file__).parent / "skills/boltzmann-tools/references"
        self.catalog = self._load("tool-contracts.v1.json")
        self.tools = self.catalog["tools"]
        self.files = self._load("file-input-contracts.v1.json")["tools"]
        self.limits = self._load("input-limits.v1.json")["tools"]

    def _load(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8-sig"))

    def tool(self, name):
        tool = self.tools.get(name)
        if not tool:
            raise ValueError("Unknown Boltzmann job name. Select an exact catalog entry; do not infer a payload.")
        if tool.get("status") != "active" or tool.get("execution_blocked"):
            raise ValueError("This Boltzmann tool is explicitly unavailable; partial validation cannot enable it.")
        return tool

    def file_rule(self, job, name):
        tool = self.tool(job)
        prop = tool["request_schema"]["properties"].get(name, {})
        if prop.get("x-input-kind") not in {"file", "file_or_value"}:
            raise ValueError(f"{job}.{name} is not declared as a local-file input in its request schema.")
        return self.files.get(job, {}).get("files", {}).get(name, {})

    def diagnostic_collection(self, job):
        """Resolve documented exact-job mappings, never guess from a job spelling."""
        if job not in self.tools:
            raise ValueError(f"Unknown Boltzmann job name: {job}.")
        collections = {
            record["collection_name"]
            for record in self.tools[job].get("diagnostics", [])
            if record.get("job_name") == job and record.get("collection_name")
            and record.get("mapping_status") in {"matched", "source_documented"}
        }
        if not collections:
            raise ValueError(f"No documented diagnostic collection mapping for {job}. "
                             "Use boltzmann_status with the original job_name and doc_id; do not guess a collection.")
        if len(collections) != 1:
            raise ValueError(f"Ambiguous diagnostic collection mapping for {job}; lookup stopped. "
                             "The submitted job's outcome is unchanged.")
        return next(iter(collections))

    def file_fields(self, job):
        return {name: prop for name, prop in self.tool(job)["request_schema"]["properties"].items()
                if prop.get("x-input-kind") in {"file", "file_or_value", "artifact"}}

    def validate_payload(self, job, payload):
        report = ValidationReport()
        try:
            tool = self.tool(job)
        except ValueError as exc:
            report.errors.append(str(exc))
            return report
        validate_schema(payload, tool["request_schema"], report)
        if not isinstance(payload, dict):
            return report
        report.warnings.extend(tool.get("review_notes", []))
        limits = self.limits.get(job, {})
        for name, rule in limits.get("fields", {}).items():
            if name not in payload:
                continue
            value = payload[name]
            if tool["request_schema"]["properties"].get(name, {}).get("x-numeric-string"):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    report.errors.append(f"payload.{name}: expected a numeric string.")
                    continue
            schema = {}
            for source, target in {"minimum": "minimum", "maximum": "maximum",
                                   "exclusive_minimum": "exclusiveMinimum", "exclusive_maximum": "exclusiveMaximum",
                                   "min_items": "minItems"}.items():
                if source in rule:
                    schema[target] = rule[source]
            validate_schema(value, schema, report, f"payload.{name}")
        for relation in limits.get("relations", []):
            left, right = payload.get(relation["left"]), payload.get(relation["right"])
            if _number(left) and _number(right) and relation["operator"] == "<=" and left > right:
                report.errors.append(f"{relation['left']} must not exceed {relation['right']}.")
        for group in limits.get("any_of_nonempty", []):
            if not any(payload.get(key) for key in group):
                report.errors.append(f"At least one of {', '.join(group)} must be nonempty.")
        for group in limits.get("combined_items", []):
            if sum(len(payload.get(key, [])) for key in group["fields"] if isinstance(payload.get(key), list)) > group["maximum"]:
                report.errors.append("Combined item count exceeds the documented maximum.")
        if not report.errors and tool.get("request_checks"):
            from .enzyme_validation import validate_request
            validate_request(tool["request_checks"], payload, report)
        return report
