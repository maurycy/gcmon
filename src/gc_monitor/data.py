from collections.abc import Mapping

import msgspec


class GCStatsInfo(msgspec.Struct):
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


class IncrementalGCStatsInfo(GCStatsInfo):
    increment_size: int
    alive_size: int
    ts_mark_alive_start: int
    ts_mark_alive_stop: int
    ts_fill_increment_start: int
    ts_fill_increment_stop: int
    ts_deduce_uncreachable_start: int
    ts_deduce_uncreachable_stop: int


def from_mapping(data: Mapping[str, int | float]) -> GCStatsInfo | IncrementalGCStatsInfo:
    if "increment_size" in data:
        return msgspec.convert(data, IncrementalGCStatsInfo)
    return msgspec.convert(data, GCStatsInfo)


def ts_to_us(ts_ns: int) -> int:
    """Convert timestamp from nanoseconds to microseconds"""
    return int(ts_ns / 1_000)


def dur_to_us(ts_start_ns: int, ts_stop_ns: int) -> int:
    """Convert duration from seconds to microseconds"""
    return int((ts_stop_ns - ts_start_ns) / 1_000)
