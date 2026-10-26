"""CSV input and JSON output using context managers and ``pathlib``.

Reading is generator-based: :func:`iter_records` yields one
:class:`~grade_analytics.models.GradeRecord` at a time, so arbitrarily large
files are processed in constant memory until they are aggregated.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Union

from .models import Course, Grade, GradeRecord, Student

__all__ = [
    "DataLoadError",
    "InvalidRecordError",
    "PathLike",
    "REQUIRED_COLUMNS",
    "ReportWriteError",
    "iter_records",
    "load_students",
    "parse_row",
    "read_json",
    "write_json_report",
]

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

REQUIRED_COLUMNS: tuple[str, ...] = GradeRecord._fields


class DataLoadError(Exception):
    """Raised when an input file cannot be opened or is structurally invalid."""


class InvalidRecordError(ValueError):
    """Raised when a single CSV row cannot be parsed."""


class ReportWriteError(Exception):
    """Raised when a report cannot be written to disk."""


def _to_path(path: PathLike) -> Path:
    return path if isinstance(path, Path) else Path(path)


def parse_row(row: Mapping[str, Optional[str]], line_number: int = 0) -> GradeRecord:
    """Convert a raw ``csv.DictReader`` row into a typed :class:`GradeRecord`.

    Raises:
        InvalidRecordError: if a field is missing, empty or has the wrong type.
    """
    try:
        values: Dict[str, str] = {}
        for column in REQUIRED_COLUMNS:
            raw = row.get(column)
            if raw is None or not raw.strip():
                raise InvalidRecordError(f"line {line_number}: missing value for {column!r}")
            values[column] = raw.strip()
        return GradeRecord(
            student_id=values["student_id"],
            name=values["name"],
            major=values["major"],
            year=int(values["year"]),
            course_code=values["course_code"],
            course_name=values["course_name"],
            credits=int(values["credits"]),
            semester=values["semester"],
            score=float(values["score"]),
        )
    except ValueError as exc:
        if isinstance(exc, InvalidRecordError):
            raise
        raise InvalidRecordError(f"line {line_number}: {exc}") from exc


def iter_records(
    path: PathLike,
    *,
    strict: bool = False,
    errors: Optional[List[str]] = None,
) -> Iterator[GradeRecord]:
    """Lazily yield :class:`GradeRecord` rows from a CSV file.

    Args:
        path: CSV file location.
        strict: when ``True`` the first invalid row raises
            :class:`InvalidRecordError`; otherwise invalid rows are skipped.
        errors: optional list that receives a message for every skipped row.

    Raises:
        DataLoadError: if the file is missing, unreadable, not UTF-8 or lacks
            required columns.
    """
    csv_path = _to_path(path)
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = set(reader.fieldnames or ())
            missing = [c for c in REQUIRED_COLUMNS if c not in header]
            if missing:
                raise DataLoadError(
                    f"{csv_path}: missing required column(s): {', '.join(missing)}"
                )
            # Data starts on line 2 (line 1 is the header).
            for line_number, row in enumerate(reader, start=2):
                try:
                    yield parse_row(row, line_number)
                except InvalidRecordError as exc:
                    if strict:
                        raise
                    message = f"{csv_path.name}: skipped {exc}"
                    logger.warning(message)
                    if errors is not None:
                        errors.append(message)
    except FileNotFoundError as exc:
        raise DataLoadError(f"Input file not found: {csv_path}") from exc
    except IsADirectoryError as exc:
        raise DataLoadError(f"Expected a file but got a directory: {csv_path}") from exc
    except PermissionError as exc:
        raise DataLoadError(f"Permission denied reading: {csv_path}") from exc
    except UnicodeDecodeError as exc:
        raise DataLoadError(f"{csv_path} is not valid UTF-8 text") from exc


def load_students(
    source: Union[PathLike, Iterable[GradeRecord]],
    *,
    strict: bool = False,
    errors: Optional[List[str]] = None,
) -> List[Student]:
    """Build :class:`Student` objects from a CSV path or an iterable of records.

    Accepting either a path or pre-parsed records (``Union`` input) makes the
    function easy to test and reuse with other data sources.

    Course objects are de-duplicated so every grade for the same course shares
    a single :class:`Course` instance. Students are returned in first-seen
    order.
    """
    records: Iterable[GradeRecord] = (
        iter_records(source, strict=strict, errors=errors)
        if isinstance(source, (str, Path))
        else source
    )

    students: Dict[str, Student] = {}
    courses: Dict[str, Course] = {}
    for record in records:
        course = courses.get(record.course_code)
        if course is None:
            course = Course(record.course_code, record.course_name, record.credits)
            courses[record.course_code] = course

        student = students.get(record.student_id)
        if student is None:
            student = Student(record.student_id, record.name, record.major, record.year)
            students[record.student_id] = student

        try:
            student.add_grade(Grade(course, record.semester, record.score))
        except ValueError as exc:
            if strict:
                raise InvalidRecordError(str(exc)) from exc
            message = f"skipped grade for {record.student_id}/{record.course_code}: {exc}"
            logger.warning(message)
            if errors is not None:
                errors.append(message)
    return list(students.values())


def write_json_report(report: Mapping[str, Any], path: PathLike, *, indent: int = 2) -> Path:
    """Write ``report`` as pretty-printed JSON, creating parent folders.

    Returns:
        The resolved output path.

    Raises:
        ReportWriteError: if the file cannot be written.
    """
    out_path = _to_path(path)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=indent, ensure_ascii=False)
            handle.write("\n")
    except PermissionError as exc:
        raise ReportWriteError(f"Permission denied writing: {out_path}") from exc
    except IsADirectoryError as exc:
        raise ReportWriteError(f"Output path is a directory: {out_path}") from exc
    except OSError as exc:
        raise ReportWriteError(f"Could not write report to {out_path}: {exc}") from exc
    return out_path.resolve()


def read_json(path: PathLike) -> Any:
    """Read a JSON document (e.g. a previously generated report)."""
    json_path = _to_path(path)
    try:
        with json_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise DataLoadError(f"JSON file not found: {json_path}") from exc
    except PermissionError as exc:
        raise DataLoadError(f"Permission denied reading: {json_path}") from exc
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"{json_path} is not valid JSON: {exc}") from exc
