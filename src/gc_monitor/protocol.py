from collections.abc import Mapping
from typing import Protocol, TypeGuard


class TGCStatsInfo(Protocol):
    gen: int
    iid: int
    ts_start: int
    ts_stop: int
    heap_size: int
    collections: int
    collected: int
    uncollectable: int
    candidates: int
    duration: float


class TIncrementalGCStatsInfo(TGCStatsInfo, Protocol):
    increment_size: int
    alive_size: int
    ts_mark_alive_start: int
    ts_mark_alive_stop: int
    ts_fill_increment_start: int
    ts_fill_increment_stop: int
    ts_deduce_uncreachable_start: int
    ts_deduce_uncreachable_stop: int


def is_incremental(item: TGCStatsInfo | TIncrementalGCStatsInfo) -> TypeGuard[TIncrementalGCStatsInfo]:
    return hasattr(item, "increment_size")


def to_mapping(item: TGCStatsInfo | TIncrementalGCStatsInfo) -> Mapping[str, int | float]:
    """Ensures a TypedDict is treated as a standard Mapping."""
    m: dict[str, int | float] = {
        "gen": item.gen,
        "iid": item.iid,
        "ts_start": item.ts_start,
        "ts_stop": item.ts_stop,
        "heap_size": item.heap_size,
        "collections": item.collections,
        "collected": item.collected,
        "uncollectable": item.uncollectable,
        "candidates": item.candidates,
        "duration": item.duration,
    }

    if is_incremental(item):
        m["alive_size"] = item.alive_size
        m["increment_size"] = item.increment_size
        m["ts_mark_alive_start"] = item.ts_mark_alive_start
        m["ts_mark_alive_stop"] = item.ts_mark_alive_stop
        m["ts_fill_increment_start"] = item.ts_fill_increment_start
        m["ts_fill_increment_stop"] = item.ts_fill_increment_stop
        m["ts_deduce_uncreachable_start"] = item.ts_deduce_uncreachable_start
        m["ts_deduce_uncreachable_stop"] = item.ts_deduce_uncreachable_stop

    return m
