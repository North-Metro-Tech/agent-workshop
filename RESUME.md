# RESUME — Agent Workshop

Initialised 20 Oct 2026 (AEDT) from the Core handoff at
`/home/aaron/vitruvius/RESUME.md`, which this file now supersedes for project
sessions. This repository is the project home: public, Apache-2.0,
`github.com/vitruvius-nmt/agent-workshop`.

## Objective

Build the Workshop: human–machine interface for LLM-driven actors using
control-systems engineering (ISA-101 HMI, ISA-18.2-aligned alarms,
reconciliation-gated availability). Hermes is adapter one. Release 1 is a
read-only supervisory layer — Workshop observes, it never controls.

## Last decision

Repository destination resolved by discovery and vault evidence (operations
journal, 13 Oct 2026): the authorised namespace is the **North-Metro-Tech
organisation** — the prior `vitruvius-nmt/...` CreateRepository failure was
historical precedent for exactly this. Repository does not yet exist remotely;
the host PAT lacks org-level `CreateRepository`, so creation is an owner
action (org URL: https://github.com/organizations/North-Metro-Tech/repositories/new).
Local repository is initialised with README, Apache-2.0 licence and this
handoff; `origin` points at `North-Metro-Tech/agent-workshop` ready for the
first push once created. Core packaged the project and filed the first
implementation card on the `agent-workshop` Kanban board (`t_941ea707`,
assignee `coder`, workspace `dir:/home/aaron/projects/agent-workshop`).
Delivery roster remains editorial + coder; model routes locked to 18 Jan 2027
review.

## Next action

Coder executes `t_941ea707`: write failing Phase 1 fixture tests for A01–A04,
then implement the reducer until they pass. Preserve actual failing and
passing test output. Nothing else — no renderer, live integrations, fleet
restructuring, novel work, profile restructuring or further spec pass.

## Open question

None blocking. Remote creation is the single owner action (Todoist); local
Phase 1 work is not blocked by it. Recorded, not yet reconciled: coder
AGENTS.md describes an isolated profile git/gh identity, but the profile's
live config reads `home_mode: host`; routing facts travel on the card.

## References

- Specification v1.1:
  `/home/aaron/vitruvius/.hermes/plans/2026-10-20_000818-agent-workshop-technical-specification.md`
- Owner direction:
  `/mnt/ironwolf/obsidian/vault/agent-workshop-direction-2026-10-20.md`
- Kanban board: `agent-workshop` (card `t_941ea707`)
- Superseded handoff: `/home/aaron/vitruvius/RESUME.md`
