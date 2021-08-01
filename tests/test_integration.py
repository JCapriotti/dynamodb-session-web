from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from .helpers import create_test_session, get_dynamo_record, mock_current_datetime
from dynamodb_session_web import NullSessionInstance, SessionDictInstance, SessionInstanceBase, \
    DEFAULT_IDLE_TIMEOUT, DEFAULT_ABSOLUTE_TIMEOUT

future_datetime = datetime.utcnow() + timedelta(days=300)

TEST_KEY = 'foo'
TEST_VALUE = 'bar'


def create_test_data(test_data: Optional[SessionInstanceBase] = None):
    if test_data is None:
        test_data = SessionDictInstance()
    test_data[TEST_KEY] = TEST_VALUE
    return test_data


class TestIntegration:

    @pytest.fixture(autouse=True)
    def _dynamodb_local(self, dynamodb_table):
        return

    def test_dictionary_save_load(self):
        session = create_test_session()
        test_data = create_test_data(session.create())

        session.save(test_data)
        actual_data = session.load(test_data.session_id)
        assert actual_data[TEST_KEY] == TEST_VALUE

    def test_load_loads_timeouts(self):
        """
        Test that a new SessionCore instance will load timeouts from a previously saved session.
        """
        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        session = create_test_session()

        initial_session_data = create_test_data(session.create(
            idle_timeout=expected_idle_timeout,
            absolute_timeout=expected_absolute_timeout)
        )
        new_session = create_test_session()
        actual_data = new_session.load(initial_session_data.session_id)

        assert actual_data.idle_timeout == expected_idle_timeout
        assert actual_data.absolute_timeout == expected_absolute_timeout

    def test_random_session_id_load_returns_null_session(self):
        session = create_test_session()
        sid = 'some_unknown_session_id'

        actual = session.load(sid)

        assert isinstance(actual, NullSessionInstance)
        assert actual.session_id == sid

    def test_expired_session_returns_null_session(self, mocker):
        session = create_test_session()
        session_instance = session.create()
        mock_current_datetime(mocker, future_datetime)

        actual = session.load(session_instance.session_id)

        assert isinstance(actual, NullSessionInstance)
        assert actual.session_id == session_instance.session_id

    def test_save_sets_all_expected_attributes(self, mocker):
        session = create_test_session()
        initial_datetime = datetime(1977, 12, 28, 12, 40, 0, 0)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create()
        session.save(session_instance)
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
        assert actual_record['accessed'] == initial_datetime.isoformat()
        assert actual_record['created'] == initial_datetime.isoformat()
        assert actual_record['idle_timeout'] == DEFAULT_IDLE_TIMEOUT
        assert actual_record['absolute_timeout'] == DEFAULT_ABSOLUTE_TIMEOUT

    def test_get_updates_accessed_expires_but_not_created(self, mocker):
        session = create_test_session()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create()
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
        assert actual_record['accessed'] == initial_datetime.isoformat()
        assert actual_record['created'] == initial_datetime.isoformat()

        new_datetime = datetime(2020, 3, 11, 1, 0, 0, 0)
        mock_current_datetime(mocker, new_datetime)

        session.load(session_instance.session_id)
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(new_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
        assert actual_record['accessed'] == new_datetime.isoformat()
        assert actual_record['created'] == initial_datetime.isoformat()

    def test_new_session_object_uses_saved_timeouts_not_defaults(self, mocker):
        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        session = create_test_session()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create(
            idle_timeout=expected_idle_timeout,
            absolute_timeout=expected_absolute_timeout
        )
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout

        new_session = create_test_session()
        new_session.load(session_instance.session_id)
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
        assert actual_record['idle_timeout'] == expected_idle_timeout
        assert actual_record['absolute_timeout'] == expected_absolute_timeout

    def test_changed_timeouts_are_allowed(self, mocker):
        session = create_test_session()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0)
        mock_current_datetime(mocker, initial_datetime)

        first_session_data = session.create()
        actual_record = get_dynamo_record(first_session_data.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT

        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        new_session = create_test_session()
        new_session_data = new_session.load(first_session_data.session_id)
        new_session_data.idle_timeout = expected_idle_timeout
        new_session_data.absolute_timeout = expected_absolute_timeout

        new_session.save(new_session_data)
        actual_record = get_dynamo_record(first_session_data.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
        assert actual_record['idle_timeout'] == expected_idle_timeout
        assert actual_record['absolute_timeout'] == expected_absolute_timeout

    def test_clear_removes_record(self):
        session = create_test_session()
        session_instance = session.create()

        # Check that it was saved first
        actual_record = get_dynamo_record(session_instance.session_id)
        assert actual_record['id'] == session_instance.session_id

        session.clear(session_instance.session_id)

        actual_record = get_dynamo_record(session_instance.session_id)
        assert actual_record is None

    def test_actual_current_timestamps_are_within_two_seconds_of_now(self):
        expected_datetime = datetime.now(tz=timezone.utc)
        expected_ttl = int(datetime.now(tz=timezone.utc).timestamp()) + DEFAULT_IDLE_TIMEOUT
        session = create_test_session()
        session_instance = session.create()

        actual_record = get_dynamo_record(session_instance.session_id)

        assert int(actual_record['expires']) - expected_ttl < 2
        assert datetime.fromisoformat(actual_record['accessed']) - expected_datetime < timedelta(seconds=2)
