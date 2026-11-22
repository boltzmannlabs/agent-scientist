"""Preflight delegated JSON schemas for common impossible closed-object contracts."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from jsonschema.validators import validator_for


def check_schema(schema):
    validator_for(schema).check_schema(schema)

    def visit(node, location):
        if not isinstance(node, dict):
            return
        if node.get('additionalProperties') is False:
            declared = set(node.get('properties', {}))
            patterns = node.get('patternProperties', {})
            impossible = [name for name in node.get('required', [])
                          if name not in declared and not any(re.search(p, name) for p in patterns)]
            if impossible:
                raise ValueError(location + ': required fields forbidden by additionalProperties=false: '
                                 + ', '.join(impossible))
        for keyword in ('properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas'):
            for name, child in node.get(keyword, {}).items():
                visit(child, location + '/' + keyword + '/' + name)
        for keyword in ('items', 'contains', 'additionalProperties', 'propertyNames', 'if', 'then', 'else', 'not'):
            child = node.get(keyword)
            if isinstance(child, list):
                for i, part in enumerate(child):
                    visit(part, location + '/' + keyword + '/' + str(i))
            else:
                visit(child, location + '/' + keyword)
        for keyword in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
            for i, child in enumerate(node.get(keyword, [])):
                visit(child, location + '/' + keyword + '/' + str(i))

    visit(schema, '$')


def reference_schema(path):
    path = Path(path).resolve(strict=True)
    schema = json.loads(path.read_text())
    check_schema(schema)
    return {'$schema': schema.get('$schema', 'json-schema.org/draft/2020-12/schema'),
            '$ref': path.as_uri()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schema', type=Path)
    parser.add_argument('--emit-reference', action='store_true',
                        help='Emit a compact local reference to the exact prevalidated schema; freeze that file in the native handoff.')
    args = parser.parse_args()
    raw = args.schema.read_bytes()
    check_schema(json.loads(raw))
    result = {'schema_preflight': 'passed', 'sha256': hashlib.sha256(raw).hexdigest(),
              'scope': 'Metaschema and explicit closed-object required-field contradictions; not full satisfiability proof.'}
    if args.emit_reference:
        result['output_schema'] = reference_schema(args.schema)
    print(json.dumps(result))
