"""Tests for statistics helpers (Counter- and deque-based)."""

from __future__ import annotations

import random
import statistics
from collections import Counter, deque

import pytest

from grade_analytics.stats import (
    RollingAverage,
    describe,
    grade_distribution,
    mean,
    median,
    mode,
    percentile,
    percentile_rank,
    percentile_ranks,
    rolling_averages,
    std_dev,
)

DATA = [70.0, 85.0, 90.0, 85.0, 60.0, 95.0]


class TestCentralTendency:
    def test_mean_matches_stdlib(self) -> None:
        assert mean(DATA) == pytest.approx(statistics.fmean(DATA))

    @pytest.mark.parametrize("values", [DATA, DATA[:-1], [42.0]])
    def test_median_matches_stdlib(self, values: list[float]) -> None:
        assert median(values) == statistics.median(values)

    def test_empty_inputs(self) -> None:
        assert mean([]) is None
        assert median([]) is None
        assert std_dev([]) is None
        assert mode([]) == []

    def test_std_dev_matches_stdlib(self) -> None:
        assert std_dev(DATA) == pytest.approx(statistics.pstdev(DATA))


class TestModeWithCounter:
    def test_single_mode(self) -> None:
        assert mode(DATA) == [85.0]

    def test_multimodal_returns_all_sorted(self) -> None:
        assert mode([3, 1, 3, 1, 2]) == [1, 3]
        assert mode([3, 1, 3, 1, 2]) == sorted(statistics.multimode([3, 1, 3, 1, 2]))

    def test_accepts_generator(self) -> None:
        assert mode(x for x in (5, 5, 6)) == [5]


class TestPercentiles:
    @pytest.mark.parametrize(("pct", "expected"), [(0, 60.0), (50, 85.0), (100, 95.0)])
    def test_percentile(self, pct: float, expected: float) -> None:
        assert percentile(DATA, pct) == expected

    def test_percentile_interpolates(self) -> None:
        assert percentile([10, 20], 25) == pytest.approx(12.5)

    def test_percentile_validates_range(self) -> None:
        with pytest.raises(ValueError):
            percentile(DATA, 101)
        assert percentile([], 50) is None

    def test_percentile_rank_counts_ties_half(self) -> None:
        assert percentile_rank(85.0, DATA) == pytest.approx(100 * (2 + 1) / 6)
        assert percentile_rank(100.0, DATA) == 100.0
        assert percentile_rank(0.0, DATA) == 0.0

    def test_percentile_ranks_matches_reference(self) -> None:
        rng = random.Random(0)
        values = [float(rng.randint(40, 100)) for _ in range(500)]
        expected = [percentile_rank(v, values) for v in values]
        assert percentile_ranks(values) == pytest.approx(expected)
        assert percentile_ranks([]) == []

    def test_percentile_rank_requires_population(self) -> None:
        with pytest.raises(ValueError):
            percentile_rank(1.0, [])


class TestGradeDistribution:
    def test_is_counter_with_all_letters_in_order(self) -> None:
        dist = grade_distribution(DATA)
        assert isinstance(dist, Counter)
        assert list(dist) == ["A", "B", "C", "D", "F"]
        assert dict(dist) == {"A": 2, "B": 2, "C": 1, "D": 1, "F": 0}
        assert sum(dist.values()) == len(DATA)

    def test_most_common(self) -> None:
        assert grade_distribution([95, 91, 50]).most_common(1) == [("A", 2)]

    def test_empty(self) -> None:
        assert sum(grade_distribution([]).values()) == 0


class TestDescribe:
    def test_fields(self) -> None:
        stats = describe(DATA)
        assert stats["count"] == 6
        assert stats["minimum"] == 60.0 and stats["maximum"] == 95.0
        assert stats["mode"] == [85.0]

    def test_empty(self) -> None:
        stats = describe([])
        assert stats["count"] == 0
        assert stats["mean"] is None and stats["minimum"] is None


class TestRollingAverageDeque:
    def test_uses_bounded_deque(self) -> None:
        ra = RollingAverage(window=2)
        assert isinstance(ra._values, deque)
        assert ra._values.maxlen == 2

    def test_window_evicts_oldest(self) -> None:
        ra = RollingAverage(window=3)
        for value in (10, 20, 30, 40):
            ra.add(value)
        assert ra.values == [20, 30, 40]
        assert len(ra) == 3
        assert ra.average == pytest.approx(30.0)

    def test_average_none_when_empty(self) -> None:
        assert RollingAverage().average is None

    def test_running_sum_stays_accurate(self) -> None:
        ra = RollingAverage(window=5)
        values = [float(v % 17) for v in range(1000)]
        for value in values:
            ra.add(value)
        assert ra.average == pytest.approx(sum(values[-5:]) / 5)

    def test_invalid_window(self) -> None:
        with pytest.raises(ValueError):
            RollingAverage(window=0)

    def test_rolling_averages_helper(self) -> None:
        assert rolling_averages([1, 2, 3, 4], window=2) == [1.0, 1.5, 2.5, 3.5]
        assert rolling_averages([], window=2) == []
