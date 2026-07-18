# SC-EVM Development Handoff

**Snapshot date:** 2026-07-18  
**Workspace:** `/home/rg/Codebase/Anthropic-VertexAI-Agent`  
**Repository:** `git@github.com:roshithrg147/ephemeral-engine.git`  
**GitHub Project:** [SC-EVM Product & Engineering](https://github.com/users/roshithrg147/projects/3)

## Purpose

This document is the durable continuation point for a new Codex chat. It records
verified repository and GitHub state, decisions made, unfinished work, and the
recommended execution order. The new chat must verify live state before making
changes because Git and GitHub may have changed after this snapshot.

## Source-of-Truth Order

When records disagree, use this order:

1. `MANIFESTO.md`
2. `PRODUCT_BOUNDARY.md`
3. Accepted records under `rfcs/`
4. `ARCHITECTURE.md`
5. GitHub issue acceptance criteria
6. GitHub Project fields and status
7. Pull-request descriptions
8. This handoff
9. Informal chat history

This handoff summarizes state. It does not supersede product or architecture
governance.

## Verified Git State

- Current branch: `agent/github-project-workflow`
- Current commit: `5bd13be`
- `main` and `origin/main` were also at `5bd13be` when this snapshot was made.
- The working tree contains intentional, uncommitted GitHub governance changes.
- `git diff --check` passes.
- Do not discard, overwrite, or reset these changes.

Tracked modifications:

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `README.md`

Untracked files:

- `.github/ISSUE_TEMPLATE/architecture_change.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/ISSUE_TEMPLATE/engineering_task.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `docs/GITHUB_PROJECTS_OPERATING_GUIDE.md`
- `docs/NEXT_SESSION_HANDOFF.md`

The governance changes have not been committed or pushed from this branch.

## Verified GitHub Authentication

GitHub CLI is authenticated as `roshithrg147`.

Verified token scopes:

- `project`
- `repo`
- `read:org`
- `gist`

Git transport uses SSH. During authentication, uploading a new SSH key was
deliberately skipped so repository security settings remained unchanged.

## GitHub Project State

Project number: `3`  
Visibility: private  
Linked repository: `roshithrg147/ephemeral-engine`  
Items: seven open issues, all in `Backlog`

The Project description and readme require alignment with the Manifesto,
Product Boundary, accepted RFCs, and Architecture.

Configured custom fields:

- Status: Inbox, Backlog, Ready, In Progress, Review, Blocked, Done
- Priority: P0 Critical, P1 High, P2 Medium, P3 Low
- Type: Product, Architecture / RFC, Engineering, Security, Evaluation,
  Documentation, Operations
- Product Pillar: Relevance, Isolation, Control, Evidence
- Release Gate: Developer Preview, Public Pilot, Production,
  Research / No Release
- RFC Required: Yes, No, To Determine
- Effort: XS, S, M, L, XL

## Seeded Backlog

| Issue | Priority | Type | Pillar | Gate | RFC | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| [#5 Authenticated principals, session ownership, and authorization](https://github.com/roshithrg147/ephemeral-engine/issues/5) | P0 | Security | Isolation | Public Pilot | Yes | XL |
| [#8 Diagnostic context, audit redaction, retention, and deletion](https://github.com/roshithrg147/ephemeral-engine/issues/8) | P0 | Security | Isolation | Public Pilot | Yes | L |
| [#7 RFC-0004 provider abstraction contract](https://github.com/roshithrg147/ephemeral-engine/issues/7) | P1 | Architecture / RFC | Control | Research / No Release | Yes | L |
| [#4 Deployable session state and concurrency model](https://github.com/roshithrg147/ephemeral-engine/issues/4) | P1 | Architecture / RFC | Isolation | Public Pilot | Yes | XL |
| [#2 Governed live-provider certification campaign](https://github.com/roshithrg147/ephemeral-engine/issues/2) | P1 | Evaluation | Evidence | Public Pilot | No | L |
| [#6 Reconcile architecture gaps with current behavior](https://github.com/roshithrg147/ephemeral-engine/issues/6) | P1 | Documentation | Evidence | Developer Preview | No | M |
| [#3 Continuous integration validation gates](https://github.com/roshithrg147/ephemeral-engine/issues/3) | P1 | Engineering | Evidence | Developer Preview | No | M |

Each issue contains evidence, boundaries, and testable acceptance criteria.
None is Ready because required decisions, dependencies, or preparation remain
incomplete.

## Incomplete Project Configuration

GitHub CLI and the public GraphQL schema do not expose mutations for creating
Project views or configuring built-in workflow rules.

Current view state:

- `View 1`, table layout, no filter

Current workflow state:

- Auto-add sub-issues to project: enabled
- Auto-close issue: disabled
- Item added to project: disabled
- Item closed: disabled
- Pull request linked to issue: disabled
- Pull request merged: disabled

Desired views:

1. Execution Board: board grouped by Status
2. Prioritized Backlog: Inbox, Backlog, and Ready grouped by Priority
3. Current Work: In Progress, Review, and Blocked
4. RFCs and Decisions: RFC Required is Yes
5. Release Gates: grouped by Release Gate and sorted by Priority
6. Roadmap: create only when dates are evidence-based

Desired workflow behavior:

1. Auto-add new issues and pull requests from `ephemeral-engine`.
2. Set newly added items to Inbox.
3. Set closed issues and pull requests to Done.
4. Set reopened items to Inbox.

Chrome and the GitHub API both confirmed the account and Project exist.
However, the GitHub Projects web editor rendered a blank application area in
desktop Chrome while the Projects list and the GitHub app remained accessible.
GitHub status showed no service incident. Treat this as a local browser asset,
extension, cache, or content-filter problem. Do not use unsupported internal
GitHub endpoints to bypass it.

## Strategic Execution Recommendation

This section is a general fallback analysis. The requested
`Strategic-Execution-Coach` skill was not present in the active skill catalog
or anywhere under `/home/rg/.codex`, so it was not run.

### Phase 0: Stabilize governance delivery

1. Review the local issue templates, pull-request template, README links, and
   operating guide.
2. Validate YAML, Markdown links/fences, and whitespace.
3. Commit the intentional governance files on
   `agent/github-project-workflow`.
4. Push the branch and open a focused pull request.
5. Complete Project views and workflows when the GitHub web editor works.

Why first: the Project should have a durable operating guide and issue intake
contract before development accelerates.

### Phase 1: Make current state trustworthy

1. Execute issue #6 and reconcile every architecture gap against current source
   and tests.
2. Execute issue #3 and add deterministic, secret-free CI gates.

Why next: planning and release decisions should rely on current evidence and
automated validation.

### Phase 2: Resolve public-boundary security decisions

1. Develop and accept the RFC governed by issue #5.
2. Develop and accept the RFC governed by issue #8.
3. Split accepted decisions into bounded implementation issues.

Do not implement a broad authentication or audit redesign before these RFCs
define the boundary.

### Phase 3: Resolve deployment and provider contracts

1. Develop the deployment-state RFC under issue #4.
2. Complete RFC-0004 under issue #7.
3. Create implementation issues only after each RFC is accepted.

### Phase 4: Produce claim-bearing evidence

1. Run a successful provider connectivity and single-call probe.
2. Freeze the governed campaign inputs.
3. Execute issue #2 using accepted RFC-0003 methodology.
4. Publish only claims supported by certification output.

## Next-Chat Startup Procedure

The next chat should:

1. Read `AGENTS.md` and this file completely.
2. Read `MANIFESTO.md`, `PRODUCT_BOUNDARY.md`, `rfcs/README.md`, and
   `ARCHITECTURE.md`.
3. Run `git status --short --branch` and inspect the complete working-tree diff.
4. Verify GitHub CLI authentication with `gh auth status`.
5. Refresh Project 3 metadata, fields, items, views, and workflows.
6. Preserve all existing local changes.
7. Start with Phase 0 unless the user explicitly selects another issue.

## Copy-Paste Prompt for the New Chat

```text
Continue SC-EVM development in:
/home/rg/Codebase/Anthropic-VertexAI-Agent

Read AGENTS.md and docs/NEXT_SESSION_HANDOFF.md completely before acting.
Then read MANIFESTO.md, PRODUCT_BOUNDARY.md, rfcs/README.md, and
ARCHITECTURE.md. Treat those documents in that authority order.

Verify the live Git state and GitHub Project 3 state before making changes.
Preserve every existing working-tree change; do not reset, discard, or
overwrite them. The current branch should be agent/github-project-workflow.

Begin with Phase 0 from the handoff: review and validate the local GitHub
governance files, fix only concrete issues, run proportional checks, and report
whether the branch is safe to commit and push. Do not implement P0 architecture
work before its RFC is accepted.

GitHub Project:
https://github.com/users/roshithrg147/projects/3

Also check whether the Strategic-Execution-Coach skill is available in this new
session. If it is unavailable, say so and continue from the handoff without
pretending it was run.
```

## Handoff Rule

Do not paste the entire historical chat into the new session unless a disputed
decision requires exact wording. The repository, GitHub issues, Project fields,
and this handoff are the operational context. They are smaller, verifiable, and
less likely to preserve stale assumptions than a raw transcript.
