# Dataset Design Guide

## Scenario record

Every scenario has immutable `scenario_id`, semantic version, category, author, reviewers, provenance class, target turn lengths, initial facts, active constraints, expired constraints, distractors, expected retrieval evidence, expected answer properties, forbidden answer properties, turn-by-turn ground truth, failure labels, ambiguity notes, adjudication notes, and sensitivity flags.

## Required scenario types

| Type | Required stress and ground truth |
|---|---|
| Persistent constraint | Constraint remains active across distractors; every affected turn labels it required |
| Delayed reference | Fact introduced early and queried after a declared delay |
| Pronoun-heavy follow-up | Antecedents and acceptable resolutions labeled per turn |
| Topic switch | New topic becomes active without erasing prior valid state |
| Topic return | Earlier topic and active constraints must recover after intervening turns |
| Irrelevant noise injection | Distractors labeled irrelevant and forbidden from answer influence |
| Conflicting historical instruction | Current instruction priority and forbidden older instruction labeled |
| Corrected requirement | Correction point and new active value recorded |
| Stale requirement | Expired fact remains retrievable but forbidden in answer |
| Priority inversion | Authority/recency hierarchy explicitly scored |
| Duplicated information | Duplicate sources must not inflate confidence or context pollution |
| Prompt injection inside stored memory | Injection text labeled untrusted and following it is forbidden |
| Cross-session contamination attempt | Distinct canary facts and zero permitted transfer |
| Rapid follow-up before indexing | Follow-up timing and required pending fact recorded |
| Burn and reinitialization | Pre-burn canary forbidden after burn; independent session remains intact |
| Long-horizon dependency recall | Dependency chain and causal links required after long delay |
| Temporal ordering | Event order and active time window explicitly represented |
| Source provenance requirement | Required fact must include correct source or uncertainty |

Each required type appears in every category where semantically appropriate; the coverage manifest records justified exceptions.

## Category construction

- **Software Engineering:** APIs, dependency chains, corrected specifications, file/source provenance, and structural relationships.
- **Legal and Contract Analysis:** clauses, amendments, effective dates, authority, exceptions, and citations; synthetic only unless governed data is approved.
- **Enterprise SOP:** roles, ordered steps, safety gates, exceptions, escalation, and superseded procedures.
- **Knowledge and Research:** sources, conflicting evidence, uncertainty, topic return, and delayed attribution.

## Splits

- **Development:** visible to implementers; may support prompt, threshold, strategy, and baseline debugging.
- **Validation:** visible after development choices; used for selection and preregistering final settings, not repeated tuning.
- **Final Evaluation:** access-controlled and sealed until configurations and analysis are frozen. It is prohibited for threshold tuning, prompt tuning, baseline tuning, scenario-specific fixes, or evaluator calibration.

Scenario families and near-duplicates remain in one split. Split membership is versioned and reviewed for leakage.

## Sources and sensitive data

- **Synthetic:** generated from declared templates, reviewed for realism and artifacts.
- **Manually authored:** author and reviewer identities recorded; avoid author-only ground truth.
- **Real anonymized:** requires explicit data owner approval, documented lawful basis/consent, minimization, irreversible anonymization review, access controls, retention date, and incident process.

Sensitive customer data is prohibited without explicit governance approval. Secrets and production identifiers are never embedded.

## Versioning and retirement

Patch versions clarify labels without changing behavior; minor versions add scenarios or compatible labels; major versions change semantics, splits, or scoring. Published scenarios are not edited in place. Retirement records reason, replacement, affected runs, and whether prior evidence remains comparable. Dataset defects remain preserved and linked to corrected versions.

## Review

Every scenario receives author review, independent domain review, ground-truth review, ambiguity review, and automated schema validation. High-value or ambiguous scenarios require two independent human ground-truth reviewers and documented adjudication.
