# Failure Modes

Ten recurring shapes of sycophantic review. Each entry gives the symptom, why the gate misses it, and the corrective move. Read this when a review feels too smooth, too harsh, or was produced under time pressure.

## 1. LGTM By Description

**Symptom**: The review mirrors the change description ("adds retry to the upload path") and confirms the code does that, then approves.
**Why it passes**: The stated goal is satisfied, so nothing looks missing.
**Fix**: Treat the description as a claim layer, not as truth. Ask what the change does that the description omits, especially behavior change on existing paths.

## 2. Nit Dump

**Symptom**: Long list of naming, formatting, and preference suggestions; no statement about whether the change is safe.
**Why it passes**: Volume reads as thoroughness.
**Fix**: Rank by impact × reachability. Anything that does not change behavior is `nit` and belongs in a short tail, never at the top.

## 3. Hallucinated Defect

**Symptom**: A confident claim about a bug that a trace would refute ("this will throw on empty list" when the caller guards it).
**Why it passes**: The code pattern genuinely appears dangerous in isolation.
**Fix**: Trace the caller and the guard before writing the finding. If untraced, it is `E0` and must be labeled a question, not a defect.

## 4. Unfalsifiable Risk

**Symptom**: "This could cause issues under high load", "not thread-safe in general", "may violate policy".
**Why it passes**: It is hedged, so it cannot be proven wrong.
**Fix**: Convert to a trigger: which input, which concurrency, which configuration, and what visible outcome. If no trigger can be named, drop it or move it to `Uncovered` as an open question.

## 5. Severity By Ease

**Symptom**: The obvious, easy-to-spot issue is `blocking`; the subtle data-integrity issue is a footnote.
**Why it passes**: Effort feels like importance.
**Fix**: Assign severity from impact and reachability first, then disclose evidence level separately. A hard-to-spot defect is not less severe.

## 6. Approval Inflation

**Symptom**: `approve` with a paragraph of real risks attached, effectively transferring the decision back to the author without a recommendation.
**Why it passes**: It reads as balanced.
**Fix**: If a risk is decision-relevant, the verdict is `conditional` with an explicit condition. "Approve with caveats" that matter is a contradiction.

## 7. Missing Disclosure

**Symptom**: No statement of what was not read: untouched call sites, unrun tests, unexamined config, assumed deployment.
**Why it passes**: The review looks complete because it does not mention its own boundary.
**Fix**: `Uncovered` is mandatory. Name the specific file, caller, or test that was skipped and why.

## 8. Audit Theater

**Symptom**: Long methodology preamble, lens lists, residual tables, and severity scales, with thin findings.
**Why it passes**: It follows the process format.
**Fix**: The process is internal scaffolding. Deliver findings, evidence, boundary, and counterargument. Delete anything that only demonstrates diligence.

## 9. Scope Creep

**Symptom**: The review drifts into refactoring advice, architecture opinions, and unrelated pre-existing defects, while the requested change stays unreviewed.
**Why it passes**: Everything raised is technically true.
**Fix**: Keep the requested change as the subject. Pre-existing issues go into a clearly separated, optionally empty section, or are omitted.

## 10. Fixing While Reviewing

**Symptom**: The reviewer edits files, rewrites tests, or commits, then reports the change as reviewed.
**Why it passes**: The result works.
**Fix**: Review is read-only by default. Editing moves the evidence: the diff under review no longer exists, and the author loses the chance to judge the change.

## Cross-Cutting Guard

Run one question over the finished review: **if the author disagreed with every finding, which one would still be defensible?** If the answer is "none", the review is performance rather than evidence. If the answer is "all of them, obviously", the review is likely severity inflation. Both point back to the residual vector, not to more prose.
