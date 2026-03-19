"""Pyperf integration for GC monitoring.

This package provides pyperf hooks for collecting GC statistics during benchmarks.
"""

from .hook import GCMonitorHook, gc_monitor_hook

__all__ = [
    "GCMonitorHook",
    "gc_monitor_hook",
]
