#!/usr/bin/env python3
"""Validate a super-code-review report against the review contract and residual gates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "review target",
    "verdict",
    "residual",
    "findings",
    "uncovered",
    "counterargument",
    "update rule",
)
MODES = ("gate", "consult", "learn")
DECISIONS = ("approve", "request-changes", "block", "conditional")
SEVERITIES = ("blocking", "should-fix", "nit")
EVIDENCE_RANK = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}
RESIDUAL_KEYS = ("q", "c", "e", "h", "a", "s", "j")
RESIDUAL_MIN, RESIDUAL_MAX = 0, 3
APPROVE_MAX_RESIDUAL = 1
DEFAULT_MAX_RESIDUAL = 2
PLACEHOLDER_VALUES = {"", "-", "...", "…", "tbd", "todo", "n/a", "na", "none"}

HEADING2 = re.compile(r"^##\s+(.+?)\s*$")
HEADING3 = re.compile(r"^###\s+(.+?)\s*$")
BULLET = re.compile(r"^[-*]\s+([A-Za-z][A-Za-z0-9 /_-]{0,40}?):\s*(.*)$")
FINDING_HEADER = re.compile(r"^F(\d+)\s*\[([A-Za-z-]+)\]\s*(.+?)\s*$")
LOCATION = re.compile(r"^(\S.*?):(\d+)(?:-(\d+))?$")
EVIDENCE = re.compile(r"^(E[0-3])\b\s*[-:]?\s*(.*)$")

TEMPLATE = """# Super Code Review

## Review Target

- Mode: gate
- Scope: <commit range, PR, or files under review>
- Decision variable: <merge, ship, keep behind a flag, revert, refactor now>
- Budget: <call sites to trace, commands allowed to run>

## Verdict

- Decision: request-changes
- Summary: <one sentence that names the decision and the reason>
- Condition: <required only when Decision is conditional>

## Residual

- r_q: 0
- r_c: 0
- r_e: 0
- r_h: 0
- r_a: 0
- r_s: 0
- r_j: 0

## Findings

### F1 [should-fix] path/to/file.py:120

- Behavior: <the wrong behavior this change introduces or preserves>
- Evidence: E1 <how the claim was established: trace, contract, or command>
- Trigger: <input, ordering, or state that reaches it>
- Fix: <smallest correct change>

## Uncovered

- <files, callers, or tests not examined, and why>

## Counterargument

- <where this verdict is most likely wrong, and what would refute it>

## Update Rule

