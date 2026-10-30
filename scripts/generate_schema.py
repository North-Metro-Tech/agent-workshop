#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deterministic Pydantic -> JSON Schema -> TypeScript (closed supported subset).

No external generator dependency. Unknown schema constructs fail, never become any.
--check proves committed outputs exactly match the backend models.
"""
import argparse
import json
from pathlib import Path
import sys
from pydantic.json_schema import models_json_schema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from workshop.web_contracts import (Acknowledgement, Fact, History, HistoryEntry,
                                    Item, Login, Session, Snapshot)


def ts(schema):
    if '$ref' in schema:
        return schema['$ref'].rsplit('/', 1)[1]
    if 'const' in schema:
        return json.dumps(schema['const'])
    if 'enum' in schema:
        return ' | '.join(json.dumps(v) for v in schema['enum'])
    if 'anyOf' in schema:
        return ' | '.join(ts(s) for s in schema['anyOf'])
    kind = schema.get('type')
    if kind in ('string', 'number', 'integer', 'boolean', 'null'):
        return {'string':'string', 'number':'number', 'integer':'number',
                'boolean':'boolean', 'null':'null'}[kind]
    if kind == 'array':
        return 'Array<'+ts(schema['items'])+'>'
    if kind == 'object' and schema.get('additionalProperties') is False:
        required = schema.get('required', [])
        return '{\n'+'\n'.join('  '+json.dumps(k)+('' if k in required else '?')+': '+ts(v)+';'
                                for k,v in schema['properties'].items())+'\n}'
    raise ValueError('Unsupported schema: '+repr(schema))


def outputs():
    models = (Acknowledgement, Fact, History, HistoryEntry, Item, Login, Session, Snapshot)
    _, document = models_json_schema([(m, 'validation') for m in models])
    definitions = document['$defs']
    types = '// GENERATED from backend Pydantic models. Do not edit.\n// Regenerate: .venv/bin/python scripts/generate_schema.py\n'
    types += '\n'.join('export type '+name+' = '+ts(schema)+';\n'
                       for name, schema in sorted(definitions.items()))
    return {'frontend/src/workshop/generated.ts': types,
            'docs/web-schema.json': json.dumps(document, indent=2, sort_keys=True)+'\n'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for path, content in outputs().items():
        target = ROOT / path
        if args.check:
            if not target.exists() or target.read_text() != content:
                print('Stale generated contract: '+path, file=sys.stderr)
                return 1
        else:
            target.write_text(content)
        print(('Verified ' if args.check else 'Generated ')+path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
