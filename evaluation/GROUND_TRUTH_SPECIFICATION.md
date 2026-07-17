# Ground-Truth Specification

Ground truth is a structured set of acceptable properties, not one expected string.

## Required fields

For every turn, record:

- required facts and their source references;
- required active constraints and causal dependencies;
- forbidden facts, conclusions, instructions, and cross-session canaries;
- active, expired, corrected, and superseded instructions with effective turn;
- acceptable variations, synonyms, units, formats, and optional details;
- retrieval labels for each eligible memory unit: required, relevant-supporting, neutral, irrelevant, harmful, stale, or prohibited-cross-session;
- answer rubric dimensions and weights;
- expected uncertainty or abstention behavior;
- ambiguity flags and alternative valid interpretations;
- adjudication notes and failure codes.

## Answer rubric

Score separately: factual correctness, constraint compliance, completeness, source/provenance fidelity, instruction priority, uncertainty calibration, and absence of forbidden content. Each dimension is 0–4 with anchored examples. The overall score is the preregistered weighted mean; individual dimensions remain reportable.

## Retrieval ground truth

Retrieval relevance is judged against the current turn, not whether a chunk is generally related to the scenario. Required evidence is the minimal set needed for the expected answer. Duplicate chunks remain separate retrieval items but share a source group to avoid inflating coverage.

## Review and disagreement

One author and one independent reviewer are mandatory. High-value, legal, security, ambiguous, or claim-bearing scenarios require two independent human reviewers before seeing strategy outputs. Reviewers record labels independently. Disagreement is measured, discussed by an adjudicator, and preserved with original labels, final label, rationale, and timestamp.

Ambiguous scenarios are not forced into false certainty. They may allow multiple answer sets, require clarification, or be marked unsuitable for a specific metric. Dataset defects are labeled and retained; they are not counted as strategy failures.

## Ground-truth changes

Changing required/forbidden behavior creates a new scenario version. Corrections after a run generate a new evaluation artifact and impact statement; raw results remain unchanged.
