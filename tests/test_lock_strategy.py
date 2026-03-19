import pytest

from gc_monitor.lock_strategy import NoLock, ThreadLock


@pytest.fixture
def no_lock():
    return NoLock()


@pytest.fixture
def thread_lock():
    return ThreadLock()


class TestNoLock:
    def test_lock_enter_returns_true(self, no_lock):
        assert no_lock.lock().__enter__() is True

    def test_context_manager(self, no_lock):
        with no_lock.lock():
            pass

    def test_fresh_instance_per_call(self, no_lock):
        assert no_lock.lock() is not no_lock.lock()


class TestThreadLock:
    def test_context_manager(self, thread_lock):
        with thread_lock.lock():
            pass

    def test_same_instance_per_call(self, thread_lock):
        assert thread_lock.lock() is thread_lock.lock()

    def test_lock_holds_until_release(self, thread_lock):
        lock = thread_lock.lock()
        acquired = lock.__enter__()
        assert acquired is True
        lock.__exit__(None, None, None)
