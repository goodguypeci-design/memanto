"""Validate that the generated goose OKF bundle imports through Memanto."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


sys.path.insert(0, str(repo_root()))

from memanto.cli.migrate.mappers import map_okf  # noqa: E402
from memanto.cli.migrate.okf_loader import load_okf_bundle  # noqa: E402

QUESTIONS = {
    "Which agent generated the migrated sessions?": ["goose"],
    "What deployment preference was preserved?": ["npm test", "deploying"],
    "Which locking decision should survive the migration?": ["postgres", "redis"],
}


def check_recall(rows: list[dict], needle_groups: dict[str, list[str]]) -> list[dict]:
    haystack = "\n".join(
        f"{row.get('title', '')}\n{row.get('content', '')}" for row in rows
    ).lower()
    report: list[dict] = []
    for question, needles in needle_groups.items():
        missing = [needle for needle in needles if needle.lower() not in haystack]
        report.append(
            {
                "question": question,
                "expected_terms": needles,
                "passed": not missing,
                "missing_terms": missing,
            }
        )
    return report


def validate(bundle: Path) -> dict:
    export = load_okf_bundle(bundle)
    rows = map_okf(export)
    type_counts = Counter(row.get("type") or "auto" for row in rows)
    checks = check_recall(rows, QUESTIONS)
    return {
        "bundle": str(bundle),
        "loaded_okf_entries": len(export["memories"]),
        "mapped_memanto_rows": len(rows),
        "type_counts": dict(sorted(type_counts.items())),
        "recall_checks": checks,
        "passed": bool(rows) and all(item["passed"] for item in checks),
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# Goose OKF round-trip validation",
        "",
        f"- OKF entries loaded: {report['loaded_okf_entries']}",
        f"- Memanto rows mapped: {report['mapped_memanto_rows']}",
        f"- Passed: {report['passed']}",
        "",
        "## Type counts",
        "",
    ]
    for memory_type, count in report["type_counts"].items():
        lines.append(f"- {memory_type}: {count}")
    lines.extend(["", "## Recall parity checks", ""])
    for check in report["recall_checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        terms = ", ".join(check["expected_terms"])
        lines.append(f"- {mark}: {check['question']} — expected `{terms}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--report", type=Path, help="write markdown validation report")
    args = parser.parse_args()

    result = validate(args.bundle)
    if args.report:
        write_markdown(result, args.report)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
