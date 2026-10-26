"""Dependency-free text visualizations for terminal output."""

from __future__ import annotations

from typing import List, Mapping, Sequence

from .schemas import TrendPoint

__all__ = ["bar_chart", "trend_chart"]

_BLOCK = "█"


def bar_chart(counts: Mapping[str, int], width: int = 40) -> List[str]:
    """Horizontal bar chart lines for labelled counts.

    >>> bar_chart({"A": 2, "B": 1}, width=4)
    ['A | ████ 2 (66.7%)', 'B | ██ 1 (33.3%)']
    """
    total = sum(counts.values())
    peak = max(counts.values(), default=0)
    label_width = max((len(label) for label in counts), default=0)
    lines: List[str] = []
    for label, count in counts.items():
        length = round(width * count / peak) if peak else 0
        share = 100 * count / total if total else 0.0
        lines.append(f"{label:<{label_width}} | {_BLOCK * length} {count} ({share:.1f}%)")
    return lines


def trend_chart(trends: Sequence[TrendPoint], width: int = 30) -> List[str]:
    """Per-semester bars scaled between the lowest and highest averages."""
    if not trends:
        return []
    averages = [t["average"] for t in trends]
    low, high = min(averages), max(averages)
    span = high - low
    label_width = max(len(t["semester"]) for t in trends)
    lines: List[str] = []
    for t in trends:
        # Keep at least one block so the smallest value is still visible.
        length = 1 + (round((width - 1) * (t["average"] - low) / span) if span else width - 1)
        lines.append(
            f"{t['semester']:<{label_width}} | {_BLOCK * length:<{width}} "
            f"avg {t['average']:6.2f}  rolling {t['rolling_average']:6.2f}"
        )
    return lines
