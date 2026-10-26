---
name: super-code-review
description: Adversarial, evidence-gated code review that resists both flattery and nit-flooding. Use when the user asks for a code review, change audit, regression check, security-sensitivity pass, or asks whether a diff is safe to merge, ship, or keep.
---

# Super Code Review

## Overview

Treat a review as a decision under constraints, not as an answer-generation task. The user's request ("review this", "is this okay?") is a starting point in the search space, not the objective function. The objective is: given the constraints that actually govern this change, what should happen next, and what evidence supports that?

Two symmetric failures define a bad review. Flattering the author ("LGTM, looks clean") accepts the change description as truth. Flattering the asker ("you're right, this is broken") manufactures findings because the user implied a problem. Both are truth-tracking failures, and both are easy to produce fluently. This skill's gates target both.

Conceptual basis: the anti-sycophancy paper `如何拒绝AI谄媚人类.md` (super-survey repo), especially 3.7 (residual-driven iteration, non-commutative operators) and 6.2-6.5 (discrete residual scoring, hard constraints, pass thresholds). The transfer is structural, not stylistic.

## Operating Order

The order of these stages is a property of the method, not a preference. Forming a verdict first and gathering support afterwards is not a review; it is an audit of a decision already made.

1. **Target** — Load the repository instructions. Identify the exact review target: commit range, PR, working tree, or named files. Never review a summary of the change when the change itself is readable.
2. **Projection (Π)** — Reconstruct the review objective. Determine the decision variable and the constraints. Record the probe budget before investigating.
3. **Fact layers** — Separate what the diff does (observed), what the author says it does (claim), and what you infer (hypothesis). These may not be merged into one narrative.
4. **Evidence (M)** — Read the whole diff, not the interesting part. Trace callers, dependents, and the invariants the change touches. Read the existing tests for those invariants. Run the narrowest command that can confirm or refute a suspicion.
5. **Multi-start (G)** — Select at least three lenses from `references/review-lenses.md` and regenerate candidate risks per lens from scratch. Do not reuse the first impression; the point is to escape the local optimum created by the diff's own narrative.
6. **Adversarial (A)** — For each surviving candidate, construct the concrete input, sequence, or state that produces the wrong behavior. Invert the new branch (fail-open ↔ fail-closed), check partial failure, cancellation, retry, and concurrency. Assign an evidence level.
7. **Synthesis (S)** — Order findings by impact × reachability × evidence strength, never by how easy they were to spot. Write a conditional verdict.
8. **Direction and stop (V)** — Score the residual vector. If any dimension is at 3, or a hard constraint is unmet, run one more targeted probe. Otherwise deliver.

## Review Target Reconstruction

Answer these before reading code in detail:

- **Mode**: `gate` (decide merge/ship), `consult` (find design problems), or `learn` (explain the change). The same finding has different value in each mode; in `gate` mode only merge-blocking issues deserve top billing.
- **Decision variable**: merge, ship, keep behind a flag, revert, or refactor now. "The code is correct" does not imply "merge now".
- **Constraints**: compatibility promises, migration and rollback, data volume and tenancy, performance budget, release window, on-call exposure, and who owns the risk after merge.
- **Budget**: how many call sites to trace, which commands may run, and whether tests are safe to execute. Register it; an unbounded adversarial loop is its own failure.

If mode or decision variable is genuinely ambiguous and the answer changes the review's shape, ask once, then proceed. Do not stall a review on information you can derive from the repository.

## Evidence Levels

Every claim carries a level, and the level is part of the finding, not a footnote.

| Level | Meaning | Allowed use |
|---|---|---|
| `E0` | Read-only inference from the diff; nothing executed or traced | `consult` material, questions, or `should-fix` at most. Never `blocking`. |
| `E1` | Static proof: call chain, type or schema contradiction, violated invariant, unreachable guard, documented contract | Any severity, including `blocking`. |
| `E2` | Reproduced: command, test, stack trace, or query output observed in this run | Any severity; required for security and data-destruction claims you call `blocking`. |
| `E3` | Reproduced and pinned: a failing test now exists in the diff or was run and reported | Strongest; use for regressions you want the author to keep. |

Never present `E0` as if it were `E2`. "This will throw on empty input" without a trace or a run is a hypothesis, and must be labeled as one.

## Adversarial Verification

A finding is only as good as the attempt to destroy it. For each candidate:

