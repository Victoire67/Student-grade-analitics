"""Tests for report assembly, JSON output and terminal rendering."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, get_type_hints

import pytest

from grade_analytics.file_io import load_students, write_json_report
from grade_analytics.models import Student
from grade_analytics.report import build_report
from grade_analytics.schemas import AnalyticsReport, StudentRanking
from grade_analytics.visualization import bar_chart, trend_chart

FIXED_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def report(students: List[Student]) -> AnalyticsReport:
    return build_report(students, source_file="test.csv", top_n=2, generated_at=FIXED_TIME)


class TestStructure:
    def test_has_every_typed_dict_key(self, report: AnalyticsReport) -> None:
        assert list(report) == list(get_type_hints(AnalyticsReport))

    def test_ranking_entries_match_schema(self, report: AnalyticsReport) -> None:
        assert set(report["rankings"][0]) == set(get_type_hints(StudentRanking))

    def test_sections_are_sorted_ordereddicts(self, report: AnalyticsReport) -> None:
        for section in ("by_major", "by_year", "courses"):
            assert isinstance(report[section], OrderedDict)
            assert list(report[section]) == sorted(report[section])

    def test_is_json_serialisable(self, report: AnalyticsReport) -> None:
        assert json.loads(json.dumps(report))["metadata"]["source_file"] == "test.csv"


class TestValues:
    def test_metadata(self, report: AnalyticsReport) -> None:
        meta = report["metadata"]
        assert meta["generated_at"] == "2026-01-01T12:00:00+00:00"
        assert (meta["student_count"], meta["course_count"], meta["record_count"]) == (4, 2, 6)

    def test_overall_statistics(self, report: AnalyticsReport) -> None:
        overall = report["overall_statistics"]
        assert overall["count"] == 6
        assert overall["mean"] == round((92 + 85 + 60 + 81 + 89 + 89) / 6, 2)
        assert overall["median"] == 87.0
        assert overall["mode"] == [89.0]

    def test_grade_distribution(self, report: AnalyticsReport) -> None:
        assert report["grade_distribution"] == {"A": 1, "B": 4, "C": 0, "D": 1, "F": 0}

    def test_top_performers_respects_top_n(self, report: AnalyticsReport) -> None:
        assert len(report["top_performers"]) == 2
        assert report["top_performers"] == report["rankings"][:2]

    def test_floats_are_rounded(self, report: AnalyticsReport) -> None:
        for entry in report["rankings"]:
            assert entry["percentile"] == round(entry["percentile"], 2)

    def test_group_summaries(self, report: AnalyticsReport) -> None:
        cs = report["by_major"]["Computer Science"]
        assert cs == {"student_count": 2, "average": 80.5, "top_student": "Cara Ng"}
        # Dan has no grades: counted in the group but not averaged.
        math = report["by_major"]["Mathematics"]
        assert math["student_count"] == 2 and math["average"] == 89.0
        assert list(report["by_year"]) == ["Year 1", "Year 2"]

    def test_course_section(self, report: AnalyticsReport) -> None:
        math = report["courses"]["MATH101"]
        assert math["enrollment"] == 3
        assert math["credits"] == 4
        assert math["statistics"]["maximum"] == 92.0

    def test_semester_trends(self, report: AnalyticsReport) -> None:
        assert [t["semester"] for t in report["semester_trends"]] == [
            "2023-Fall", "2024-Spring", "2024-Fall",
        ]

    def test_empty_input(self) -> None:
        empty = build_report([])
        assert empty["overall_statistics"]["mean"] is None
        assert empty["rankings"] == [] and empty["semester_trends"] == []


class TestSampleDataIntegration:
    def test_sample_report(self, sample_csv: Path, tmp_path: Path) -> None:
        students = load_students(sample_csv)
        report = build_report(students, source_file=sample_csv.name)
        out = write_json_report(report, tmp_path / "report.json")
        loaded = json.loads(out.read_text(encoding="utf-8"))

        assert loaded["metadata"]["record_count"] == 180
        assert sum(loaded["grade_distribution"].values()) == 180
        ranks = [r["rank"] for r in loaded["rankings"]]
        assert ranks == sorted(ranks) and ranks[0] == 1
        averages = [r["weighted_average"] for r in loaded["rankings"]]
        assert averages == sorted(averages, reverse=True)
        assert all(0 <= r["percentile"] <= 100 for r in loaded["rankings"])


class TestVisualization:
    def test_bar_chart(self) -> None:
        lines = bar_chart({"A": 4, "B": 2, "F": 0}, width=8)
        assert lines[0].count("█") == 8
        assert lines[1].count("█") == 4
        assert lines[2].count("█") == 0 and "0 (0.0%)" in lines[2]

    def test_bar_chart_empty(self) -> None:
        assert bar_chart({}) == []
        assert bar_chart({"A": 0}) == ["A |  0 (0.0%)"]

    def test_trend_chart(self, report: AnalyticsReport) -> None:
        lines = trend_chart(report["semester_trends"], width=10)
        assert len(lines) == 3
        assert lines[0].count("█") == 1  # lowest average still visible
        assert lines[1].count("█") == 10  # highest average gets full width
        assert trend_chart([]) == []
