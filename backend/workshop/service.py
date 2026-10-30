# SPDX-License-Identifier: Apache-2.0
"""Single-process loopback HTTP/SSE binding; all historian calls on its owning loop.

No executor, native control route, background writer thread, or public bind.
Use scripts/dev.py serve; direct multi-worker/reload Uvicorn is unsupported.
"""
import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
import fcntl
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .api import LocalAPI
from .storage import RecoveryRequired, State, Storage
from .web_contracts import Acknowledgement, Login, Session
from .web_projection import history_excerpt, project

COOKIE = 'workshop_session'
MAX_RESPONSE = 4 * 1024 * 1024
CURSOR = re.compile(r'^[a-f0-9]{32}:(0|[1-9][0-9]{0,18})$')


@dataclass(frozen=True)
class Settings:
    historian: Path
    operator_token: str
    origin: str = 'http://127.0.0.1:8765'
    source_mode: str = 'synthetic'
    viewer_token: str | None = None
    session_seconds: float = 3600
    poll_seconds: float = 1
    frontend: Path | None = None
    extra_origin: str | None = None

    def __post_init__(self):
        url = urlsplit(self.origin)
        if (url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost'}
                or url.path or url.query or url.fragment or url.username or not url.port):
            raise ValueError('Only an explicit loopback HTTP origin is supported')
        if self.extra_origin is not None:
            extra = urlsplit(self.extra_origin)
            hostname = extra.hostname or ''
            labels = hostname.split('.')
            # Configuration guard only; requests NEVER use suffix matching.
            # Require a plain ASCII DNS authority, not userinfo, URL decorations
            # or parser-normalized whitespace/control characters.
            if (extra.scheme != 'https' or not hostname.endswith('.ts.net')
                    or extra.username is not None or extra.password is not None
                    or extra.path or extra.query or extra.fragment
                    or extra.geturl() != self.extra_origin
                    or any(ord(c) <= 32 or ord(c) >= 127 for c in self.extra_origin)
                    or len(hostname) > 253
                    or any(not label or len(label) > 63
                           or label[0] == '-' or label[-1] == '-'
                           or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label)
                           for label in labels)
                    or extra.netloc != hostname + (f':{extra.port}' if extra.port is not None else '')
                    or extra.port == 0):
                raise ValueError('Extra origin must be an exact HTTPS origin under .ts.net')
        if self.source_mode not in {'synthetic', 'approved-local'}:
            raise ValueError('Explicit source mode required')
        if not 32 <= len(self.operator_token) <= 256 or (self.viewer_token is not None and
                (not 32 <= len(self.viewer_token) <= 256 or self.viewer_token == self.operator_token)):
            raise ValueError('Distinct provisioned secrets of 32 to 256 characters required')
        if not 0 < self.session_seconds <= 86400 or not 0.01 <= self.poll_seconds <= 60:
            raise ValueError('Invalid service bounds')