1. Write the strongest reason the change is correct.
2. Write the strongest reason it is wrong, in terms of a reachable state.
3. Construct the trigger: exact input, ordering, or configuration that exposes it.
4. Try to falsify your own finding: find the guard, caller contract, or test that already prevents it.
5. Keep the finding only if step 4 failed, or downgrade it and say what would settle it.

Prefer one reproduced defect over five plausible ones. Severity inflation is the review-side equivalent of padding a report.

## Residual Gates

Score seven dimensions from `0` (resolved for this decision) to `3` (decision-level gap). Full definitions and per-dimension examples are in `references/residual-model.md`.

- `r_q` review objective — mode, decision variable, and gate criteria still vague
- `r_c` constraints — compatibility, migration, rollback, data, perf, release window unexamined
- `r_e` evidence — blocking claims lack a trace or a reproduction
- `r_h` hypotheses — the change's implicit contracts (input ranges, upstream behavior, data scale) unverified
- `r_a` adversarial — no failing input was ever constructed; "risks" were listed instead
- `r_s` sensitivity — no statement of what scale, concurrency, or config would flip the verdict
- `r_j` action — the author cannot tell what must change, what may change, and how to verify

Hard constraints are pass/fail and cannot be offset by strength elsewhere:

- The full diff was not read.
- A hypothesis is presented as a reproduced defect.
- A `blocking` finding has no `file:line`.
- The review modified code, tests, or Git state without being asked.
- A verdict was issued without a stated mode and decision variable.
- Test or command output is cited that was never observed.

Run the checker before delivering: `python3 scripts/check_review.py <review.md>` (or `-` for stdin). It enforces sections, severity and evidence consistency, residual thresholds, and disclosure of uncovered surface.

## Output Contract

Generate the skeleton with `python3 scripts/check_review.py --template`, then fill it. Required sections: `Review Target`, `Verdict`, `Residual`, `Findings`, `Uncovered`, `Counterargument`, `Update Rule`.

Rules the checker enforces:

- `Mode` is `gate`, `consult`, or `learn`; `Scope` and `Budget` are non-empty.
- `Decision` is `approve`, `request-changes`, `block`, or `conditional`; `conditional` requires a non-empty `Condition`.
- `approve` forbids any `blocking` finding and requires all residuals at or below 1.
- Each finding header is `### F<n> [severity] path/to/file.ext:LINE` with severity in `blocking`, `should-fix`, `nit`, followed by non-empty `Behavior`, `Evidence` (with level), `Trigger`, and `Fix`.
- `blocking` findings need `E1` or stronger.
- `Uncovered` lists what you did not inspect; "none" is only valid with the reason coverage is complete.
- `Counterargument` states where your own verdict is most likely wrong.
- `Update Rule` states which later evidence would change the verdict.

Deliver findings first, ordered by severity. State verified defects, open questions, and residual risk as three separate categories. If there are no findings, say so explicitly and name the test gap or unexamined boundary.

## Stop Rule

Stop when the best remaining probe has low expected value relative to its cost and no residual sits at 3. In practice: if the next step is "read one more caller" or "run one more test" and it could plausibly change the verdict, take it; if it would only add color, deliver.

Do not iterate to look thorough. Do not compress to look decisive. Both are local optima.

## Hard Rules

- Default to read-only. Review the change; do not fix it unless the user asks for the fix in the same request.
- Stay inside the requested scope. Note adjacent risks in `Uncovered` instead of expanding the review.
- Distinguish "this is wrong" from "I would have written it differently". Style preferences are `nit` and must not borrow the language of defects.
- Do not use lint output, formatter diffs, or `TODO` comments as the review's conclusion. They are inputs, not findings, unless they change behavior.
- Do not claim a command ran, a test passed, or a defect reproduced without observed output.
- Anti-narrative check: reject "best practice", "someone might", "in some cases", and "previously we did it this way" as standalone justification.

## Failure Modes

Read `references/failure-modes.md` when a review feels suspiciously clean, suspiciously harsh, or is being produced under time pressure. It lists the ten recurring shapes of sycophantic review with the corrective move for each.

## Limits

- No probabilities. Code review has no usable base rate; numeric confidence is false precision. Use evidence levels plus reachability.
- No composite score. Turning residuals into a single quality number invites optimizing the number; the residual gate exists to prevent finalizing, not to rank reviews.
- Bounded probes. Open-ended adversarial iteration is affordable in research and not in a review someone is waiting on.
- The method cannot manufacture domain knowledge. If the invariant lives outside the repository, say so and name the owner who can confirm it.
