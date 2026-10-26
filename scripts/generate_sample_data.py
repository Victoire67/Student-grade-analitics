"""Generate reproducible synthetic grade data.

Usage::

    python scripts/generate_sample_data.py                         # data/students.csv
    python scripts/generate_sample_data.py -n 50000 -o data/large_students.csv

Each student gets a latent "ability" and a small per-semester improvement so
the generated data shows realistic spread and upward trends.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple

FIRST_NAMES: Sequence[str] = (
    "Amara", "Ben", "Chloe", "Daniel", "Elena", "Femi", "Grace", "Hugo", "Ines", "Jamal",
    "Keza", "Liam", "Maya", "Noah", "Olivia", "Pablo", "Quinn", "Rosa", "Sami", "Tara",
    "Umar", "Vera", "Wei", "Ximena", "Yusuf", "Zoe",
)
LAST_NAMES: Sequence[str] = (
    "Mugisha", "Smith", "Chen", "Garcia", "Okafor", "Ivanova", "Kim", "Uwase", "Brown",
    "Silva", "Nguyen", "Haddad", "Martin", "Kowalski", "Tanaka", "Mensah",
)
MAJORS: Sequence[str] = (
    "Computer Science", "Mathematics", "Physics", "Economics", "Biology",
)
# code, name, credits
COURSES: Sequence[Tuple[str, str, int]] = (
    ("CS101", "Intro to Programming", 4),
    ("CS201", "Data Structures", 4),
    ("MATH101", "Calculus I", 4),
    ("MATH201", "Linear Algebra", 3),
    ("PHYS101", "Mechanics", 4),
    ("ECON101", "Microeconomics", 3),
    ("BIO101", "Cell Biology", 3),
    ("STAT201", "Probability & Statistics", 3),
)
SEMESTERS: Sequence[str] = ("2023-Fall", "2024-Spring", "2024-Fall", "2025-Spring")
HEADER: List[str] = [
    "student_id", "name", "major", "year", "course_code", "course_name",
    "credits", "semester", "score",
]


def generate_rows(n_students: int, seed: int) -> Iterator[List[str]]:
    """Yield CSV rows (excluding the header) for ``n_students`` students."""
    rng = random.Random(seed)
    for index in range(1, n_students + 1):
        student_id = f"S{index:04d}" if n_students < 10_000 else f"S{index:06d}"
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        major = rng.choice(MAJORS)
        year = rng.randint(1, 4)
        ability = rng.gauss(76, 9)
        growth = rng.uniform(-0.5, 2.5)
        taken = rng.sample(list(COURSES), k=rng.randint(3, 6))
        for term_index, (code, course_name, credits) in enumerate(taken):
            semester = SEMESTERS[term_index % len(SEMESTERS)]
            raw = ability + growth * (term_index % len(SEMESTERS)) + rng.gauss(0, 6)
            score = round(min(100.0, max(0.0, raw)))
            yield [
                student_id, name, major, str(year), code, course_name,
                str(credits), semester, str(score),
            ]


def write_csv(path: Path, n_students: int, seed: int) -> int:
    """Write the dataset to ``path``; returns the number of data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for row in generate_rows(n_students, seed):
            writer.writerow(row)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-n", "--students", type=int, default=40, help="number of students")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/students.csv"))
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    args = parser.parse_args()
    rows = write_csv(args.output, args.students, args.seed)
    print(f"Wrote {rows} records for {args.students} students to {args.output}")


if __name__ == "__main__":
    main()
