# Review Lenses

Each lens is a separate starting point. Regenerate candidate risks from the diff for each lens you select rather than mapping one first impression onto all of them. Use at least three; use more when the change crosses process, data, and network boundaries.

## 1. Attacker

Assume the change is hostile input's best opportunity.

- Every new input path: who controls the value, what is the worst well-formed value, and what happens on the malformed one?
- Authorization on every new read/write path; ownership checks after a lookup, not instead of it.
- Secrets, tokens, or personal data crossing a new boundary: logs, error messages, telemetry, URLs.
- New outbound calls: SSRF surface, TLS verification, redirect handling, response size limits.
- Dangerous defaults newly introduced: permissive CORS, disabled verification, wildcard scopes.

## 2. Data Integrity

The failure mode is silent corruption, not an exception.

- Write paths: partial update on multi-step mutation, missing transaction boundary, lost update under concurrency.
- Migration: adds a column without default, drops before deploy drains, backfill without idempotency, index lock duration on a live table.
- Deletion and retention: soft-delete filters missing on a new query; cascade behavior changed.
- Idempotency of retries: duplicate insert, duplicate side effect, double charge.
- Type or precision change: truncation, timezone drift, integer overflow, float money.

## 3. Contract Breaker

The caller did not change, and now the caller is wrong.

- Signature or semantic change on an exported function, endpoint, event, or CLI flag; return-shape change that a consumer destructures.
- Error behavior change: an exception becomes a `null`, a retryable error becomes terminal, an error code changes meaning.
- Ordering, pagination, or default-value change that consumers depend on without documentation.
- Breaking a documented invariant: sorted output, unique ids, non-empty list, stable ordering of a map.
- Public schema or DTO changed without a versioning path.

## 4. Concurrency And Time

- Shared state without synchronization; read-modify-write on a value that another request can change.
- Check-then-act across an await, a network call, or a transaction boundary.
- Lock ordering, lock scope, and what happens when the lock holder dies.
- Timeouts, cancellation, and cleanup: does the finally/context-manager path actually run on the new branch?
- Retries: unbounded retry, retry without jitter, retry of a non-idempotent operation.
- Clock and scheduling assumptions: sleep-based waits, local-time comparisons, DST.

## 5. Operator On Call

The person paged at 3 a.m. has only what this change left behind.

- Failure visibility: new failure path with no log, or a log without the identifying key.
- Alertability: silent degradation, swallowed exception, `except: pass`, or a fallback that hides the fault.
- Rollback: does reverting the code restore the previous behavior, or has the data already been written in the new shape?
- Blast radius: is the change isolated per tenant/instance, or does it affect every request behind a shared flag?
- Resource growth: unbounded queue, cache, connection pool, or in-memory accumulation.

## 6. Scale And Cost

- N+1 queries introduced in a loop or a serializer; extra query per item on a hot path.
- Unbounded result set, unbounded fan-out, missing pagination or limit.
- Algorithmic change on a path that is O(n) per request today and O(n²) for a new input class.
- Cache key includes or omits the wrong dimension (tenant, user, locale, permission).
- New external calls on the critical path without timeout or circuit breaking.

## 7. New Teammate

The next reader has the diff, not this conversation.

- Names and structure that encode an assumption the code no longer honors.
- Dead branch, unreachable guard, or a flag that is always true.
- A comment that contradicts the code; a docstring that promises a guarantee no longer provided.
- Copy-paste residue: leftover scaffolding, debug output, disabled test, skipped assertion.
- Test that asserts the implementation's shape rather than the behavior, so it cannot catch the regression it was written for.

## 8. Test Skeptic

Tests are evidence, and they can lie.

- Does the new test fail if the fix is reverted? If not, it is decoration.
- Is the test's input the one that actually triggers the bug class (empty, boundary, concurrent, error path)?
- Mocked away the exact boundary where the defect lives?
- Test isolation: shared state, time, ordering, or network dependence that makes it flaky rather than failing.
- Coverage of the failure path versus the happy path ratio.

## Selecting Lenses

| Change shape | Minimum lens set |
|---|---|
| Auth, permissions, input parsing | Attacker, Data Integrity, Contract Breaker |
| Schema, migration, batch job | Data Integrity, Operator, Scale |
| Public API, library, shared module | Contract Breaker, New Teammate, Test Skeptic |
| Concurrency, queue, scheduler | Concurrency, Operator, Data Integrity |
| Performance-sensitive path | Scale, Operator, Data Integrity |
| Small internal refactor | New Teammate, Test Skeptic, Contract Breaker |

Record the lenses you used in the review. A lens you skipped is an uncovered surface.
