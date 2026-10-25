# Gate A — retained-fact presentation correction

Implementation only; **independent Gate B review and root live acceptance remain pending**.
Task `t_53f5e3fb`; normative Core disposition `t_38604cb5`; reviewer `t_1160dd3c`.

## Source and scope

Branch `fix/release1-retained-agreement` starts at exact signed checkpoint
`5ee7ab43697ef8fc5b583341e4c45703184d586b`. The sole product merge base is
`5f7df84da20206a89d87a8ed692dff537edfefc4`. Only product change is
`collectors/workshop_collectors/workflow.py`. Other changes are one new regression
file, this evidence directory, and the mandated additive RESUME entry.

No `backend/workshop/`, adapter, outbox, schema, dependency/lock, observer-script,
service, installed historian, or native source changes. No actual native reads
or observation were performed in this implementation lane. Fixtures write only
their own temporary synthetic stores. Existing approved Python environment and
frontend node_modules were copied into this isolated no-hardlinks clone; source
links were rebound to this checkout using `scripts/dev.py install` (no downloads).
Claude Code was absent from PATH and standard local/npm-global locations, so
bounded direct implementation and explicit review were used, not an invented
harness-success claim. No owner notification, deployment, or self-approval.

## Exact contract

- Independent expected derivation, every raw current-acquisition identity/epoch/
  cursor/watermark/completeness check, all process/station/status/outcome/progress/
  tool/retry/failure checks, and global safety guard are unchanged, mandatory and
  byte-identical. `verify.py` asserts these sections against the sealed checkpoint.
- Current canonical equality is mandatory for active and terminal expectations.
- For unknown expectation only, either both mappings already equal unknown
  (`current`) or **all** retained guards must hold: stored latch is exactly True;
  supported ACTIVE-family source-record fact; invalidated canonical acquisition;
  presented mapping matches that fact, presented support is True and evidence
  source_record; presented lifecycle quality is unknown. No terminal/unsupported
  retained fact qualifies. The existing unconditional raw checks still run.
- Retained rows report actual `projected_lifecycle`, `retained_lifecycle`, unknown
  quality, latched True and `agreement_basis=retained_prior_fact`. Equality rows
  say `agreement_basis=current`; this basis is mapped equality, NOT fresh quality
  or a fleet-health claim. Global coverage partial/availability unknown/native
  controls off remain unchanged. `observe_workflow.py` needs no change.

## Reproduction and controls

`backend/tests/test_workflow_retained.py`: **34 new regression cases**.

The live-shape fixture uses the actual synthetic Hermes adapters, outbox and
Storage: three running attempts observed at10; close/reopen the SAME historian;
then at12 one blocked, one scheduled, one done/completed, plus one new running
attempt. Delivery actually reports accepted2/ignored2. The two ignored records
remain newest raw provenance (seven records total), current blocked/unknown labels
and lifecycle unknown, while canonical prior active remains acquired_at=None.
Verifier reports **two retained + two current**. `synthetic-live-shape.json` is
real execution of that fixture, not a constructed example report.

Negative cases cover retained terminal, unsupported, unknown, wrong evidence,
valid acquisition, false latch despite unknown quality, wrong projection mapping/
evidence/support, five non-unknown/missing quality values, every raw identity/
epoch/cursor/watermark/completeness/process/station/status/outcome guard, and
independent active/terminal fact/view mismatches. Fault-injection tests first
verify the unchanged mixed input passes, so their raises are not vacuous failures
on some other row. A real unknown-first/reopen/source-active transition proves
unsupported prior currency failures still raise. Four fresh first-observation
mappings (active/blocked/scheduled/terminal) retain existing behavior.

Original pre-fix red evidence: **5 failed/29 passed**, including the real retained
reproduction at the canonical equality assertion; four other failures were the
new agreement_basis assertions on otherwise agreeing fresh rows. This red run
preceded the nonvacuity preconditions added to negative tests. The current full
regression file is the committed green version, not represented as byte-identical
to the earlier red test file.

## Executed gates

| Gate | Real result |
|---|---|
| Unchanged existing backend suite (new file excluded) | 568 passed, zero skips |
| New focused regressions | 34 passed, zero skips |
| Complete backend suite | 602 passed, zero skips |
| Frontend Vitest | 57 passed |
| Actual synthetic TCP/Chromium Playwright | 4 passed; skipped0/unexpected0/flaky0 |
| Frontend typecheck/build | PASS |
| Generated schema --check | PASS |
| Compile check | PASS |
| Synthetic demo + collector demo, repeated byte-for-byte | PASS |
| `sfw npm audit --include=dev --json` | Actual exit1, exactly one HIGH: happy-dom GHSA-834v-8h66-3h79 |
| `sfw npm audit --omit=dev --json` | Exit0, zero vulnerabilities |
| Checkpoint boundaries/preserved evidence | PASS, 368 old files byte-identical; prior RESUME retained |

The development audit is **not clean**. Existing Core time-bounded dev-only
acceptance remains separate; no quarantine bypass or dependency remediation here.
Raw commands, exit codes, JUnit and Playwright JSON are committed beside this
report. The original tracked browser scene is restored byte-for-byte after the
synthetic run; new screenshot is separately saved. No stale sealed evidence was
re-executed or relabeled. `boundaries.json` records HEAD at the time the working
tree was checked; exact signed candidate head and post-commit execution are
recorded in task completion metadata and the separate exact-head artifact.

Reproduce in an equivalent approved environment:

```
/home/aaron/hermes-agent/.venv/bin/python evidence/retained-agreement/run-gates.py backend
/home/aaron/hermes-agent/.venv/bin/python evidence/retained-agreement/run-gates.py frontend
PYTHONPATH=.venv/lib/python3.11/site-packages:backend:collectors /home/aaron/hermes-agent/.venv/bin/python evidence/retained-agreement/verify.py
```

Set `WORKSHOP_GATE_EVIDENCE` to an external directory for immutable exact-head
reruns without changing the committed evidence. These scripts use no live source.

## Review focus / remaining work

Review the conjunction guarding the retained path, preservation of every raw
check, truthful per-row presentation and the nonvacuous negative cases. Gate B
must independently verify this exact signed head in its own clone and approve
before merge. PR base is `docs/release1-mvp-closure`, not main.

Root alone then performs post-review merged-head full suites and approved-local
workflow/native-fence/installed HTTPS/historian presentation verification without
resetting either retained historian or restarting the installed service. This
lane does NOT claim installed live acceptance, MVP closure, a clean dev audit,
manual assistive-technology validation, or owner-ready status.
