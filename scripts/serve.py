#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Explicit single-writer loopback service entrypoint. Never autostarts a collector."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'collectors')]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--synthetic', action='store_true')
    mode.add_argument('--approved-local', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--state-dir', type=Path, default=ROOT/'.workshop-state/service')
    parser.add_argument('--init-secret', action='store_true', help='Create a private secret file and exit; does not serve')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('Use an unprivileged loopback port')
    source_mode = 'synthetic' if args.synthetic else 'approved-local'
    directory = args.state_dir.absolute() / source_mode
    if directory != directory.resolve():
        parser.error('State directory must be an exact nonsymlink local path')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    secret_path = directory/'login-secret'
    if args.init_secret:
        with open(secret_path, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
            file.write(secrets.token_urlsafe(32)+'\n')
        print('Created private login secret at '+str(secret_path))
        return 0
    token = os.environ.get('WORKSHOP_LOGIN_TOKEN')
    if token is None:
        if secret_path.is_symlink() or secret_path.stat().st_mode & 0o077:
            parser.error('Secret must be a private nonsymlink file (mode 600)')
        token = secret_path.read_text().strip()
    import uvicorn
    from workshop.service import Settings, create_app
    settings = Settings(historian=directory/'historian.db', operator_token=token,
                        origin=f'http://127.0.0.1:{args.port}', source_mode=source_mode,
                        frontend=ROOT/'frontend/dist')
    print('Workshop '+source_mode+' at '+settings.origin+'; no native controls; single writer', flush=True)
    uvicorn.run(create_app(settings), host='127.0.0.1', port=args.port,
                workers=1, proxy_headers=False, access_log=False, log_level='warning',
                loop='asyncio', http='h11', ws='none', timeout_graceful_shutdown=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