- <later evidence that would change the decision>
"""


def normalise_heading(raw: str) -> str:
    text = re.sub(r"[`*_]", "", raw).strip().lower()
    text = re.sub(r"[:\s]+$", "", text)
    return re.sub(r"\s+", " ", text)


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = HEADING2.match(line)
        if match:
            current = normalise_heading(match.group(1))
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def bullets(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        match = BULLET.match(line.strip())
        if match:
            key = match.group(1).strip().lower()
            fields.setdefault(key, match.group(2).strip())
    return fields


def bullet_texts(lines: list[str]) -> list[str]:
    texts: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            texts.append(stripped[2:].strip())
    return texts


def is_meaningful(value: str, *, min_length: int = 1) -> bool:
    text = value.strip().strip("`")
    if text.lower() in PLACEHOLDER_VALUES:
        return False
    if len(text) < min_length:
        return False
    if text.startswith("<") and text.endswith(">"):
        return False
    return True


def parse_findings(lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        stripped = line.strip()
        heading = HEADING3.match(stripped)
        if heading:
            current = {"header": heading.group(1).strip(), "fields": {}}
            findings.append(current)
            continue
        if current is None:
            continue
        match = BULLET.match(stripped)
        if match:
            fields = current["fields"]
            assert isinstance(fields, dict)
            fields.setdefault(match.group(1).strip().lower(), match.group(2).strip())
    return findings


def parse_residuals(lines: list[str]) -> tuple[dict[str, int], list[str]]:
    residuals: dict[str, int] = {}
    problems: list[str] = []
    for line in lines:
        match = BULLET.match(line.strip())
        if not match:
            continue
        key = match.group(1).strip().lower()
        if not key.startswith("r_"):
            continue
        dimension = key[2:]
        if dimension not in RESIDUAL_KEYS:
            problems.append("unknown residual dimension: %s" % key)
            continue
        raw_value = re.sub(r"[^0-9-]", "", match.group(2).strip()[:3])
        if not raw_value:
            problems.append("residual %s has no numeric score" % key)
            continue
        residuals[dimension] = int(raw_value)
    return residuals, problems


def validate(text: str, *, max_residual: int = DEFAULT_MAX_RESIDUAL, max_phi: int | None = None) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def fail(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    def warn(code: str, message: str) -> None:
        warnings.append({"code": code, "message": message})

    if not text.strip():
        fail("empty-report", "the review is empty")
        return {"ok": False, "errors": errors, "warnings": warnings, "residuals": {}, "phi": None, "max_residual": None}

    sections = split_sections(text)
    for name in REQUIRED_SECTIONS:
        if name not in sections:
            fail("missing-section", "missing required section: %s" % name)

    target = bullets(sections.get("review target", []))
    mode = target.get("mode", "").strip().lower()
    if not mode:
        fail("missing-mode", "Review Target requires a Mode")
    elif mode not in MODES:
        fail("invalid-mode", "Mode must be one of %s, found %r" % (", ".join(MODES), mode))
    if not is_meaningful(target.get("scope", ""), min_length=3):
        fail("missing-scope", "Review Target requires a concrete Scope")
    if not is_meaningful(target.get("budget", ""), min_length=3):
        fail("missing-budget", "Review Target requires a probe Budget")

    verdict = bullets(sections.get("verdict", []))
    decision = verdict.get("decision", "").strip().lower()
    if not decision:
        fail("missing-decision", "Verdict requires a Decision")
    elif decision not in DECISIONS:
        fail("invalid-decision", "Decision must be one of %s, found %r" % (", ".join(DECISIONS), decision))
    if not is_meaningful(verdict.get("summary", ""), min_length=10):
        fail("missing-summary", "Verdict requires a substantive Summary")
    if decision == "conditional" and not is_meaningful(verdict.get("condition", ""), min_length=10):
        fail("conditional-without-condition", "Decision conditional requires a non-empty Condition")

    residual_lines = sections.get("residual", [])
    residuals, residual_problems = parse_residuals(residual_lines)
    for problem in residual_problems:
        fail("invalid-residual", problem)
    for dimension in RESIDUAL_KEYS:
        if dimension not in residuals:
            fail("missing-residual", "missing residual r_%s" % dimension)
            continue
        value = residuals[dimension]
        if value < RESIDUAL_MIN or value > RESIDUAL_MAX:
            fail("invalid-residual", "r_%s must be between 0 and 3, found %d" % (dimension, value))
        elif value == 3:
            fail("residual-critical", "r_%s is 3: the verdict must not be delivered yet" % dimension)
        elif value > max_residual:
            fail("residual-over-threshold", "r_%s is %d, above the threshold %d" % (dimension, value, max_residual))

    phi = sum(abs(value) for value in residuals.values()) if residuals else None
    if max_phi is not None and phi is not None and phi > max_phi:
        fail("phi-over-threshold", "aggregate residual %d exceeds the threshold %d" % (phi, max_phi))

    finding_lines = sections.get("findings", [])
    findings = parse_findings(finding_lines)
    if not findings:
        prose = " ".join(finding_lines).strip().lower()
        if not any(token in prose for token in ("no findings", "none", "no defects")):
            fail("missing-findings", "Findings is empty; either list findings or state that there are none")
    seen_ids: set[str] = set()
    severity_order = {name: index for index, name in enumerate(SEVERITIES)}
    previous_severity: int | None = None
    blocking_count = 0
    for finding in findings:
        header = str(finding["header"])
        fields = finding["fields"]
        assert isinstance(fields, dict)
        match = FINDING_HEADER.match(header)
        if not match:
            fail("bad-finding-header", "finding header must look like F1 [blocking] path/to/file.ext:42, found %r" % header)
            continue
        finding_id, severity_raw, location = match.group(1), match.group(2).lower(), match.group(3)
        if finding_id in seen_ids:
            warn("duplicate-finding-id", "finding id F%s is used more than once" % finding_id)
        seen_ids.add(finding_id)
        if severity_raw not in SEVERITIES:
            fail("invalid-severity", "F%s has unknown severity %r" % (finding_id, severity_raw))
            continue
        if previous_severity is not None and severity_order[severity_raw] < previous_severity:
            warn("unsorted-findings", "F%s ranks above an earlier finding; order by impact, not by discovery" % finding_id)
        previous_severity = severity_order[severity_raw]
        if severity_raw == "blocking":
            blocking_count += 1

        location_match = LOCATION.match(location.strip())
        if not location_match:
            fail("bad-location", "F%s location must be path:line, found %r" % (finding_id, location))

        for field_name in ("behavior", "evidence", "trigger", "fix"):
            if not is_meaningful(str(fields.get(field_name, "")), min_length=8):
                fail("missing-field", "F%s requires a substantive %s" % (finding_id, field_name.capitalize()))

        evidence_text = str(fields.get("evidence", "")).strip()
        evidence_match = EVIDENCE.match(evidence_text)
        if not evidence_match:
            fail("invalid-evidence-level", "F%s Evidence must start with E0, E1, E2, or E3" % finding_id)
            continue
        level = evidence_match.group(1)
        detail = evidence_match.group(2).strip()
        if not is_meaningful(detail, min_length=4):
            fail("missing-evidence", "F%s Evidence must state how the claim was established" % finding_id)
        if severity_raw == "blocking" and EVIDENCE_RANK[level] < EVIDENCE_RANK["E1"]:
            fail(
                "weak-evidence-for-blocking",
                "F%s is blocking but only %s; trace, prove, or reproduce it, or downgrade the severity" % (finding_id, level),
            )

    if decision == "approve" and blocking_count:
        fail("approve-with-blocking", "Decision approve conflicts with %d blocking finding(s)" % blocking_count)

    uncovered_texts = bullet_texts(sections.get("uncovered", []))
    if not uncovered_texts:
        fail("uncovered-empty", "Uncovered must list what was not examined, or state none with the reason")
    elif not any(is_meaningful(text, min_length=8) for text in uncovered_texts):
        fail("uncovered-empty", "Uncovered bullets are placeholders; name the skipped surface and why")

    if not any(is_meaningful(line.strip(" -*"), min_length=10) for line in sections.get("counterargument", [])):
        fail("counterargument-empty", "Counterargument must state where this verdict is most likely wrong")

    if not any(is_meaningful(line.strip(" -*"), min_length=10) for line in sections.get("update rule", [])):
        fail("update-rule-empty", "Update Rule must state which later evidence would change the decision")

    if decision == "approve" and residuals:
        over = [key for key, value in residuals.items() if value > APPROVE_MAX_RESIDUAL]
        if over:
            fail("residual-over-threshold", "Decision approve requires every residual at or below 1; over: %s" % ", ".join("r_" + key for key in over))

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "residuals": {"r_" + key: value for key, value in residuals.items()},
        "phi": phi,
        "max_residual": max(residuals.values()) if residuals else None,
    }


def read_report(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="review markdown file, or - for stdin")
    parser.add_argument("--template", action="store_true", help="print the review skeleton and exit")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--max-residual", type=int, default=DEFAULT_MAX_RESIDUAL, metavar="N", help="per-dimension residual threshold (default: 2)")
    parser.add_argument("--max-phi", type=int, default=None, metavar="N", help="optional aggregate residual threshold")
    args = parser.parse_args(argv)

    if args.template:
        sys.stdout.write(TEMPLATE)
        return 0
    if not args.path:
        parser.error("a review path is required unless --template is used")
    if not RESIDUAL_MIN <= args.max_residual <= RESIDUAL_MAX:
        parser.error("--max-residual must be between 0 and 3")

    try:
        text = read_report(args.path)
    except OSError as error:
        sys.stderr.write("cannot read review: %s\n" % error)
        return 2

    result = validate(text, max_residual=args.max_residual, max_phi=args.max_phi)

    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        status = "PASS" if result["ok"] else "FAIL"
        details = []
        if result["phi"] is not None:
            details.append("phi=%d" % result["phi"])
        if result["max_residual"] is not None:
            details.append("max_residual=%d" % result["max_residual"])
        suffix = " (%s)" % ", ".join(details) if details else ""
        sys.stdout.write("%s%s\n" % (status, suffix))
        for warning in result["warnings"]:
            sys.stdout.write("- warning [%s] %s\n" % (warning["code"], warning["message"]))
        for error in result["errors"]:
            sys.stdout.write("- error [%s] %s\n" % (error["code"], error["message"]))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
