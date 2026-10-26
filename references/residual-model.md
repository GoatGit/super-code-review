# Residual Model For Code Review

The residual vector is inherited from the anti-sycophancy paper (`如何拒绝AI谄媚人类.md`, 3.7.1 and 6.2) and re-specified for review decisions. A residual is an uncovered gap in the decision, not a defect count. Two reviews with the same findings can have very different residuals.

## Dimensions

| Key | Dimension | High-residual evidence in a review |
|---|---|---|
| `r_q` | Review objective | Mode never stated; "review" silently means "approve"; merge criteria are the reviewer's habits rather than the project's gates; the user asked a design question and received a defect list |
| `r_c` | Constraints | Compatibility promise, migration path, rollback plan, data volume, tenancy, performance budget, release window, or on-call exposure not examined; the review treats code correctness as the whole decision |
| `r_h` | Hypotheses | The change's implicit contracts unverified: upstream always returns a non-null field, the table stays under a million rows, callers only pass one tenant id, the queue is not reordered |
| `r_e` | Evidence | A `blocking` claim rests on reading the diff alone; no caller traced; no test or command run; a claim is cited as reproduced without observed output |
| `r_a` | Adversarial | "Risks" enumerated but no failing input, sequence, or state constructed; the strongest opposing argument was never written; the reviewer only searched for confirmation |
| `r_s` | Sensitivity | Nothing says which scale, concurrency level, payload size, or configuration would turn "fine" into "broken"; the verdict reads as unconditional |
| `r_j` | Action | Findings without fixes or without required/optional distinction; the author cannot tell what must change before merge and how to verify the change |

## Score Levels

| Score | Meaning | Consequence |
|---|---|---|
| 0 | Settled for this decision: evidence, constraint, or action meaning is explicit | May support the verdict |
| 1 | Minor gap that would not change the verdict | State it as an assumption or a follow-up |
| 2 | Decision-level gap that could change approve/request-changes | Probe it, or convert the verdict into an explicit conditional branch |
| 3 | Severe gap: the verdict as stated would mislead | Do not deliver; run one more targeted probe |

Any dimension at 3 blocks delivery regardless of how strong the other dimensions are. This is the whole point of the vector: strong evidence does not compensate for an unexamined constraint.

## Aggregation And Hard Constraints

Soft aggregation is `Φ = Σ w_i r_i`, equal weights by default. It is diagnostic, not a score to optimize. Raise weights for the dimensions the stakes actually depend on:

- Production data, migrations, tenancy, auth: raise `r_c`, `r_e`, `r_a`.
- API or library surface: raise `r_c` and `r_h` (contract breaks are the failure mode).
- Internal refactor with tests: `r_a` and `r_s` matter more than exhaustive reading.
- Early design consult: `r_q` and `r_h` dominate; defect enumeration is premature.

Hard constraints (`h_k`) are not weighted:

1. Whole diff read, not sampled.
2. Every `blocking` finding has `file:line`.
3. Evidence level matches how the claim was established.
4. No fabricated command, test, or coverage result.
5. Review target and mode stated.
6. No mutation of code, tests, or Git state unless requested.

Violating any `h_k` fails the review even when every residual is 0.

## Stop Rule

Continue probing while a residual at 3 exists and the next probe could plausibly change the verdict. Stop when the best remaining probe is unlikely to change the decision and its cost is non-trivial. Write the stopping reason into `Uncovered` or `Update Rule` so the reader sees the boundary rather than assuming completeness.

## Reviewer Weights By Mode

| Mode | Typical failure if weights are wrong |
|---|---|
| `gate` | Compressing to a verdict while a merge-blocking constraint is unexamined |
| `consult` | Producing a defect list for a design question that needed an objective and assumption review |
| `learn` | Explaining mechanics while never stating what the change risks |

## What Not To Do

- Do not report `Φ` as a quality score or compare reviews by it.
- Do not lower a residual because the finding is hard to probe; record it and say what would settle it.
- Do not raise a severity to satisfy a residual; residuals describe the review, not the code.
