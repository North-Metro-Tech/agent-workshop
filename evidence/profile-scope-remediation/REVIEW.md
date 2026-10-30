# Stage 1: approved Core profile identifier correction

Task: t_4002229b. Authority: Core ruling t_684f0878 and the two-stage instruction on this card.
Base: `feat/phase3-mvp`, `60f507670cfa46facd01638dc272d804d7edad73`.
Branch: `fix/approved-core-profile`.

## Change and fences

The sole production change is `approved_scope().profiles` from `('coder', 'vitruvius-core')` to `('coder', 'default')`. Core confirmed default is its actual operator identity and vitruvius-core was never provisioned. The board/path/source-instance pinning and entire fail-closed `observe()` implementation are byte-identical. Three test fixture pins and the two specified scope documents are updated. Six regression cases pin the factory's exact tuple, coder/default admission, unchanged null-profile treatment, and rejection of vitruvius-core/unapproved profiles without native byte/schema mutations. Every native store in these tests is synthetic; the factory policy is transplanted into a temporary synthetic path, not used to acquire the real board.

`verify_scope.py` proves the production diff is precisely the tuple replacement, checks the exact runtime lock/import provenance, preserves demo.py/lock/manifests/RESUME.md byte-for-byte, and checks all 472 named backend results with zero skips.

No dependencies installed, no config/native-board changes, no live acquisition, no service deployment, no RESUME update, and no new runtime controls. Existing failed twelve-scenario transcripts on `test/release1-integrated-scenarios` at `92d1607e1ad7c2b92d821fa7e993f53d9c7bace0` are untouched. Claude Code remains absent from PATH; this bounded change used the previously recorded authorized direct fallback. Internal validation is not independent approval.

## Actual results and raw evidence

- `regression-before.txt`: new regression tests against ORIGINAL production tuple: 3 failed, 3 passed, 31 deselected. Failures establish wrong factory tuple, rejected default, admitted obsolete vitruvius-core.
- `regression-after.txt`: SAME six tests after the sole production fix: 6 passed, 31 deselected.
- `backend-full.txt`: full backend suite, 472 passed in 18.36s, zero skips; synthetic TCP/service tests included.
- `integrity.txt`: candidate import provenance, all 14 locked runtime versions, exact one-tuple production diff, unchanged guard/demo/manifests/RESUME, raw-result checks: passed.
- `schema-check.txt`: both generated TypeScript and JSON schema verified current.
- `git diff --check`: passed, with a directory-local exception only for pytest's trailing spaces in the raw `regression-before.txt` assertion capture; no source whitespace exemptions.

Runtime reused only this project's already-approved installed Python 3.11 lock environment, plus the existing approved pytest interpreter. No install or package update. Reproduce from this branch's repository root in this workspace:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend:$PWD/collectors:$PWD/../validation-f429-integrated/.venv/lib/python3.11/site-packages" /home/aaron/hermes-agent/.venv/bin/python -m pytest backend/tests -v --no-header --tb=short -p no:cacheprovider
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend:$PWD/collectors:$PWD/../validation-f429-integrated/.venv/lib/python3.11/site-packages" /home/aaron/hermes-agent/.venv/bin/python evidence/profile-scope-remediation/verify_scope.py
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/backend:$PWD/collectors:$PWD/../validation-f429-integrated/.venv/lib/python3.11/site-packages" /home/aaron/hermes-agent/.venv/bin/python scripts/generate_schema.py --check

## Independent Core review and routing — NOT task completion

This is the requested Stage 1 checkpoint, not twelve-scenario acceptance. Review the exact candidate independently; if approved, integrate into `feat/phase3-mvp`, record the actual merge head, then RETURN THIS CARD TO CODER FOR STAGE 2. Do NOT mark this scenario card done upon approving only the tuple change: that would prematurely release deployment/final/root children (`t_2ec73616`, `t_a87670b9`, `t_7e8a8223`, inspected and still gated). The task remains incomplete until Stage 2 evidence and its final independent gate.

Stage 2 must freshly regenerate all twelve raw named transcripts at the exact integrated merge head, product read-only; A05/A06/A08/A10/A25 must execute actual `observe_workflow.py --approved-local` successfully with native main/schema unchanged, agreement report and task-scope denial. Actual provisioned browser tests must have zero skips. Preserve the failed prior evidence; no relabeling. Local-only evidence branch, no pull-request URLs in board handoffs (standing respawn-guard hygiene). No auto-merge or self-approval. Frontend/browser/full twelve-scenario/live integration are deliberately not rerun before Stage 1 independent integration, and no such pass is claimed.
