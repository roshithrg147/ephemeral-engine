# SC-EVM Request for Comments

This directory is the decision record for significant SC-EVM product and architecture changes.

Every RFC must align with:

- [Product Manifesto](../MANIFESTO.md) — highest-level product philosophy and decision principles.
- [Product Boundary](../PRODUCT_BOUNDARY.md) — authoritative product scope, MVP, classifications, and non-goals.
- [Architecture](../ARCHITECTURE.md) — current implemented architecture, experiments, limitations, and proposed work.

## When an RFC is required

An RFC must precede a significant product, architecture, commercial, or compatibility decision, including:

- Product-boundary changes.
- Architectural subsystem additions or removals.
- Persistence-model changes.
- Security-boundary changes.
- Model-provider contract changes.
- Context-admission policy changes.
- Backward-incompatible API changes.
- Benchmark-methodology changes affecting commercial claims.
- New commercial editions or packaging boundaries.

An RFC is not required for typo or formatting fixes, internal refactors with no behavioral or architectural effect, routine test additions, dependency patch updates with no material design consequence, or documentation corrections that only align text with accepted behavior.

A significant change must not become canonical until its RFC is Accepted.

## RFC lifecycle

1. Copy [RFC-0000-template.md](RFC-0000-template.md) and assign the next available number.
2. Develop the proposal as **Draft**.
3. Move it to **Under Review** when reviewers and validation criteria are identified.
4. Record the outcome as **Accepted** or **Rejected**.
5. Mark an abandoned proposal **Withdrawn**.
6. Mark an older accepted record **Superseded** only when a later accepted RFC explicitly replaces it.

Accepted RFCs are controlled decision records. Clarifications may correct wording without changing the decision; material changes require a superseding RFC.

## Accepted statuses

- **Draft:** incomplete and not ready for review.
- **Under Review:** complete enough for formal review and decision.
- **Accepted:** approved and canonical.
- **Rejected:** considered and declined.
- **Superseded:** replaced by a later accepted RFC.
- **Withdrawn:** removed from consideration by its author before a decision.

## Numbering and naming

RFC numbers are sequential and never reused. Filenames use `RFC-NNNN-short-title.md`. Cross-references must use relative links, and superseding RFCs must name every record they replace.

`RFC-0000` is the reusable template and is not a decision. Rejected, withdrawn, and superseded numbers remain reserved.

## Proposed queue

The following topics reserve the expected sequence but are not decisions and do not yet have RFC files:

- RFC-0002 — Architecture Canonicalization
- RFC-0003 — Benchmark Methodology
- RFC-0004 — Provider Abstraction
