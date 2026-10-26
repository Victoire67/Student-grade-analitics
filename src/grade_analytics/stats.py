"""Statistical helpers built on ``collections``.

Mode and grade distributions use :class:`collections.Counter`; rolling
averages use a bounded :class:`collections.deque` so each update is O(1).
"""

from __future__ import annotations

import math
from collections import Counter, deque
from typing import Deque, Iterable, List, Optional, Sequence

from .models import LetterGrade, score_to_letter
from .schemas import ScoreStatistics

__all__ = [
    "RollingAverage",
    "describe",
    "grade_distribution",
    "mean",
    "median",
    "mode",
    "percentile",
    "percentile_rank",
    "rolling_averages",
    "std_dev",
]


def mean(values: Sequence[float]) -> Optional[float]:
    """Arithmetic mean, or ``None`` for an empty sequence."""
    if not values:
        return None
    return math.fsum(values) / len(values)


def median(values: Sequence[float]) -> Optional[float]:
    """Middle value (mean of the two middle values for even counts)."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def mode(values: Iterable[float]) -> List[float]:
    """All most-common values, sorted ascending.

    Returns every tied value so multimodal data is reported honestly; returns
    an empty list for empty input.

    >>> mode([90, 85, 90, 70, 85])
    [85, 90]
    """
    counts = Counter(values)
    if not counts:
        return []
    top = max(counts.values())
    return sorted(value for value, count in counts.items() if count == top)


def std_dev(values: Sequence[float]) -> Optional[float]:
    """Population standard deviation, or ``None`` for an empty sequence."""
    avg = mean(values)
    if avg is None:
        return None
    return math.sqrt(math.fsum((v - avg) ** 2 for v in values) / len(values))


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """Value at percentile ``pct`` (0-100) using linear interpolation."""
    if not 0 <= pct <= 100:
        raise ValueError(f"pct must be within [0, 100], got {pct}")
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def percentile_rank(value: float, population: Sequence[float]) -> float:
    """Percentage of ``population`` scoring below ``value`` (ties count half).

    >>> percentile_rank(80, [60, 70, 80, 90])
    62.5
    """
    if not population:
        raise ValueError("population must not be empty")
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    return 100.0 * (below + 0.5 * equal) / len(population)


def grade_distribution(scores: Iterable[float]) -> "Counter[str]":
    """Count letter grades, always including every letter (A-F) in order."""
    counts: Counter[str] = Counter({letter.value: 0 for letter in LetterGrade})
    counts.update(score_to_letter(score).value for score in scores)
    return counts


def describe(values: Sequence[float]) -> ScoreStatistics:
    """Summary statistics for ``values`` as a :class:`ScoreStatistics` dict."""
    return ScoreStatistics(
        count=len(values),
        mean=mean(values),
        median=median(values),
        mode=mode(values),
        std_dev=std_dev(values),
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
    )


class RollingAverage:
    """Fixed-window moving average backed by ``deque(maxlen=window)``.

    The deque automatically evicts the oldest value when full, and a running
    sum keeps :meth:`add` O(1) regardless of the window size.

    >>> ra = RollingAverage(window=3)
    >>> [ra.add(v) for v in (70, 80, 90, 100)]
    [70.0, 75.0, 80.0, 90.0]
    """

    __slots__ = ("_window", "_values", "_total")

    def __init__(self, window: int = 3) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self._window = window
        self._values: Deque[float] = deque(maxlen=window)
        self._total = 0.0

    @property
    def window(self) -> int:
        """Maximum number of values averaged."""
        return self._window

    @property
    def values(self) -> List[float]:
        """Values currently inside the window, oldest first."""
        return list(self._values)

    @property
    def average(self) -> Optional[float]:
        """Current average, or ``None`` before any value is added."""
        if not self._values:
            return None
        return self._total / len(self._values)

    def add(self, value: float) -> float:
        """Push ``value`` into the window and return the updated average."""
        if len(self._values) == self._window:
            self._total -= self._values[0]
        self._values.append(value)
        self._total += value
        return self._total / len(self._values)

    def __len__(self) -> int:
        return len(self._values)


def rolling_averages(values: Iterable[float], window: int = 3) -> List[float]:
    """Rolling average after each value in ``values``."""
    roller = RollingAverage(window)
    return [roller.add(value) for value in values]
