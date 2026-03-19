import pytest

from gc_monitor.data import GCStatsInfo, IncrementalGCStatsInfo, from_mapping, dur_to_us, ts_to_us
from gc_monitor.protocol import to_mapping


@pytest.fixture
def gc_stats_struct():
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
def gc_stats_dict(gc_stats_struct):
    return to_mapping(gc_stats_struct)


@pytest.fixture
def incremental_struct():
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


@pytest.fixture
def incremental_dict(incremental_struct):
    return to_mapping(incremental_struct)


class TestGCStatsInfo:
    def test_struct_creation(self, gc_stats_struct):
        assert gc_stats_struct.gen == 0
        assert gc_stats_struct.iid == 1
        assert gc_stats_struct.ts_start == 1_000_000
        assert gc_stats_struct.ts_stop == 2_000_000
        assert gc_stats_struct.heap_size == 1024
        assert gc_stats_struct.collections == 5
        assert gc_stats_struct.collected == 50
        assert gc_stats_struct.uncollectable == 0
        assert gc_stats_struct.candidates == 10
        assert gc_stats_struct.duration == 0.005

    def test_satisfies_tgc_stats_info_protocol(self, gc_stats_struct):
        result = to_mapping(gc_stats_struct)
        assert "ts_start" in result
        assert "gen" in result


class TestIncrementalGCStatsInfo:
    def test_struct_creation(self, incremental_struct):
        assert incremental_struct.gen == 1
        assert incremental_struct.increment_size == 500
        assert incremental_struct.alive_size == 300

    def test_inherits_base_fields(self, incremental_struct):
        assert incremental_struct.gen == 1
        assert incremental_struct.ts_start == 3_000_000
        assert incremental_struct.collections == 10

    def test_satisfies_t_incremental_protocol(self, incremental_struct):
        result = to_mapping(incremental_struct)
        assert "increment_size" in result

    def test_satisfies_tgc_stats_info_protocol(self, incremental_struct):
        result = to_mapping(incremental_struct)
        assert "gen" in result


class TestFromMapping:
    def test_returns_gc_stats_info(self, gc_stats_dict):
        result = from_mapping(gc_stats_dict)
        assert isinstance(result, GCStatsInfo)
        assert result.gen == 0
        assert result.ts_start == 1_000_000

    def test_returns_incremental(self, incremental_dict):
        result = from_mapping(incremental_dict)
        assert isinstance(result, IncrementalGCStatsInfo)
        assert result.gen == 1
        assert result.increment_size == 500


class TestTimeConversions:
    def test_ts_to_us(self):
        assert ts_to_us(1_000_000) == 1_000

    def test_ts_to_us_zero(self):
        assert ts_to_us(0) == 0

    def test_ts_to_us_rounds_down(self):
        assert ts_to_us(1_999) == 1

    def test_dur_to_us(self):
        assert dur_to_us(1_000_000, 3_000_000) == 2_000

    def test_dur_to_us_zero(self):
        assert dur_to_us(1000, 1000) == 0

    def test_dur_to_us_negative(self):
        assert dur_to_us(5_000_000, 2_000_000) == -3_000
