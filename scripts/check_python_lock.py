#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed PyPI publication/hash/yank/advisory check of every locked resolution.

No installs or executable package metadata. Also query OSV for known advisories.
Run before Socket-wrapped installation, and after any resolution change.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lock', nargs='?', default='requirements.lock')
    parser.add_argument('--output', default='evidence/phase3-remediation/python-quarantine-audit.json')
    args = parser.parse_args()
    raw = (ROOT / args.lock).read_text()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    blocks = re.findall(r'^([a-zA-Z0-9_.-]+)==([^\s\\]+)(.*?)(?=^[a-zA-Z0-9_.-]+==|\Z)', raw, re.M | re.S)
    if not blocks:
        raise ValueError('No pinned resolutions')

    def check(block):
        name, version, content = block
        with urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=60) as response:
            data = json.load(response)
        files = data['urls']
        hashes = set(re.findall(r'--hash=sha256:([0-9a-f]{64})', content))
        registry = {f['digests']['sha256'] for f in files}
        published = max(datetime.fromisoformat(f['upload_time_iso_8601']) for f in files)
        query = json.dumps({'package': {'name': name, 'ecosystem': 'PyPI'}, 'version': version}).encode()
        with urlopen(Request('https://api.osv.dev/v1/query', data=query,
                             headers={'Content-Type': 'application/json'}), timeout=60) as response:
            osv = json.load(response)
        advisories = sorted({v['id'] for v in data.get('vulnerabilities', []) if not v.get('withdrawn')}
                            | {v['id'] for v in osv.get('vulns', []) if not v.get('withdrawn')})
        passed = bool(hashes) and hashes <= registry and published <= cutoff and not advisories and not any(f['yanked'] for f in files)
        return dict(name=name, version=version, published=published.isoformat(),
                    age_days=(now-published).total_seconds()/86400,
                    all_lock_hashes_match_registry=bool(hashes) and hashes <= registry,
                    requires_dist=data['info']['requires_dist'], advisories=advisories, passed=passed)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, blocks))
    report = dict(checked_at=now.isoformat(), required_age_days=7, lock=args.lock,
                  lock_sha256=hashlib.sha256(raw.encode()).hexdigest(), resolutions=len(results),
                  all_pass=all(p['passed'] for p in results), packages=results)
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'packages'}))
    for p in results:
        print(p['name'], p['version'], 'PASS' if p['passed'] else 'FAIL', p['advisories'])
    return 0 if report['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