class Boundary:
    """Check exact authority/origin, never trust X-Forwarded-* or arbitrary CORS."""
    def __init__(self, app, *, origin, extra_origin=None):
        self.app = app
        approved = (origin,) if extra_origin is None else (origin, extra_origin)
        self.origins = frozenset(value.encode('ascii') for value in approved)
        self.hosts = frozenset(urlsplit(value).netloc.encode('ascii') for value in approved)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        headers = scope['headers']
        values = lambda name: [v for k,v in headers if k.lower() == name]
        hosts, origins = values(b'host'), values(b'origin')
        mutation = scope['method'] not in {'GET', 'HEAD'}
        bad = (len(hosts) != 1 or hosts[0] not in self.hosts or len(origins) > 1 or
               (origins and origins[0] not in self.origins) or
               (mutation and not origins) or
               values(b'sec-fetch-site') == [b'cross-site'] or
               len(values(b'cookie')) > 1)
        if scope['path'].startswith('/api/'):
            bad = bad or bool(scope.get('query_string'))
        if bad:
            await JSONResponse({'detail':'Host/origin boundary rejected'}, status_code=403)(scope, receive, send)
            return
        size = 0
        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > 4096:
                raise HTTPException(413, 'Request too large')
            return message
        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message['headers']) + [
                    (b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff'),
                    (b'referrer-policy', b'no-referrer'), (b'x-frame-options', b'DENY'),
                    (b'content-security-policy', b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]
            await send(message)
        await self.app(scope, bounded_receive, secure_send)


def initial_synthetic(now):
    """Explicit labelled demo, not discovered/native activity. No automatic changes."""
    from .contracts import AlarmRule, ExecutionKey, FeedPolicy, Observation, TaskKey
    from .reducer import Reducer
    r = Reducer()
    r.register_role('synthetic-coder', scope=('synthetic-board',), inventory_approved=False)
    r.register_feed('synthetic-feed', FeedPolicy(5, 15, 30), group='synthetic-observer')
    for n in (1, 2):
        r.observe_execution('synthetic-coder', ExecutionKey('synthetic-runtime', 'attempt-'+str(n)),
            session='synthetic-session', parent=None,
            task=TaskKey('synthetic-instance', 'synthetic-board', 'task-'+str(n)),
            lifecycle=Observation('working', 'active', 'synthetic-v1',
                'urn:synthetic:service', 'synthetic-feed', now, evidence_class='source_record'),
            acquired_at=now)
    r.alarms.register(AlarmRule('Synthetic observation uncertainty', 'synthetic-observer',
        'Demonstration condition', 'No fleet coverage established', 'Inspect retained evidence',
        'Before interpretation', 'synthetic only', 'diagnostic', 'local-demo'))
    r.alarms.update('Synthetic observation uncertainty', True, now=now, reliable_order=False)
    return State(r)


def encoded(model):
    payload = model.model_dump_json()
    if len(payload.encode()) > MAX_RESPONSE:
        raise HTTPException(503, 'Projection exceeds bounded display limit')
    return payload


def create_app(settings, *, clock=time.monotonic):
    sessions = {}
    login_attempts = []

    @asynccontextmanager
    async def lifespan(app):
        directory = settings.historian.parent
        if directory.is_symlink() or settings.historian.is_symlink():
            raise ValueError('Historian paths must not be symlinks')
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = settings.historian.with_suffix('.writer-lock')
        if lock_path.is_symlink():
            raise ValueError('Writer lock must not be a symlink')
        with lock_path.open('a') as writer_lock:
            # Held throughout lifetime. A second service fails before Storage
            # can invalidate another live service's state on open.
            fcntl.flock(writer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            binding_path = settings.historian.with_suffix('.service-binding.json')
            binding = {'source_mode': settings.source_mode,
                       'clock': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
            if binding_path.is_symlink():
                raise ValueError('Service binding must not be a symlink')
            if binding_path.exists():
                if json.loads(binding_path.read_text()) != binding:
                    raise ValueError('Source mode or acquisition clock changed; explicit recovery required')
            else:
                if settings.historian.exists():
                    raise ValueError('Unbound historian; use a new service state directory')
                with binding_path.open('x') as file:
                    file.write(json.dumps(binding))
            collector = None
            if settings.source_mode == 'approved-local':
                from .web_source import ApprovedSource
                collector = ApprovedSource(directory)
                initial = collector.initial
            else:
                initial = initial_synthetic(clock())
            store = Storage(settings.historian, initial=None if settings.historian.exists() else initial)
            app.state.storage = store
            app.state.source_error = False
            async def acquire():
                while True:
                    if collector is not None:
                        try:
                            collector.acquire(store, now=clock())
                            app.state.source_error = False
                        except Exception:
                            # Last-known domain acquisition ages still decay;
                            # do not leak source paths/rows into transport errors.
                            app.state.source_error = True
                    await asyncio.sleep(settings.poll_seconds)
            task = asyncio.create_task(acquire())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                store.close()
                if collector is not None:
                    collector.close()
                sessions.clear()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(Boundary, origin=settings.origin, extra_origin=settings.extra_origin)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exception):
        # Pydantic's default errors include rejected input: never echo secrets.
        return JSONResponse({'detail':'Invalid request contract'}, status_code=422)

    def authenticate(request):
        value = request.cookies.get(COOKIE, '')
        entry = sessions.get(hashlib.sha256(value.encode()).hexdigest())
        if entry is None or clock() >= entry['expires']:
            raise HTTPException(401, 'Local session required')
        return entry

    def snapshot():
        now = clock()
        result = project(app.state.storage.snapshot(now=now), now=now, source_mode=settings.source_mode)
        if app.state.source_error:
            result = result.model_copy(update={'connection_quality':'source acquisition failed; last-known facts'})
        return result

    @app.get('/api/session', response_model=Session)
    async def session(request: Request):
        entry = authenticate(request)
        return Session(csrf=entry['csrf'], permissions=entry['permissions'], controller_connected=False)

    @app.post('/api/session')
    async def login(request: Request, body: Login):
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise HTTPException(415, 'JSON required')
        now = clock()
        login_attempts[:] = [t for t in login_attempts if now-t < 60]
        if len(login_attempts) >= 20:
            raise HTTPException(429, 'Login rate limit')
        login_attempts.append(now)
        permissions = None
        if hmac.compare_digest(body.token.encode('utf-8'), settings.operator_token.encode('utf-8')):
            permissions = ['viewer', 'operator']
        elif settings.viewer_token and hmac.compare_digest(body.token.encode('utf-8'), settings.viewer_token.encode('utf-8')):
            permissions = ['viewer']
        if permissions is None:
            raise HTTPException(401, 'Local session required')
        for key in list(sessions):
            if sessions[key]['expires'] <= now:
                del sessions[key]
        if len(sessions) >= 128:
            raise HTTPException(503, 'Session capacity reached')
        # Rotate an existing session on login, don't leave an old operator token usable.
        previous = request.cookies.get(COOKIE, '')
        sessions.pop(hashlib.sha256(previous.encode()).hexdigest(), None)
        token = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(token.encode()).hexdigest()] = dict(
            csrf=secrets.token_urlsafe(32), permissions=permissions, expires=now+settings.session_seconds)
        response = JSONResponse({'authenticated':True})
        response.set_cookie(COOKIE, token, httponly=True, samesite='strict', secure=False,
                            max_age=int(settings.session_seconds), path='/')
        return response

    @app.get('/api/snapshot')
    async def get_snapshot(request: Request):
        authenticate(request)
        return JSONResponse(json.loads(encoded(snapshot())))

    @app.get('/api/history')
    async def get_history(request: Request):
        authenticate(request)
        return JSONResponse(json.loads(encoded(history_excerpt(app.state.storage.retained_diagnostics()))))

    @app.post('/api/alarms/acknowledge')
    async def acknowledge(request: Request, body: Acknowledgement):
        entry = authenticate(request)
        csrf = request.headers.get('x-csrf-token', '')
        if not hmac.compare_digest(csrf.encode('utf-8'), entry['csrf'].encode('utf-8')) or 'operator' not in entry['permissions']:
            raise HTTPException(403, 'Local operator and CSRF required')
        try:
            LocalAPI(storage=app.state.storage).acknowledge(body.occurrence_id, now=clock(), authorized=True)
        except KeyError:
            raise HTTPException(404, 'Unknown local alarm occurrence') from None
        return {'acknowledged':True, 'native_write_enabled':False}

    @app.get('/api/events')
    async def events(request: Request):
        authenticate(request)
        cursors = request.headers.getlist('last-event-id')
        cursor = cursors[0] if len(cursors) == 1 else None
        reset = len(cursors) > 1
        if cursor:
            if len(cursor) > 160 or not CURSOR.fullmatch(cursor):
                reset = True
            else:
                try:
                    # Validate identity/range/retention in the historian's own
                    # read transaction. SSE always sends a FULL current snapshot,
                    # never pretends historical replay is current state.
                    app.state.storage.replay(cursor, now=clock())
                except RecoveryRequired:
                    reset = True
        async def stream():
            if reset:
                yield 'event: reset\ndata: {"reason":"full snapshot required"}\n\n'
            while True:
                try:
                    authenticate(request)
                except HTTPException:
                    yield 'event: session-expired\ndata: {}\n\n'
                    return
                model = snapshot()
                yield 'event: snapshot\nid: '+model.cursor+'\ndata: '+encoded(model)+'\n\n'
                await asyncio.sleep(settings.poll_seconds)
        return StreamingResponse(stream(), media_type='text/event-stream',
                                 headers={'X-Accel-Buffering':'no'})

    if settings.frontend is not None:
        if not (settings.frontend / 'index.html').is_file():
            raise ValueError('Build frontend before starting service')
        app.mount('/', StaticFiles(directory=settings.frontend, html=True), name='hmi')
    return app
