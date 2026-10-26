"""Tests for defaultdict/OrderedDict-based aggregations and rankings."""

from __future__ import annotations

from collections import OrderedDict
from typing import List

import pytest

from grade_analytics.aggregators import (
    courses_by_code,
    group_by,
    group_by_major,
    group_by_year,
    rank_students,
    scores_by_course,
    scores_by_semester,
    semester_averages,
    semester_trends,
    top_performers,
)
from grade_analytics.models import Student


class TestGrouping:
    def test_group_by_major(self, students: List[Student]) -> None:
        groups = group_by_major(students)
        assert type(groups) is dict  # defaultdict is not leaked to callers
        assert {k: [s.student_id for s in v] for k, v in groups.items()} == {
            "Mathematics": ["S1", "S4"],
            "Computer Science": ["S2", "S3"],
        }

    def test_group_by_year(self, students: List[Student]) -> None:
        groups = group_by_year(students)
        assert sorted(groups) == [1, 2]
        assert len(groups[1]) == 2

    def test_missing_key_is_absent_not_empty(self, students: List[Student]) -> None:
        assert "Physics" not in group_by_major(students)

    def test_custom_key(self, students: List[Student]) -> None:
        groups = group_by(students, lambda s: len(s.grades))
        assert len(groups[2]) == 3 and len(groups[0]) == 1

    def test_empty(self) -> None:
        assert group_by_major([]) == {}


class TestScoreAggregation:
    def test_scores_by_course(self, students: List[Student]) -> None:
        assert scores_by_course(students) == {
            "MATH101": [92, 81, 89],
            "CS101": [85, 60, 89],
        }

    def test_scores_by_semester(self, students: List[Student]) -> None:
        assert scores_by_semester(students)["2024-Fall"] == [85, 81, 89]

    def test_courses_by_code_sorted_and_shared(self, students: List[Student]) -> None:
        courses = courses_by_code(students)
        assert list(courses) == ["CS101", "MATH101"]
        assert courses["MATH101"].credits == 4


class TestSemesterOrdering:
    def test_semester_averages_is_chronological_ordereddict(
        self, students: List[Student]
    ) -> None:
        averages = semester_averages(students)
        assert isinstance(averages, OrderedDict)
        assert list(averages) == ["2023-Fall", "2024-Spring", "2024-Fall"]
        assert averages["2024-Spring"] == pytest.approx((92 + 89) / 2)

    def test_semester_trends_rolling(self, students: List[Student]) -> None:
        trends = semester_trends(students, window=2)
        assert [t["semester"] for t in trends] == ["2023-Fall", "2024-Spring", "2024-Fall"]
        assert trends[0]["rolling_average"] == 60
        assert trends[1]["rolling_average"] == pytest.approx((60 + 90.5) / 2)
        assert trends[2]["rolling_average"] == pytest.approx((90.5 + 85) / 2)


class TestRanking:
    def test_order_and_competition_ranks(self, students: List[Student]) -> None:
        ranking = rank_students(students)
        # Ann and Cara tie on weighted average (89.0) so share rank 1; Cara is
        # listed first because her unweighted average (89.0 vs 88.5) is higher.
        assert [r["student_id"] for r in ranking] == ["S3", "S1", "S2"]
        assert [r["rank"] for r in ranking] == [1, 1, 3]

    def test_excludes_students_without_grades(self, students: List[Student]) -> None:
        assert "S4" not in {r["student_id"] for r in rank_students(students)}

    def test_percentiles_and_letters(self, students: List[Student]) -> None:
        ranking = {r["student_id"]: r for r in rank_students(students)}
        assert ranking["S2"]["percentile"] == pytest.approx(100 * 0.5 / 3)
        assert ranking["S1"]["percentile"] == ranking["S3"]["percentile"]
        assert ranking["S2"]["letter"] == "C"

    def test_top_performers(self, students: List[Student]) -> None:
        assert [r["student_id"] for r in top_performers(students, n=1)] == ["S3"]
        assert top_performers(students, n=0) == []
        assert len(top_performers(students, n=50)) == 3
        with pytest.raises(ValueError):
            top_performers(students, n=-1)
