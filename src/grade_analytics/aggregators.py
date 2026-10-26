"""Collection-based aggregations over :class:`~grade_analytics.models.Student`.

* ``defaultdict(list)`` groups students and scores without key checks.
* ``OrderedDict`` keeps semester averages in chronological order.
* :class:`~grade_analytics.stats.RollingAverage` (a ``deque``) smooths trends.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from typing import Callable, DefaultDict, Dict, Hashable, List, Optional, TypeVar

from .models import Course, Student, score_to_letter, semester_sort_key
from .schemas import StudentRanking, TrendPoint
from .stats import RollingAverage, mean, percentile_ranks

__all__ = [
    "courses_by_code",
    "group_by",
    "group_by_major",
    "group_by_year",
    "rank_students",
    "scores_by_course",
    "scores_by_semester",
    "semester_averages",
    "semester_trends",
    "top_performers",
]

K = TypeVar("K", bound=Hashable)

# Rankings compare averages at this precision so float noise can't split ties.
_RANK_PRECISION = 4


def group_by(students: List[Student], key: Callable[[Student], K]) -> Dict[K, List[Student]]:
    """Group students by an arbitrary key function using ``defaultdict``."""
    groups: DefaultDict[K, List[Student]] = defaultdict(list)
    for student in students:
        groups[key(student)].append(student)
    return dict(groups)


def group_by_major(students: List[Student]) -> Dict[str, List[Student]]:
    """Students grouped by major."""
    return group_by(students, lambda s: s.major)


def group_by_year(students: List[Student]) -> Dict[int, List[Student]]:
    """Students grouped by year of study."""
    return group_by(students, lambda s: s.year)


def scores_by_course(students: List[Student]) -> Dict[str, List[float]]:
    """Every score recorded for each course code."""
    scores: DefaultDict[str, List[float]] = defaultdict(list)
    for student in students:
        for grade in student.grades:
            scores[grade.course.code].append(grade.score)
    return dict(scores)


def courses_by_code(students: List[Student]) -> Dict[str, Course]:
    """Map course codes to their :class:`Course`, sorted by code."""
    found: Dict[str, Course] = {}
    for student in students:
        for grade in student.grades:
            found.setdefault(grade.course.code, grade.course)
    return dict(sorted(found.items()))


def scores_by_semester(students: List[Student]) -> Dict[str, List[float]]:
    """Every score recorded in each semester (unordered)."""
    scores: DefaultDict[str, List[float]] = defaultdict(list)
    for student in students:
        for grade in student.grades:
            scores[grade.semester].append(grade.score)
    return dict(scores)


def semester_averages(students: List[Student]) -> "OrderedDict[str, float]":
    """Cohort average per semester, in chronological order."""
    by_semester = scores_by_semester(students)
    ordered: OrderedDict[str, float] = OrderedDict()
    for semester in sorted(by_semester, key=semester_sort_key):
        avg = mean(by_semester[semester])
        if avg is not None:
            ordered[semester] = avg
    return ordered


def semester_trends(students: List[Student], window: int = 3) -> List[TrendPoint]:
    """Semester averages with a rolling average over the last ``window`` terms."""
    roller = RollingAverage(window)
    return [
        TrendPoint(semester=semester, average=avg, rolling_average=roller.add(avg))
        for semester, avg in semester_averages(students).items()
    ]


def rank_students(students: List[Student]) -> List[StudentRanking]:
    """Rank students by credit-weighted average (highest first).

    Uses standard competition ranking ("1224"): tied students share a rank
    and the next rank skips accordingly. Ties are broken for display order by
    unweighted average, then student id. Students with no grades are omitted.
    """
    graded: List[tuple[Student, float, float]] = []
    for student in students:
        weighted: Optional[float] = student.weighted_average
        average: Optional[float] = student.average
        if weighted is not None and average is not None:
            graded.append((student, weighted, average))

    graded.sort(key=lambda item: (-item[1], -item[2], item[0].student_id))
    percentiles = percentile_ranks([weighted for _, weighted, _ in graded])

    rankings: List[StudentRanking] = []
    previous: Optional[float] = None
    rank = 0
    for position, ((student, weighted, average), pct) in enumerate(
        zip(graded, percentiles), start=1
    ):
        rounded = round(weighted, _RANK_PRECISION)
        if rounded != previous:
            rank = position
            previous = rounded
        rankings.append(
            StudentRanking(
                rank=rank,
                student_id=student.student_id,
                name=student.name,
                major=student.major,
                year=student.year,
                average=average,
                weighted_average=weighted,
                percentile=pct,
                letter=score_to_letter(weighted).value,
            )
        )
    return rankings


def top_performers(students: List[Student], n: int = 5) -> List[StudentRanking]:
    """The ``n`` highest-ranked students."""
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    return rank_students(students)[:n]
