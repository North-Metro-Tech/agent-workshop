# Agent Workshop Release 1 — installed observer (final MVP gate pending)

Installation task: t_2ec73616. Approved product:
d56e3ccf6f332fd4b578fa47cd2e2a7f24a726d4 (schema2).
This is installation/integration evidence, NOT the final owner-ready notification
or the beginning of the 30-day validation period. Those gates remain downstream.

Current checkout:
    /home/aaron/.local/share/agent-workshop/release1/checkout-schema2
Current private schema2 state:
    /home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local
Service:
    agent-workshop-release1.service (systemd --user)

The observer is manually started, with Restart=no and boot autostart disabled.
No timer, automatic restart, capacity-failure recovery job or reboot recovery
has been installed. It is independent of the Hermes native worker lifecycle.

Local operator access

On THIS Linux host, open exactly http://127.0.0.1:8765 and use the actual login
form. Read the private mode-600 file locally:
    /home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local/login-secret
Never paste that secret into URLs, task comments, shell arguments, browser
storage, bundles or published evidence. Sessions are in memory, expire after
one hour, and are revoked on service restart.

127.0.0.1 is this host only: it is NOT a phone or remote-desktop address.
Remote access has NOT been authorised or solved. Do not proxy, tunnel, change
the listening authority or expose this loopback development service. Aaron's
actual-use/accessibility judgement remains a final-gate responsibility.

Safe operations

    systemctl --user status agent-workshop-release1.service --no-pager
    systemctl --user show agent-workshop-release1.service -p Restart -p NRestarts
    journalctl --user -u agent-workshop-release1.service --no-pager
    systemctl --user stop agent-workshop-release1.service

A deliberate stop is the rollback: it affects ONLY the Workshop observer,
not native workers, boards, schedules or task execution. Preserve all state.
A manual restart on the same boot invalidates live freshness and sessions;
partial collection does not establish complete runtime availability. A new boot,
changed source identity or configuration may fail closed and needs explicit
owner-reviewed state/recovery. Never delete the binding sidecar, rebase clocks,
prune protected facts, auto-retry capacity failures, or create fresh state just
to conceal an acquisition error. Escalate a capacity/source failure to Core.

Scope and limitations

Only the existing approved agent-workshop board and coder/default profile/task
bindings are observed. Runtime coverage is partial and role availability unknown.
No atomic runtime watermark or full-fleet inventory is claimed. Product controls
remain fixed off; even controller mode cannot enable native writes. Local alarm
acknowledgements affect Workshop records only.

Systemd read-only restrictions were REQUESTED, but actual service mountinfo
resolves the native path under rw root. There is NO demonstrated kernel-enforced
read-only mount boundary. Adapter mode=ro/query_only and product fixed-off
controls remain intact; configuration alone is not a hardening proof.

Preserved failed installation

The original schema1 historian/outbox at state/approved-local remain read-only
diagnostic material. Do not restart, migrate, prune, replace or delete them.
The original checkout remains at 35e8c334. Its report/archive under evidence/
remain historical failed-attempt evidence, not current readiness evidence.
Current evidence is under evidence/schema2-install/ once packaging completes;
the signed evidence branch is ops/release1-fleet-install-schema2.

Sustained QA and this installed-resource window are finite evidence only, not a
30-day capacity, throughput, RSS-leak, automatic reboot, remote-access, manual
screen-reader or owner-use acceptance claim. Final MVP/RESUME notification is
not owned by this installation file.

## Owner-authorised tailnet access — addendum, 24 October 2026

This decision supersedes ONLY the earlier blanket remote-access prohibition for
one path. Aaron authorised tailnet-only operator use from his named owner
devices: aoruselite (desktop) and his Android phone, after enrolment in the owner
tailnet. Device enrolment and Aaron's actual-use/accessibility review remain
separate owner gates; this document does not attest either is complete. No other
device, account, public network or access path is authorised by this decision.
Tailscale ACL/device administration, not HTTP origin matching, enforces device
access; `.ts.net` validation alone is not proof of a caller's identity.

The sole additional approved origin is exactly:

    https://frankenfarm.taile4f46c.ts.net:10000

Tailscale Serve terminates HTTPS on tailnet-only port 10000 and proxies to the
unchanged loopback listener at 127.0.0.1:8765. Public exposure and Tailscale Funnel
remain FORBIDDEN. Do not reset shared Serve configuration or change other ports.
No wildcard/suffix request matching, CORS allowance, forwarded-header trust,
public bind, native write access or new collector scope is authorised.

After independent Core approval/merge, the installed user unit
`agent-workshop-release1.service` must have this single environment setting:

    Environment=WORKSHOP_EXTRA_ORIGIN=https://frankenfarm.taile4f46c.ts.net:10000

`Settings.extra_origin` is optional. When absent, the original loopback-only
boundary is unchanged. Invalid configured extras fail startup: only one plain
ASCII HTTPS origin with a DNS hostname under `.ts.net` is allowed; no HTTP,
public hostname, bare IP, userinfo, path, query, fragment or origin list. The
runtime boundary is an exact SET of the primary and optional extra, not a DNS
suffix rule. Host must exactly match one approved netloc, including its port;
Origin, when supplied, must exactly match one approved origin. Mutations still
require an approved Origin and the existing session/CSRF/permission checks.
In particular, the tailnet hostname WITHOUT `:10000` is rejected. X-Forwarded-*
and Forwarded cannot substitute for Host or Origin. No CORS headers are added.

Open the authorised HTTPS URL and use the same private login form. The transport
is HTTPS via Serve; the application still sets its existing host-only,
HttpOnly/SameSite Strict session cookie without Secure for loopback compatibility.
Do not use a plaintext tailnet URL. Sessions do not transfer between hostnames;
a restart revokes all sessions, so log in again. Tailnet access is not protection
against a compromised enrolled device, hostile local OS user or same-origin XSS.

Reviewed delivery must update the existing checkout only (no reinstall or data
migration), retain the exact schema2 state paths and binding/secret files, apply
the unit environment, daemon-reload and deliberately restart once on the same
boot. Preserve Restart=no, disabled boot autostart and all existing restrictions.
Verify loopback GET 200, actual HTTPS tailnet GET 200, foreign Host 403, missing
`:10000` Host 403 and wrong Origin 403. Verify historian identity/diagnostics
survive and native writes remain fixed off. If restart/recovery fails, stop and
escalate; do not replace state, remove binding fences or silently retry.

Rollback: remove only the extra-origin unit setting and deliberately restart;
loopback access remains, the tailnet Host fails closed with 403. Preserve state
and all unrelated Serve routes. This addendum is configuration guidance, not a
claim of completed deployment, owner review, MVP readiness or 30-day acceptance.
