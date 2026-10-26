# super-code-review

An adversarial, evidence-gated code review skill for coding agents. It resists two symmetric failures: flattering the author ("looks clean") and flattering the asker (manufacturing findings because the user implied a problem).

The method is a transfer of the anti-sycophancy paper [`如何拒绝AI谄媚人类.md`](https://github.com/GoatGit/super-survey) into code review: rebuild the objective before judging, fix the order of operations, score the review's remaining decision gaps, and gate delivery on hard constraints instead of a quality score.

## Install

```bash
npx skills add GoatGit/super-code-review
```

Install globally (all projects) or target a specific agent:

```bash
npx skills add GoatGit/super-code-review -g
npx skills add GoatGit/super-code-review -g -a claude-code -y
```

Without the CLI, copy this repository into your agent's skill directory:

```bash
git clone https://github.com/GoatGit/super-code-review.git ~/.agents/skills/super-code-review
```

## Use

Ask for a review, change audit, regression check, or pre-merge assessment. The skill runs a fixed sequence:

```text
target -> objective projection -> fact layers -> evidence -> multi-start lenses -> adversarial check -> synthesis -> residual gate
```

Before delivering, validate the written review:

```bash
python3 scripts/check_review.py --template > review.md   # skeleton
python3 scripts/check_review.py review.md                # gate
```

The checker enforces:

- review mode (`gate` / `consult` / `learn`), scope, and probe budget are stated
- every finding carries `path:line`, a behavior, a trigger, a fix, and an evidence level (`E0`-`E3`)
- `blocking` findings need `E1` or stronger; `approve` forbids `blocking` and requires residuals at or below 1
- any residual at 3 blocks delivery
- uncovered surface, counterargument, and update rule are disclosed

Exit code is `0` when the review passes and `1` when it does not. `--json` emits machine-readable output.

## Layout

```text
SKILL.md                       workflow, evidence levels, hard rules
references/residual-model.md   7 residual dimensions and pass thresholds
references/review-lenses.md    8 review lenses and minimum lens sets
references/failure-modes.md    10 shapes of sycophantic review and their fixes
scripts/check_review.py        zero-dependency review gate
tests/                         checker tests
```

## Requirements

Python 3.9+ with the standard library only. No network access is required by any script.

## License

MIT
