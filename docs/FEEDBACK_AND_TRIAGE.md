# Feedback and Triage Guide

This guide describes how to submit feedback, report bugs, or request features, and explains our internal triage workflow.

## 1. Issue Templates

All bugs and suggestions must be filed using our GitHub issue templates located in `.github/ISSUE_TEMPLATE/`.

### Bug Reports
- **Required Fields:** Version / Commit Hash, Environment (OS, Python version, Model settings), Reproduction steps, Expected behavior, Actual behavior.
- **Wording warning:** Do not include sensitive API keys, machine hostnames, or private directory paths in logs.

---

## 2. Severity Classification

We triage bugs using four severity levels:

- **Critical:** Catastrophic crashes, correctness/gating failures that break reasoning, or data loss.
- **High:** Logical isolation leakage, session burn failures, or major usability regressions.
- **Medium:** Minor timing variations, latency overheads, or packaging glitches.
- **Low:** Cosmetic issues, formatting typos, or documentation clarifications.

---

## 3. Triage Workflow & SLAS

1. **New Issue:** Automatically assigned the `needs-reproduction` label.
2. **Reproduction:** Maintainers reproduce the issue. If valid, the label is updated to `bug-confirmed` and assigned a severity.
3. **Response Expectation:** 
   - **Critical/High:** Addressed within 48 hours.
   - **Medium/Low:** Addressed in the next release cycle.
4. **Resolution:** Merged PRs must reference the issue number and include regression unit tests.
