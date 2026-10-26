"""Benchmark memory and speed trade-offs between data-structure choices.

Usage::

    python scripts/benchmark_memory.py               # 100,000 records
    python scripts/benchmark_memory.py -n 500000

Memory is measured with ``tracemalloc`` (bytes actually allocated by Python
objects, including nested strings/floats), which is more accurate than
``sys.getsizeof`` because it accounts for every contained object.
"""

from __future__ import annotations

import argparse
import csv
import gc
import io
import sys
import timeit
import tracemalloc
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_sample_data import HEADER, generate_rows  # noqa: E402
from grade_analytics.file_io import iter_records  # noqa: E402
from grade_analytics.models import GradeRecord, score_to_letter  # noqa: E402


@dataclass
class PlainRecord:
    student_id: str
    name: str
    major: str
    year: int
    course_code: str
    course_name: str
    credits: int
    semester: str
    score: float


@dataclass(slots=True)
class SlottedRecord:
    student_id: str
    name: str
    major: str
    year: int
    course_code: str
    course_name: str
    credits: int
    semester: str
    score: float


def measure(build: Callable[[], object]) -> Tuple[int, int]:
    """Return (retained bytes, peak bytes) allocated while running ``build``."""
    gc.collect()
    tracemalloc.start()
    obj = build()
    retained, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del obj
    return retained, peak


def best_time(func: Callable[[], None], repeat: int = 3) -> float:
    """Fastest of ``repeat`` single runs, in seconds."""
    return min(timeit.repeat(func, number=1, repeat=repeat))


def mib(n_bytes: float) -> str:
    return f"{n_bytes / 1024 / 1024:8.2f} MiB"


def build_csv(n_records: int) -> str:
    """Generate an in-memory CSV containing about ``n_records`` rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    count = 0
    # ~4.5 records per student on average.
    for row in generate_rows(n_records // 4 + 1, seed=7):
        writer.writerow(row)
        count += 1
        if count >= n_records:
            break
    return buffer.getvalue()


def bench_representations(text: str) -> List[Tuple[str, int]]:
    rows: List[Dict[str, str]] = list(csv.DictReader(io.StringIO(text)))

    def typed(row: Dict[str, str]) -> Tuple[str, str, str, int, str, str, int, str, float]:
        return (
            row["student_id"], row["name"], row["major"], int(row["year"]),
            row["course_code"], row["course_name"], int(row["credits"]),
            row["semester"], float(row["score"]),
        )

    typed_rows = [typed(r) for r in rows]
    builders: List[Tuple[str, Callable[[], object]]] = [
        ("list[dict] (csv.DictReader)", lambda: [dict(r) for r in rows]),
        ("list[dataclass]", lambda: [PlainRecord(*t) for t in typed_rows]),
        ("list[dataclass(slots=True)]", lambda: [SlottedRecord(*t) for t in typed_rows]),
        ("list[namedtuple] (GradeRecord)", lambda: [GradeRecord(*t) for t in typed_rows]),
        # tuple(t) would return `t` itself, so unpack into a fresh tuple.
        ("list[tuple]", lambda: [tuple([*t]) for t in typed_rows]),
    ]
    # Field values are shared between representations, so each figure is the
    # per-record container overhead (dict / instance / tuple) plus the list.
    results = []
    for label, build in builders:
        retained, _ = measure(build)
        results.append((label, retained))
    return results


def bench_streaming(path: Path) -> List[Tuple[str, int]]:
    def eager() -> float:
        records = list(iter_records(path))
        return sum(r.score for r in records) / len(records)

    def lazy() -> float:
        total = count = 0.0
        for record in iter_records(path):
            total += record.score
            count += 1
        return total / count

    return [
        ("eager: list(iter_records(...))", measure(eager)[1]),
        ("lazy: for r in iter_records(...)", measure(lazy)[1]),
    ]


def bench_rolling(n: int, window: int = 3) -> List[Tuple[str, float]]:
    values = [float(i % 100) for i in range(n)]

    def with_list() -> None:
        buf: List[float] = []
        for v in values:
            buf.append(v)
            if len(buf) > window:
                buf.pop(0)
            sum(buf) / len(buf)

    def with_deque() -> None:
        buf: deque[float] = deque(maxlen=window)
        total = 0.0
        for v in values:
            if len(buf) == window:
                total -= buf[0]
            buf.append(v)
            total += v
            total / len(buf)

    return [
        (f"list + pop(0) + sum() (window={window})", best_time(with_list)),
        (f"deque(maxlen) + running sum (window={window})", best_time(with_deque)),
    ]


def bench_counting(n: int) -> List[Tuple[str, float]]:
    scores = [float(i % 101) for i in range(n)]
    letters = [score_to_letter(s).value for s in scores]

    def manual_dict() -> None:
        counts: Dict[str, int] = {}
        for letter in letters:
            if letter in counts:
                counts[letter] += 1
            else:
                counts[letter] = 1

    def counter() -> None:
        Counter(letters)

    return [
        ("dict with if/else", best_time(manual_dict)),
        ("Counter(iterable)", best_time(counter)),
    ]


def bench_deque_vs_list_left(n: int) -> List[Tuple[str, float]]:
    def list_insert() -> None:
        buf: List[int] = []
        for i in range(n):
            buf.insert(0, i)

    def deque_appendleft() -> None:
        buf: deque[int] = deque()
        for i in range(n):
            buf.appendleft(i)

    return [
        ("list.insert(0, x)", best_time(list_insert)),
        ("deque.appendleft(x)", best_time(deque_appendleft)),
    ]


def report_table(
    title: str, rows: Sequence[Tuple[str, float]], fmt: Callable[[float], str]
) -> Iterator[str]:
    baseline = rows[0][1] or 1
    yield f"\n### {title}\n"
    yield "| Approach | Result | Relative |"
    yield "|---|---:|---:|"
    for label, value in rows:
        yield f"| {label} | {fmt(value).strip()} | {value / baseline:.2f}x |"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark collection trade-offs.")
    parser.add_argument("-n", "--records", type=int, default=100_000)
    parser.add_argument("--tmp", type=Path, default=Path("data/large_benchmark.csv"))
    args = parser.parse_args()

    text = build_csv(args.records)
    args.tmp.parent.mkdir(parents=True, exist_ok=True)
    args.tmp.write_text(text, encoding="utf-8")
    n = text.count("\n") - 1

    def ms(seconds: float) -> str:
        return f"{seconds * 1000:8.1f} ms"

    print(f"## Benchmark results ({n:,} records, Python {sys.version.split()[0]})")
    sections: List[Tuple[str, Sequence[Tuple[str, float]], Callable[[float], str]]] = [
        ("Retained memory per representation", bench_representations(text), mib),
        ("Peak memory: eager list vs generator", bench_streaming(args.tmp), mib),
        ("Rolling average update cost", bench_rolling(n), ms),
        ("Grade distribution counting", bench_counting(n), ms),
        ("Prepending 50,000 items", bench_deque_vs_list_left(50_000), ms),
    ]
    for title, rows, fmt in sections:
        for line in report_table(title, rows, fmt):
            print(line)
    args.tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
