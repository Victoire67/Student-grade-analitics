# Performance & Memory Notes

Measurements were produced with:

```bash
python scripts/benchmark_memory.py            # 100,000 records
```

Environment: Python 3.14.8, Windows 11, 100,000 synthetic records.
Absolute numbers vary by machine and Python version; the **relative** figures
are what matter.

## 1. Representing a record

Memory retained by a list of 100,000 records, measured with `tracemalloc`.
Field values (strings, ints, floats) are shared between representations, so
the figures isolate the per-record **container** overhead.

| Approach | Retained | Relative |
|---|---:|---:|
| `list[dict]` (raw `csv.DictReader` rows) | 26.70 MiB | 1.00x |
| `list[dataclass]` | 15.26 MiB | 0.57x |
| `list[dataclass(slots=True)]` | **10.68 MiB** | **0.40x** |
| `list[namedtuple]` (`GradeRecord`) | 12.97 MiB | 0.49x |
| `list[tuple]` | 12.21 MiB | 0.46x |

**Takeaways**

- Keeping raw `DictReader` rows is the most expensive choice: every row owns a
  hash table sized for its keys.
- `slots=True` removes the per-instance `__dict__`, cutting dataclass memory by
  ~30%. This is why `Course`, `Grade` and `Student` are slotted.
- A `namedtuple` costs about the same as a plain tuple but adds named access,
  immutability and `_asdict()`. It is used for `GradeRecord`, the flat
  row type that streams out of the CSV reader.
- Slotted dataclasses win when you also need validation (`__post_init__`),
  defaults, methods and mutability (`Student.grades`).

## 2. Eager loading vs generators

Peak memory while computing the mean score of a 100,000-row file.

| Approach | Peak | Relative |
|---|---:|---:|
| `list(iter_records(path))` then average | 44.52 MiB | 1.00x |
| `for r in iter_records(path)` (streaming) | **0.17 MiB** | ~0.00x |

`iter_records` is a generator, so a single pass over the data uses constant
memory regardless of file size. `load_students` still materialises `Student`
objects because rankings and medians need all scores, but it never holds the
raw rows as well, so memory scales with the aggregated model, not the file.

## 3. Rolling averages: `deque` vs `list`

| Approach | Time (100k updates) | Relative |
|---|---:|---:|
| `list` + `pop(0)` + `sum()` per update | 25.1 ms | 1.00x |
| `deque(maxlen=w)` + running sum | **14.8 ms** | 0.59x |

`list.pop(0)` is O(n) and re-summing the window is O(w). `RollingAverage`
uses `deque(maxlen=w)` for automatic O(1) eviction and keeps a running total,
so each update is O(1) regardless of window size. The gap grows with the window.

The difference is starker when inserting at the front of a sequence:

| Approach | Time (50k prepends) | Relative |
|---|---:|---:|
| `list.insert(0, x)` | 397.0 ms | 1.00x |
| `deque.appendleft(x)` | **2.1 ms** | 0.01x |

## 4. Counting: `Counter` vs manual `dict`

| Approach | Time (100k letters) | Relative |
|---|---:|---:|
| `dict` with `if key in d` | 7.8 ms | 1.00x |
| `Counter(iterable)` | **4.2 ms** | 0.54x |

`Counter` counts in C, and it adds `most_common()` and arithmetic between
counters. `grade_distribution` seeds the counter with every letter (A-F) at
zero so reports always list the same keys in the same order.

## 5. Other design decisions

| Concern | Choice | Why |
|---|---|---|
| Grouping students by major/year | `defaultdict(list)` | No key-existence checks; one pass, O(n). Converted to a plain `dict` before returning so missing keys don't silently create entries. |
| Ordered report sections | `OrderedDict` with sorted keys | Deterministic, diff-friendly JSON; makes ordering an explicit part of the contract. |
| Semester ordering | `semester_sort_key` → `(year, season)` | String sorting would put `2024-Fall` before `2024-Spring`. |
| Shared course objects | One frozen `Course` per code | `load_students` de-duplicates courses so 100k grades reference a handful of `Course` instances. |
| Median / percentiles | `sorted()` once per call, O(n log n) | Simple and exact; fine for class-sized and course-sized groups. |
| Percentile ranks | `percentile_ranks`: sort once + `bisect` | O(n log n) for a whole ranking instead of O(n²) (see below). |

## 6. Case study: fixing an O(n²) hot spot

The first version of `rank_students` called `percentile_rank(value, population)`
for each student. Each call scans the whole population, so ranking *n*
students cost O(n²). That was invisible on the 40-student sample but
dominated runtime at scale.

`percentile_ranks` sorts the averages once and uses `bisect_left` /
`bisect_right` to count values below and equal to each score, which is
O(n log n). `tests/test_stats.py` checks that it matches the reference
implementation exactly.

End-to-end CLI run on 50,000 students / 225,127 records:

| Version | Wall time |
|---|---:|
| Linear `percentile_rank` per student (O(n²)) | 6 min 44 s |
| `percentile_ranks` with `bisect` (O(n log n)) | **5.0 s** (~81x faster) |

Reproduce:

```bash
python scripts/generate_sample_data.py -n 50000 -o data/large_students.csv
python -m grade_analytics data/large_students.csv -o reports/large.json -q
```
