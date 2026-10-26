"""Command-line interface: ``grade-analytics INPUT.csv [-o REPORT.json]``."""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .file_io import (
    DataLoadError,
    InvalidRecordError,
    ReportWriteError,
    load_students,
    write_json_report,
)
from .report import build_report, iter_ranking_lines
from .schemas import AnalyticsReport, GroupSummary
from .visualization import bar_chart, trend_chart

__all__ = ["build_parser", "main", "render_summary"]

DEFAULT_OUTPUT = Path("reports") / "report.json"


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="grade-analytics",
        description="Analyse student grades from a CSV file and write a JSON report.",
    )
    parser.add_argument("input", type=Path, help="CSV file with student grade records")
    parser.add_argument(
        "-o", "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"JSON report path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--top", type=int, default=5, help="number of top performers (default: 5)")
    parser.add_argument(
        "--window", type=int, default=3,
        help="rolling-average window in semesters (default: 3)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="fail on the first invalid row instead of skipping it",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress the terminal summary")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _group_line(label: str, group: GroupSummary) -> str:
    count = group["student_count"]
    noun = "student" if count == 1 else "students"
    return f"   {label:<22} {group['average']:>6}  ({count} {noun}, top: {group['top_student']})"


def render_summary(report: AnalyticsReport, top_n: int) -> str:
    """Human-readable summary of a report for terminal display."""
    meta = report["metadata"]
    overall = report["overall_statistics"]
    lines: List[str] = [
        "=" * 72,
        " STUDENT GRADE ANALYTICS REPORT",
        "=" * 72,
        f" Source   : {meta['source_file']}",
        f" Students : {meta['student_count']}   Courses: {meta['course_count']}"
        f"   Records: {meta['record_count']}",
        f" Mean {overall['mean']}  Median {overall['median']}  Std dev {overall['std_dev']}"
        f"  Mode {overall['mode']}",
        "",
        " Grade distribution",
        *("   " + line for line in bar_chart(report["grade_distribution"])),
        "",
        f" Top {top_n} performers",
        *("   " + line for line in iter_ranking_lines(report["top_performers"])),
        "",
        " Average by major",
        *(_group_line(major, group) for major, group in report["by_major"].items()),
        "",
        " Semester trends",
        *("   " + line for line in trend_chart(report["semester_trends"])),
        "=" * 72,
    ]
    return "\n".join(lines)


def _ensure_utf8_stdout() -> None:
    """Avoid UnicodeEncodeError for chart glyphs on legacy (e.g. cp1252) consoles."""
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if encoding.replace("-", "") != "utf8" and isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit code (0 success, 1 failure)."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.ERROR if args.quiet else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    _ensure_utf8_stdout()

    if args.top < 0 or args.window < 1:
        print("error: --top must be >= 0 and --window must be >= 1", file=sys.stderr)
        return 1

    errors: List[str] = []
    try:
        students = load_students(args.input, strict=args.strict, errors=errors)
    except (DataLoadError, InvalidRecordError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not students:
        print(f"error: no valid records found in {args.input}", file=sys.stderr)
        return 1

    report = build_report(
        students, source_file=args.input.name, top_n=args.top, trend_window=args.window
    )
    try:
        out_path = write_json_report(report, args.output)
    except ReportWriteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(render_summary(report, args.top))
        if errors:
            print(f" Skipped {len(errors)} invalid row(s); see warnings above.")
        print(f" Report written to {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
