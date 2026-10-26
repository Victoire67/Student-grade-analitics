"""Core data models for the grade analytics tool.

Design notes
------------
* ``GradeRecord`` is a ``namedtuple`` representing one *raw* CSV row. Named
  tuples are immutable and carry no per-instance ``__dict__``, which makes them
  a cheap container while streaming large files.
* ``Course``, ``Grade`` and ``Student`` are ``dataclasses`` using
  ``slots=True`` to keep the memory footprint low while still offering
  defaults, validation in ``__post_init__`` and rich methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from statistics import fmean
from typing import Dict, List, NamedTuple, Optional, Tuple

__all__ = [
    "Course",
    "Grade",
    "GradeRecord",
    "LetterGrade",
    "Student",
    "score_to_letter",
    "semester_sort_key",
]

MIN_SCORE = 0.0
MAX_SCORE = 100.0

_SEASON_ORDER: Dict[str, int] = {"spring": 1, "summer": 2, "fall": 3}


class LetterGrade(str, Enum):
    """Letter grades on a standard 10-point scale."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


# Lower bound (inclusive) for each letter, checked from highest to lowest.
_LETTER_THRESHOLDS: Tuple[Tuple[float, LetterGrade], ...] = (
    (90.0, LetterGrade.A),
    (80.0, LetterGrade.B),
    (70.0, LetterGrade.C),
    (60.0, LetterGrade.D),
)


def score_to_letter(score: float) -> LetterGrade:
    """Convert a numeric score (0-100) to a :class:`LetterGrade`.

    >>> score_to_letter(91.5)
    <LetterGrade.A: 'A'>
    >>> score_to_letter(59.9).value
    'F'
    """
    for threshold, letter in _LETTER_THRESHOLDS:
        if score >= threshold:
            return letter
    return LetterGrade.F


def semester_sort_key(semester: str) -> Tuple[int, int]:
    """Return a sortable key for semester labels such as ``"2024-Fall"``.

    Unknown seasons sort after known ones within the same year.

    >>> sorted(["2024-Fall", "2024-Spring", "2023-Fall"], key=semester_sort_key)
    ['2023-Fall', '2024-Spring', '2024-Fall']
    """
    year_part, _, season_part = semester.partition("-")
    try:
        year = int(year_part)
    except ValueError as exc:
        raise ValueError(
            f"Invalid semester {semester!r}; expected 'YYYY-Season'"
        ) from exc
    return year, _SEASON_ORDER.get(season_part.strip().lower(), 99)


class GradeRecord(NamedTuple):
    """One flat, immutable row of the input CSV."""

    student_id: str
    name: str
    major: str
    year: int
    course_code: str
    course_name: str
    credits: int
    semester: str
    score: float


@dataclass(frozen=True, slots=True)
class Course:
    """A course offering. Frozen so it can be used as a dict key / set member."""

    code: str
    name: str
    credits: int = 3

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("Course code must not be empty")
        if self.credits <= 0:
            raise ValueError(f"Course credits must be positive, got {self.credits}")


@dataclass(frozen=True, slots=True)
class Grade:
    """A single score a student earned in a course during a semester."""

    course: Course
    semester: str
    score: float

    def __post_init__(self) -> None:
        if not MIN_SCORE <= self.score <= MAX_SCORE:
            raise ValueError(
                f"Score must be between {MIN_SCORE} and {MAX_SCORE}, got {self.score}"
            )
        # Validate the semester label eagerly so bad data fails at load time.
        semester_sort_key(self.semester)

    @property
    def letter(self) -> LetterGrade:
        """Letter grade corresponding to :attr:`score`."""
        return score_to_letter(self.score)


@dataclass(slots=True)
class Student:
    """A student and every grade they have earned."""

    student_id: str
    name: str
    major: str
    year: int
    grades: List[Grade] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.student_id:
            raise ValueError("student_id must not be empty")
        if self.year < 1:
            raise ValueError(f"year must be >= 1, got {self.year}")

    def add_grade(self, grade: Grade) -> None:
        """Attach a grade to this student."""
        self.grades.append(grade)

    @property
    def scores(self) -> List[float]:
        """All raw scores in insertion order."""
        return [grade.score for grade in self.grades]

    @property
    def average(self) -> Optional[float]:
        """Unweighted mean score, or ``None`` when the student has no grades."""
        return fmean(self.scores) if self.grades else None

    @property
    def weighted_average(self) -> Optional[float]:
        """Credit-weighted mean score, or ``None`` when there are no grades."""
        if not self.grades:
            return None
        total_credits = sum(g.course.credits for g in self.grades)
        return sum(g.score * g.course.credits for g in self.grades) / total_credits

    def grade_for(self, course_code: str, semester: Optional[str] = None) -> Optional[Grade]:
        """Return the most recent grade for ``course_code`` (optionally in a semester)."""
        matches = [
            g
            for g in self.grades
            if g.course.code == course_code and (semester is None or g.semester == semester)
        ]
        if not matches:
            return None
        return max(matches, key=lambda g: semester_sort_key(g.semester))

    def scores_by_semester(self) -> Dict[str, List[float]]:
        """Scores grouped by semester, with semesters in chronological order."""
        grouped: Dict[str, List[float]] = {}
        for grade in sorted(self.grades, key=lambda g: semester_sort_key(g.semester)):
            grouped.setdefault(grade.semester, []).append(grade.score)
        return grouped
