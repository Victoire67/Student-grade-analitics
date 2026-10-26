"""``TypedDict`` definitions describing the JSON report structure.

These types document the exact shape of the generated report and let mypy
verify that the report builder produces every required key.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

__all__ = [
    "AnalyticsReport",
    "CourseSummary",
    "GroupSummary",
    "ReportMetadata",
    "ScoreStatistics",
    "StudentRanking",
    "TrendPoint",
]


class ReportMetadata(TypedDict):
    """Provenance information for a report."""

    generated_at: str
    source_file: str
    tool_version: str
    student_count: int
    course_count: int
    record_count: int


class ScoreStatistics(TypedDict):
    """Descriptive statistics for a collection of scores."""

    count: int
    mean: Optional[float]
    median: Optional[float]
    mode: List[float]
    std_dev: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]


class StudentRanking(TypedDict):
    """A student's position in the overall ranking."""

    rank: int
    student_id: str
    name: str
    major: str
    year: int
    average: float
    weighted_average: float
    percentile: float
    letter: str


class GroupSummary(TypedDict):
    """Aggregate statistics for a group of students (by major or year)."""

    student_count: int
    average: Optional[float]
    top_student: Optional[str]


class CourseSummary(TypedDict):
    """Aggregate statistics for a single course."""

    course_name: str
    credits: int
    enrollment: int
    statistics: ScoreStatistics
    grade_distribution: Dict[str, int]


class TrendPoint(TypedDict):
    """Cohort average for one semester, with a rolling average."""

    semester: str
    average: float
    rolling_average: float


class AnalyticsReport(TypedDict):
    """Top-level JSON report document."""

    metadata: ReportMetadata
    overall_statistics: ScoreStatistics
    grade_distribution: Dict[str, int]
    top_performers: List[StudentRanking]
    rankings: List[StudentRanking]
    by_major: Dict[str, GroupSummary]
    by_year: Dict[str, GroupSummary]
    courses: Dict[str, CourseSummary]
    semester_trends: List[TrendPoint]
