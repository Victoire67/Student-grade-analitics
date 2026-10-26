"""Assemble the :class:`~grade_analytics.schemas.AnalyticsReport` document."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Iterable, List, Optional, overload

from . import __version__
from .aggregators import (
    courses_by_code,
    group_by_major,
    group_by_year,
    rank_students,
    scores_by_course,
    semester_trends,
)
from .models import Student
from .schemas import (
    AnalyticsReport,
    CourseSummary,
    GroupSummary,
    ReportMetadata,
    ScoreStatistics,
    StudentRanking,
    TrendPoint,
)
from .stats import describe, grade_distribution, mean

__all__ = ["build_report"]

DECIMALS = 2


@overload
def _round(value: float) -> float: ...
@overload
def _round(value: None) -> None: ...
def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, DECIMALS)


def _round_stats(stats: ScoreStatistics) -> ScoreStatistics:
    return ScoreStatistics(
        count=stats["count"],
        mean=_round(stats["mean"]),
        median=_round(stats["median"]),
        mode=[round(v, DECIMALS) for v in stats["mode"]],
        std_dev=_round(stats["std_dev"]),
        minimum=_round(stats["minimum"]),
        maximum=_round(stats["maximum"]),
    )


def _round_ranking(entry: StudentRanking) -> StudentRanking:
    rounded = entry.copy()
    rounded["average"] = _round(entry["average"])
    rounded["weighted_average"] = _round(entry["weighted_average"])
    rounded["percentile"] = _round(entry["percentile"])
    return rounded


def _summarise_group(members: List[Student]) -> GroupSummary:
    ranked = rank_students(members)
    averages = [r["weighted_average"] for r in ranked]
    return GroupSummary(
        student_count=len(members),
        average=_round(mean(averages)),
        top_student=ranked[0]["name"] if ranked else None,
    )


def build_report(
    students: List[Student],
    *,
    source_file: str = "<memory>",
    top_n: int = 5,
    trend_window: int = 3,
    generated_at: Optional[datetime] = None,
) -> AnalyticsReport:
    """Compute every analytic and return a JSON-serialisable report.

    Group and course sections are ``OrderedDict`` instances with sorted keys so
    the JSON output is deterministic and easy to diff between runs.

    Args:
        students: students to analyse.
        source_file: name recorded in the report metadata.
        top_n: number of entries in ``top_performers``.
        trend_window: rolling-average window (in semesters) for trends.
        generated_at: timestamp override, mainly for reproducible tests.
    """
    all_scores: List[float] = [g.score for s in students for g in s.grades]
    course_scores = scores_by_course(students)
    courses = courses_by_code(students)
    rankings = [_round_ranking(r) for r in rank_students(students)]

    by_major: OrderedDict[str, GroupSummary] = OrderedDict(
        (major, _summarise_group(members))
        for major, members in sorted(group_by_major(students).items())
    )
    by_year: OrderedDict[str, GroupSummary] = OrderedDict(
        (f"Year {year}", _summarise_group(members))
        for year, members in sorted(group_by_year(students).items())
    )
    course_section: OrderedDict[str, CourseSummary] = OrderedDict(
        (
            code,
            CourseSummary(
                course_name=course.name,
                credits=course.credits,
                enrollment=len(course_scores[code]),
                statistics=_round_stats(describe(course_scores[code])),
                grade_distribution=dict(grade_distribution(course_scores[code])),
            ),
        )
        for code, course in courses.items()
    )
    trends: List[TrendPoint] = [
        TrendPoint(
            semester=t["semester"],
            average=_round(t["average"]),
            rolling_average=_round(t["rolling_average"]),
        )
        for t in semester_trends(students, window=trend_window)
    ]

    timestamp = generated_at or datetime.now(timezone.utc)
    metadata = ReportMetadata(
        generated_at=timestamp.isoformat(timespec="seconds"),
        source_file=source_file,
        tool_version=__version__,
        student_count=len(students),
        course_count=len(courses),
        record_count=len(all_scores),
    )

    return AnalyticsReport(
        metadata=metadata,
        overall_statistics=_round_stats(describe(all_scores)),
        grade_distribution=dict(grade_distribution(all_scores)),
        top_performers=rankings[: max(top_n, 0)],
        rankings=rankings,
        by_major=by_major,
        by_year=by_year,
        courses=course_section,
        semester_trends=trends,
    )


def iter_ranking_lines(rankings: Iterable[StudentRanking]) -> Iterable[str]:
    """Yield fixed-width text lines for a ranking table."""
    yield f"{'Rank':>4}  {'ID':<6} {'Name':<20} {'Major':<18} {'W.Avg':>6} {'Pctl':>6}"
    for r in rankings:
        yield (
            f"{r['rank']:>4}  {r['student_id']:<6} {r['name'][:20]:<20} "
            f"{r['major'][:18]:<18} {r['weighted_average']:>6.2f} {r['percentile']:>6.1f}"
        )
