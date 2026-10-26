"""End-to-end tests for the command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from grade_analytics.cli import main


def test_generates_report_and_summary(
    sample_csv: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "report.json"
    assert main([str(sample_csv), "-o", str(out), "--top", "3"]) == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert len(report["top_performers"]) == 3
    stdout = capsys.readouterr().out
    assert "STUDENT GRADE ANALYTICS REPORT" in stdout
    assert "Top 3 performers" in stdout
    assert "Report written to" in stdout


def test_quiet_mode(sample_csv: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(sample_csv), "-o", str(tmp_path / "r.json"), "-q"]) == 0
    assert capsys.readouterr().out == ""


def test_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "missing.csv")]) == 1
    assert "not found" in capsys.readouterr().err


def test_messy_file_lenient_vs_strict(
    messy_csv: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(messy_csv), "-o", str(tmp_path / "r.json")]) == 0
    assert "Skipped 4 invalid row(s)" in capsys.readouterr().out
    assert main([str(messy_csv), "-o", str(tmp_path / "r.json"), "--strict"]) == 1


def test_empty_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text(
        "student_id,name,major,year,course_code,course_name,credits,semester,score\n",
        encoding="utf-8",
    )
    assert main([str(empty), "-o", str(tmp_path / "r.json")]) == 1
    assert "no valid records" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--top", "-1"], ["--window", "0"]])
def test_invalid_options(sample_csv: Path, args: list[str]) -> None:
    assert main([str(sample_csv), *args]) == 1


def test_unwritable_output(sample_csv: Path, tmp_path: Path) -> None:
    # Output path is an existing directory.
    assert main([str(sample_csv), "-o", str(tmp_path), "-q"]) == 1
