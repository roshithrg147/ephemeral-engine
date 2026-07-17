# Evaluation Methodology Summary

SC-EVM utilizes a controlled evaluation framework to generate reproducible evidence.

## Campaign Configuration
- **Fixed Seeds:** All campaigns run across three seeds: `(11, 42, 101)`.
- **Baselines:** Results are compared against six baselines: Full Replay, Sliding Window, Rolling Summary, Top-K Retrieval, SC-EVM without Graphify, and SC-EVM with Graphify.
- **Statistical Bootsrapping:** Standardized mean differences and confidence intervals are computed using 10,000 bootstrap resamples.
