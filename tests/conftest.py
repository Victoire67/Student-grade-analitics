"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from grade_analytics.models import Course, Grade, Student

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

CSV_HEADER = "student_id,name,major,year,course_code,course_name,credits,semester,score\n"


@pytest.fixture
def math101() -> Course:
    return Course("MATH101", "Calculus I", 4)


@pytest.fixture
def cs101() -> Course:
    return Course("CS101", "Intro to Programming", 3)


@pytest.fixture
def students(math101: Course, cs101: Course) -> List[Student]:
    """Four students across two majors, three semesters and two courses.

    Weighted averages: Ann 89.0, Bob 72.0, Cara 89.0 (tie with Ann), Dan none.
    """
    ann = Student("S1", "Ann Lee", "Mathematics", 2)
    ann.add_grade(Grade(math101, "2024-Spring", 92))
    ann.add_grade(Grade(cs101, "2024-Fall", 85))

    bob = Student("S2", "Bob Ray", "Computer Science", 1)
    bob.add_grade(Grade(cs101, "2023-Fall", 60))
    bob.add_grade(Grade(math101, "2024-Fall", 81))

    cara = Student("S3", "Cara Ng", "Computer Science", 2)
    cara.add_grade(Grade(math101, "2024-Spring", 89))
    cara.add_grade(Grade(cs101, "2024-Fall", 89))

    dan = Student("S4", "Dan Ito", "Mathematics", 1)
    return [ann, bob, cara, dan]


@pytest.fixture
def write_csv(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Factory writing CSV ``body`` (header added automatically) to a temp file."""

    def _write(body: str, name: str = "grades.csv", header: str = CSV_HEADER) -> Path:
        path = tmp_path / name
        path.write_text(header + body, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def sample_csv() -> Path:
    return DATA_DIR / "students.csv"


@pytest.fixture
def messy_csv() -> Path:
    return DATA_DIR / "messy_students.csv"
