"""Tests for CSV reading, JSON writing and error handling."""

from __future__ import annotations

import types
from pathlib import Path
from typing import Any, Callable, List

import pytest

from grade_analytics.file_io import (
    DataLoadError,
    InvalidRecordError,
    ReportWriteError,
    iter_records,
    load_students,
    parse_row,
    read_json,
    write_json_report,
)
from grade_analytics.models import GradeRecord

WriteCsv = Callable[..., Path]

GOOD_ROWS = (
    "S1,Ann Lee,Math,2,MATH101,Calculus,4,2024-Spring,92\n"
    "S1,Ann Lee,Math,2,CS101,Intro CS,3,2024-Fall,85\n"
    "S2,Bob Ray,CS,1,CS101,Intro CS,3,2024-Fall,78.5\n"
)


VALID_ROW = dict(
    student_id="S1", name=" Ann ", major="Math", year="2", course_code="M1",
    course_name="Calc", credits="4", semester="2024-Fall", score="91.5",
)


class TestParseRow:
    def test_types_are_converted(self) -> None:
        record = parse_row(VALID_ROW)
        assert record == GradeRecord("S1", "Ann", "Math", 2, "M1", "Calc", 4, "2024-Fall", 91.5)

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_missing_value(self, blank: str) -> None:
        with pytest.raises(InvalidRecordError, match="line 7: missing value for 'score'"):
            parse_row(VALID_ROW | {"score": blank}, line_number=7)

    def test_bad_number(self) -> None:
        with pytest.raises(InvalidRecordError, match="line 3"):
            parse_row(VALID_ROW | {"credits": "four"}, line_number=3)


class TestIterRecords:
    def test_is_lazy_generator(self, write_csv: WriteCsv) -> None:
        records = iter_records(write_csv(GOOD_ROWS))
        assert isinstance(records, types.GeneratorType)
        first = next(records)
        assert first.student_id == "S1" and first.score == 92.0
        assert len(list(records)) == 2

    def test_handles_utf8_bom(self, tmp_path: Path) -> None:
        path = tmp_path / "bom.csv"
        header = "student_id,name,major,year,course_code,course_name,credits,semester,score\n"
        path.write_text(header + GOOD_ROWS, encoding="utf-8-sig")
        assert len(list(iter_records(path))) == 3

    def test_accepts_str_path(self, write_csv: WriteCsv) -> None:
        assert len(list(iter_records(str(write_csv(GOOD_ROWS))))) == 3

    def test_lenient_skips_and_reports(self, write_csv: WriteCsv) -> None:
        path = write_csv(GOOD_ROWS + "S3,Cy,CS,1,CS101,Intro CS,3,2024-Fall,abc\n")
        errors: List[str] = []
        assert len(list(iter_records(path, errors=errors))) == 3
        assert len(errors) == 1 and "line 5" in errors[0]

    def test_strict_raises(self, write_csv: WriteCsv) -> None:
        path = write_csv("S3,Cy,CS,one,CS101,Intro CS,3,2024-Fall,80\n")
        with pytest.raises(InvalidRecordError):
            list(iter_records(path, strict=True))

    def test_missing_columns(self, write_csv: WriteCsv) -> None:
        path = write_csv("S1,Ann\n", header="student_id,name\n")
        with pytest.raises(DataLoadError, match="missing required column"):
            list(iter_records(path))

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(DataLoadError, match="not found"):
            list(iter_records(tmp_path / "missing.csv"))

    def test_directory_instead_of_file(self, tmp_path: Path) -> None:
        # Windows raises PermissionError for directories; POSIX raises
        # IsADirectoryError. Both must surface as DataLoadError.
        with pytest.raises(DataLoadError):
            list(iter_records(tmp_path))

    def test_permission_denied(
        self, write_csv: WriteCsv, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = write_csv(GOOD_ROWS)

        def deny(*_: Any, **__: Any) -> None:
            raise PermissionError("denied")

        monkeypatch.setattr(Path, "open", deny)
        with pytest.raises(DataLoadError, match="Permission denied"):
            list(iter_records(path))

    def test_non_utf8(self, tmp_path: Path) -> None:
        path = tmp_path / "latin1.csv"
        path.write_bytes(b"student_id,name\n\xff\xfe\xfa\n")
        with pytest.raises(DataLoadError, match="UTF-8"):
            list(iter_records(path))


class TestLoadStudents:
    def test_from_path(self, write_csv: WriteCsv) -> None:
        students = load_students(write_csv(GOOD_ROWS))
        assert [s.student_id for s in students] == ["S1", "S2"]
        assert len(students[0].grades) == 2

    def test_from_iterable_of_records(self) -> None:
        records = [
            GradeRecord("S1", "Ann", "Math", 1, "M1", "Calc", 4, "2024-Fall", 90.0),
            GradeRecord("S2", "Bob", "Math", 1, "M1", "Calc", 4, "2024-Fall", 80.0),
        ]
        students = load_students(records)
        assert students[0].grades[0].course is students[1].grades[0].course

    def test_invalid_grade_values_skipped(self, write_csv: WriteCsv) -> None:
        path = write_csv(GOOD_ROWS + "S2,Bob Ray,CS,1,MATH101,Calculus,4,2024-Fall,120\n")
        errors: List[str] = []
        students = load_students(path, errors=errors)
        assert len(students[1].grades) == 1
        assert "between" in errors[0]

    def test_invalid_grade_values_strict(self, write_csv: WriteCsv) -> None:
        path = write_csv("S2,Bob Ray,CS,1,MATH101,Calculus,4,Fall-2024,80\n")
        with pytest.raises(InvalidRecordError):
            load_students(path, strict=True)

    def test_messy_sample_file(self, messy_csv: Path) -> None:
        errors: List[str] = []
        students = load_students(messy_csv, errors=errors)
        assert len(errors) == 4
        assert {s.student_id for s in students} == {"S9001", "S9002", "S9004"}

    def test_sample_dataset(self, sample_csv: Path) -> None:
        errors: List[str] = []
        students = load_students(sample_csv, errors=errors)
        assert errors == []
        assert len(students) == 40
        assert sum(len(s.grades) for s in students) == 180


class TestJson:
    def test_round_trip_and_creates_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "report.json"
        out = write_json_report({"name": "Zoë", "values": [1, 2]}, target)
        assert out == target.resolve()
        assert read_json(out) == {"name": "Zoë", "values": [1, 2]}
        assert target.read_text(encoding="utf-8").endswith("\n")

    def test_write_to_directory_fails(self, tmp_path: Path) -> None:
        with pytest.raises(ReportWriteError):
            write_json_report({}, tmp_path)

    def test_write_permission_denied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def deny(*_: Any, **__: Any) -> None:
            raise PermissionError("denied")

        monkeypatch.setattr(Path, "open", deny)
        with pytest.raises(ReportWriteError, match="Permission denied"):
            write_json_report({}, tmp_path / "r.json")

    def test_read_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(DataLoadError, match="not valid JSON"):
            read_json(bad)

    def test_read_missing_json(self, tmp_path: Path) -> None:
        with pytest.raises(DataLoadError, match="not found"):
            read_json(tmp_path / "nope.json")
