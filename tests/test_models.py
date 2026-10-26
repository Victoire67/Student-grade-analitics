"""Tests for dataclass / namedtuple models."""

from __future__ import annotations

import dataclasses
from typing import List

import pytest

from grade_analytics.models import (
    Course,
    Grade,
    GradeRecord,
    LetterGrade,
    Student,
    score_to_letter,
    semester_sort_key,
)


class TestScoreToLetter:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100, LetterGrade.A), (90, LetterGrade.A), (89.99, LetterGrade.B),
            (80, LetterGrade.B), (70, LetterGrade.C), (60, LetterGrade.D),
            (59.9, LetterGrade.F), (0, LetterGrade.F),
        ],
    )
    def test_boundaries(self, score: float, expected: LetterGrade) -> None:
        assert score_to_letter(score) is expected


class TestSemesterSortKey:
    def test_chronological_order(self) -> None:
        labels = ["2025-Spring", "2024-Fall", "2024-Summer", "2024-Spring", "2023-Fall"]
        assert sorted(labels, key=semester_sort_key) == list(reversed(labels))

    def test_case_insensitive(self) -> None:
        assert semester_sort_key("2024-FALL") == semester_sort_key("2024-fall")

    def test_unknown_season_sorts_last_in_year(self) -> None:
        assert semester_sort_key("2024-Winter") > semester_sort_key("2024-Fall")

    def test_invalid_year_raises(self) -> None:
        with pytest.raises(ValueError, match="YYYY-Season"):
            semester_sort_key("Fall-2024")


class TestGradeRecord:
    def test_is_immutable_namedtuple(self) -> None:
        record = GradeRecord("S1", "Ann", "Math", 1, "M1", "Calc", 4, "2024-Fall", 90.0)
        assert record.score == 90.0
        assert record._asdict()["course_code"] == "M1"
        with pytest.raises(AttributeError):
            record.score = 50.0  # type: ignore[misc]


class TestCourse:
    def test_frozen_and_hashable(self, math101: Course) -> None:
        assert {math101, Course("MATH101", "Calculus I", 4)} == {math101}
        with pytest.raises(dataclasses.FrozenInstanceError):
            math101.credits = 5  # type: ignore[misc]

    def test_uses_slots(self, math101: Course) -> None:
        assert not hasattr(math101, "__dict__")

    @pytest.mark.parametrize(("code", "credits"), [("", 3), ("X1", 0), ("X1", -2)])
    def test_validation(self, code: str, credits: int) -> None:
        with pytest.raises(ValueError):
            Course(code, "Name", credits)


class TestGrade:
    def test_letter_property(self, math101: Course) -> None:
        assert Grade(math101, "2024-Fall", 85).letter is LetterGrade.B

    @pytest.mark.parametrize("score", [-0.1, 100.1])
    def test_rejects_out_of_range(self, math101: Course, score: float) -> None:
        with pytest.raises(ValueError, match="between"):
            Grade(math101, "2024-Fall", score)

    def test_rejects_bad_semester(self, math101: Course) -> None:
        with pytest.raises(ValueError):
            Grade(math101, "autumn", 80)


class TestStudent:
    def test_defaults_are_independent(self) -> None:
        a = Student("A", "A", "M", 1)
        b = Student("B", "B", "M", 1)
        assert a.grades is not b.grades

    @pytest.mark.parametrize(("sid", "year"), [("", 1), ("S1", 0)])
    def test_validation(self, sid: str, year: int) -> None:
        with pytest.raises(ValueError):
            Student(sid, "Name", "Major", year)

    def test_averages(self, students: List[Student]) -> None:
        ann = students[0]
        assert ann.average == pytest.approx(88.5)
        # (92*4 + 85*3) / 7
        assert ann.weighted_average == pytest.approx(623 / 7)

    def test_averages_none_without_grades(self, students: List[Student]) -> None:
        dan = students[3]
        assert dan.average is None
        assert dan.weighted_average is None

    def test_grade_for(self, students: List[Student], math101: Course) -> None:
        ann = students[0]
        grade = ann.grade_for("MATH101")
        assert grade is not None and grade.score == 92
        assert ann.grade_for("MATH101", semester="2024-Fall") is None
        assert ann.grade_for("NOPE") is None

    def test_grade_for_returns_latest_attempt(self, math101: Course) -> None:
        s = Student("S", "S", "M", 1)
        s.add_grade(Grade(math101, "2024-Fall", 70))
        s.add_grade(Grade(math101, "2024-Spring", 50))
        latest = s.grade_for("MATH101")
        assert latest is not None and latest.semester == "2024-Fall"

    def test_scores_by_semester_is_chronological(self, students: List[Student]) -> None:
        bob = students[1]
        assert list(bob.scores_by_semester()) == ["2023-Fall", "2024-Fall"]
