from typing import Protocol, TypedDict, override, runtime_checkable


class TargetProcessMetadata(TypedDict):
    pid: int


@runtime_checkable
class TargetProcess(Protocol):
    @property
    def pid(self) -> int: ...
    def metadata(self) -> TargetProcessMetadata: ...


class ExternalProcess(TargetProcess):
    def __init__(self, pid: int):
        self._pid = pid

    @property
    @override
    def pid(self) -> int:
        return self._pid

    @override
    def metadata(self) -> TargetProcessMetadata:
        return {
            "pid": self._pid,
        }
