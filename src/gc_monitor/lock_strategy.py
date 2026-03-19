from typing import Any, Protocol


class ContextLock(Protocol):
    def __enter__(self) -> bool: ...
    def __exit__(self, type: Any, value: Any, traceback: Any) -> None: ...


class LockStrategy(Protocol):
    def lock(self) -> ContextLock: ...


class NoLock:
    class EmptyLock:
        def __enter__(self) -> bool:
            return True

        def __exit__(self, type: Any, value: Any, traceback: Any) -> None: ...

    def lock(self) -> ContextLock:
        return NoLock.EmptyLock()


class ThreadLock:
    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()

    def lock(self) -> ContextLock:
        return self._lock
