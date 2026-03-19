import pytest

from gc_monitor.poll_status import PollStatus


@pytest.fixture
def poll_status_list():
    return list(PollStatus)


class TestPollStatusMembers:
    def test_all_members_present(self, poll_status_list):
        assert poll_status_list == [
            PollStatus.OK,
            PollStatus.FAIL,
            PollStatus.INVALID_PROCESS,
            PollStatus.INVALID_PYTHON,
        ]

    def test_int_enum_comparison(self):
        assert PollStatus.OK == 1
        assert PollStatus.FAIL == 2
        assert PollStatus.INVALID_PROCESS == 3
        assert PollStatus.INVALID_PYTHON == 4

    def test_repr(self):
        assert repr(PollStatus.OK) == "<PollStatus.OK: 1>"
