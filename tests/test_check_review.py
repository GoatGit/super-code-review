from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "check_review.py"
REQUIRED_SECTIONS = (
    "## Review Target",
    "## Verdict",
    "## Residual",
    "## Findings",
    "## Uncovered",
    "## Counterargument",
    "## Update Rule",
)


def run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        text=True,
        input=stdin,
        capture_output=True,
    )


def finding(
    identifier: str = "F1",
    severity: str = "blocking",
    location: str = "src/queue.py:88",
    behavior: str = "Retry loop re-enqueues a job that already succeeded.",
    evidence: str = "E2 reproduced: python -m pytest tests/test_queue.py -k retry",
    trigger: str = "Two workers pick up the same job after the visibility timeout expires.",
    fix: str = "Make the enqueue conditional on the persisted attempt counter.",
) -> str:
    return "\n".join(
        [
            "### %s [%s] %s" % (identifier, severity, location),
            "",
            "- Behavior: %s" % behavior,
            "- Evidence: %s" % evidence,
            "- Trigger: %s" % trigger,
            "- Fix: %s" % fix,
        ]
    )


def build_review(
    *,
    mode: str = "gate",
    scope: str = "commit 4f2a1c..9d3b0e",
    budget: str = "trace up to 5 callers; run tests/test_queue.py only",
    decision: str = "request-changes",
    summary: str = "The retry change can duplicate a completed job; merge is blocked.",
    condition: str = "",
    findings: list[str] | None = None,
    residuals: dict[str, int] | None = None,
    uncovered: str = "- src/metrics.py not read: outside the reviewed change",
    counterargument: str = "- The duplicate may be absorbed downstream by the idempotency key.",
    update_rule: str = "- A test proving the retry path re-reads the attempt counter changes the verdict.",
) -> str:
    if findings is None:
        findings = [finding()]
    if residuals is None:
        residuals = {"q": 0, "c": 1, "e": 0, "h": 1, "a": 0, "s": 1, "j": 0}
    residual_block = "\n".join("- r_%s: %d" % (key, value) for key, value in residuals.items())
    verdict_lines = ["- Decision: %s" % decision, "- Summary: %s" % summary]
    if condition:
        verdict_lines.append("- Condition: %s" % condition)
    findings_block = "\n\n".join(findings) if findings else "- No findings."
    return "\n\n".join(
        [
            "# Super Code Review",
            "## Review Target\n\n- Mode: %s\n- Scope: %s\n- Budget: %s" % (mode, scope, budget),
            "## Verdict\n\n" + "\n".join(verdict_lines),
            "## Residual\n\n" + residual_block,
            "## Findings\n\n" + findings_block,
            "## Uncovered\n\n" + uncovered,
            "## Counterargument\n\n" + counterargument,
            "## Update Rule\n\n" + update_rule,
        ]
    ) + "\n"


class CheckReviewCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write_review(self, text: str, name: str = "review.md") -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def assert_error(self, result: subprocess.CompletedProcess[str], code: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[%s]" % code, result.stdout)

    def test_template_lists_every_required_section(self) -> None:
        result = run_cli("--template")
        self.assertEqual(result.returncode, 0, result.stderr)
        for heading in REQUIRED_SECTIONS:
            self.assertIn(heading, result.stdout)

    def test_template_is_rejected_until_filled(self) -> None:
        template = run_cli("--template").stdout
        result = run_cli(str(self.write_review(template)))
        self.assertEqual(result.returncode, 1)
        self.assertIn("[missing-scope]", result.stdout)

    def test_valid_request_changes_review_passes(self) -> None:
        path = self.write_review(build_review())
        result = run_cli(str(path))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)
        self.assertIn("phi=3", result.stdout)

    def test_valid_approve_without_findings_passes(self) -> None:
        text = build_review(
            decision="approve",
            summary="The rename is mechanical; no behavior change was found.",
            findings=[],
            residuals={key: 0 for key in ("q", "c", "e", "h", "a", "s", "j")},
            uncovered="- No surface skipped: full diff read and all 2 callers traced.",
        )
        result = run_cli(str(self.write_review(text)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_approve_with_blocking_finding_fails(self) -> None:
        text = build_review(
            decision="approve",
            summary="Everything looks fine and the change is safe to merge.",
            residuals={key: 0 for key in ("q", "c", "e", "h", "a", "s", "j")},
        )
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "approve-with-blocking")

    def test_residual_three_blocks_delivery(self) -> None:
        residuals = {"q": 0, "c": 0, "e": 3, "h": 0, "a": 0, "s": 0, "j": 0}
        result = run_cli(str(self.write_review(build_review(residuals=residuals))))
        self.assert_error(result, "residual-critical")

    def test_blocking_finding_needs_more_than_read_only_inference(self) -> None:
        text = build_review(findings=[finding(evidence="E0 looks unsafe from the diff")])
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "weak-evidence-for-blocking")

    def test_finding_location_requires_a_line_number(self) -> None:
        text = build_review(findings=[finding(location="src/queue.py")])
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "bad-location")

    def test_missing_section_fails(self) -> None:
        text = build_review().replace("## Counterargument", "## Notes")
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "missing-section")

    def test_conditional_decision_requires_condition(self) -> None:
        text = build_review(decision="conditional")
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "conditional-without-condition")

    def test_conditional_decision_with_condition_passes(self) -> None:
        text = build_review(
            decision="conditional",
            condition="Merge only after the retry path is proven idempotent by a failing-then-passing test.",
        )
        result = run_cli(str(self.write_review(text)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_placeholder_uncovered_fails(self) -> None:
        text = build_review(uncovered="- <files not examined>")
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "uncovered-empty")

    def test_approve_requires_low_residuals(self) -> None:
        residuals = {"q": 0, "c": 2, "e": 0, "h": 0, "a": 0, "s": 0, "j": 0}
        text = build_review(
            decision="approve",
            summary="No defect found in the reviewed diff; safe to merge.",
            findings=[],
            residuals=residuals,
        )
        result = run_cli(str(self.write_review(text)))
        self.assert_error(result, "residual-over-threshold")

    def test_stdin_and_json_output(self) -> None:
        result = run_cli("-", "--json", stdin=build_review())
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["residuals"]["r_c"], 1)
        self.assertEqual(payload["max_residual"], 1)
        self.assertEqual(payload["errors"], [])

    def test_unsorted_findings_only_warns(self) -> None:
        findings = [
            finding(identifier="F1", severity="nit", evidence="E1 style guide section 4"),
            finding(identifier="F2", severity="blocking"),
        ]
        result = run_cli(str(self.write_review(build_review(findings=findings))))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[unsorted-findings]", result.stdout)

    def test_missing_review_file_uses_usage_exit_code(self) -> None:
        result = run_cli(str(self.root / "absent.md"))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
