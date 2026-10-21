#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Source-checkout development commands; standard library only, no downloads.

install provisions a no-pip .venv and links this checkout's own backend code.
Tests use the invoking Python's already-approved pytest. This intentionally does
not install/update third-party packages or bypass the dependency quarantine.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('install', 'test', 'demo', 'check'))
    args, rest = parser.parse_known_args()
    if args.command != 'test' and rest:
        parser.error('extra arguments are supported only by test')
    if args.command == 'install':
        target = ROOT / '.venv'
        marker = target / 'workshop-source-install'
        if target.exists() and not marker.exists():
            parser.error('Refusing to alter an existing unmanaged .venv')
        builder = venv.EnvBuilder(with_pip=False)
        builder.create(target)
        # sysconfig's venv scheme is available on Python 3.11 as well; the
        # newer venv context.lib_path convenience attribute is not.
        purelib = sysconfig.get_path('purelib', scheme='venv',
                                    vars={'base': str(target), 'platbase': str(target)})
        Path(purelib, 'workshop-source.pth').write_text(str(ROOT / 'backend') + '\n')
        marker.write_text('Workshop source-only install; no third-party packages installed.\n')
        print('Workshop source linked in ' + str(target))
        return 0
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'backend')
    if args.command == 'test':
        command = [sys.executable, '-m', 'pytest', *(rest or ['-q'])]
    elif args.command == 'demo':
        command = [sys.executable, '-m', 'workshop.demo']
    else:
        command = [sys.executable, '-m', 'compileall', '-q', 'backend', 'scripts']
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
