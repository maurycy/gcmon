from collections.abc import Mapping

import pytest

from gc_monitor.protocol import TGCStatsInfo, TIncrementalGCStatsInfo, is_incremental, to_mapping
from gc_monitor.data import GCStatsInfo, IncrementalGCStatsInfo


@pytest.fixture
def simple_item():
    return GCStatsInfo(
        gen=0,
        iid=1,
        ts_start=1_000_000,
        ts_stop=2_000_000,
        heap_size=1024,
        collections=5,
        collected=50,
        uncollectable=0,
        candidates=10,
        duration=0.005,
    )


@pytest.fixture
def incremental_item():
    return IncrementalGCStatsInfo(
        gen=1,
        iid=2,
        ts_start=3_000_000,
        ts_stop=4_000_000,
        heap_size=2048,
        collections=10,
        collected=100,
        uncollectable=1,
        candidates=20,
        duration=0.01,
        increment_size=500,
        alive_size=300,
        ts_mark_alive_start=3_000_500,
        ts_mark_alive_stop=3_001_000,
        ts_fill_increment_start=3_001_500,
        ts_fill_increment_stop=3_002_000,
        ts_deduce_uncreachable_start=3_002_500,
        ts_deduce_uncreachable_stop=3_003_000,
    )


class TestIsIncremental:
    def test_regular_returns_false(self, simple_item):
        assert is_incremental(simple_item) is False

    def test_incremental_returns_true(self, incremental_item):
        assert is_incremental(incremental_item) is True

    def test_incremental_type_guard(self, incremental_item):
        result = is_incremental(incremental_item)
        if result:
            assert incremental_item.increment_size == 500
            assert incremental_item.alive_size == 300


class TestToMapping:
    def test_regular_item(self, simple_item):
        result = to_mapping(simple_item)

        assert isinstance(result, Mapping)
        assert result["gen"] == 0
        assert result["iid"] == 1
        assert result["ts_start"] == 1_000_000
        assert result["ts_stop"] == 2_000_000
        assert result["heap_size"] == 1024
        assert result["collections"] == 5
        assert result["collected"] == 50
        assert result["uncollectable"] == 0
        assert result["candidates"] == 10
        assert result["duration"] == 0.005
        assert "increment_size" not in result

    def test_incremental_item(self, incremental_item):
        result = to_mapping(incremental_item)

        assert result["gen"] == 1
        assert result["increment_size"] == 500
        assert result["alive_size"] == 300
        assert result["ts_mark_alive_start"] == 3_000_500
        assert result["ts_mark_alive_stop"] == 3_001_000
        assert result["ts_fill_increment_start"] == 3_001_500
        assert result["ts_fill_increment_stop"] == 3_002_000
        assert result["ts_deduce_uncreachable_start"] == 3_002_500
        assert result["ts_deduce_uncreachable_stop"] == 3_003_000
