"""Shared fixtures for exporter tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gc_monitor.exporters import JsonlExporter, TraceExporter
from gc_monitor.lock_strategy import NoLock

from tests.conftest import DEFAULT_METADATA


@pytest.fixture
def jsonl_exporter(tmp_path: Path) -> Any:
    """Factory fixture for JsonlExporter instances.

    Usage:
        exporter, path = jsonl_exporter(threshold=50)
    """
    def _make(threshold: int = 100, metadata: dict | None = None) -> tuple[JsonlExporter, Path]:
        path = tmp_path / "test.jsonl"
        exporter = JsonlExporter(NoLock, metadata or DEFAULT_METADATA, output_path=path, flush_threshold=threshold)
        return exporter, path
    return _make


@pytest.fixture
def trace_exporter(tmp_path: Path) -> Any:
    """Factory fixture for TraceExporter instances.

    Usage:
        exporter, path = trace_exporter(threshold=50)
    """
    def _make(threshold: int = 100, metadata: dict | None = None) -> tuple[TraceExporter, Path]:
        path = tmp_path / "trace.json"
        exporter = TraceExporter(NoLock, metadata or DEFAULT_METADATA, output_path=path, flush_threshold=threshold)
        return exporter, path
    return _make


@pytest.fixture
def read_jsonl() -> Any:
    """Read a JSONL file and return list of parsed events."""
    def _read(path: Path) -> list[dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    return _read
