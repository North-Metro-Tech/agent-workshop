#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check every npm lock resolution's publication age and registry integrity.

Uses only the Python standard library. Run BEFORE Socket-wrapped npm ci.
This is an age/integrity gate, not a package-security audit or Socket replacement.
Refreshes evidence/phase3-npm-quarantine.json; offline/unknown metadata fails closed.
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = json.loads((ROOT / 'frontend/package-lock.json').read_text())
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=7)
    packages = {}
    for path, meta in lock['packages'].items():
        if path:
            name = path.rsplit('node_modules/', 1)[1]
            packages[(name, meta['version'])] = meta

    def check(item):
        (name, version), meta = item
        with urllib.request.urlopen(
            'https://registry.npmjs.org/' + name.replace('/', '%2f'), timeout=60
        ) as response:
            registry = json.load(response)
        published = datetime.datetime.fromisoformat(registry['time'][version].replace('Z', '+00:00'))
        dist = registry['versions'][version]['dist']
        integrity = bool(dist.get('integrity')) and dist['integrity'] == meta.get('integrity')
        resolved = dist.get('tarball') == meta.get('resolved')
        return {
            'name': name, 'version': version, 'published': published.isoformat(),
            'age_days': (now - published).total_seconds() / 86400,
            'registry_integrity_matches': integrity,
            'registry_tarball_matches': resolved,
            'pass': published <= cutoff and integrity and resolved,
            'install_script': registry['versions'][version].get('scripts', {}).get('postinstall'),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = sorted(pool.map(check, packages.items()), key=lambda item: item['name'])
    report = {
        'checked_at': now.isoformat(), 'required_age_days': 7,
        'resolutions': len(results), 'all_pass': all(result['pass'] for result in results),
        'packages': results,
    }
    (ROOT / 'evidence/phase3-npm-quarantine.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'packages'}))
    return 0 if report['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
