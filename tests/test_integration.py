from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from dynamodb_session_web import NullSessionInstance, SessionDictInstance, SessionInstanceBase, \
    DEFAULT_IDLE_TIMEOUT, DEFAULT_ABSOLUTE_TIMEOUT
from pytest import param
from .helpers import create_test_session, get_dynamo_record, mock_current_datetime

FUTURE_DATETIME = datetime.utcnow() + timedelta(days=300)
EXPECTED_KEY = 'foo'
EXPECTED_VALUE = 'bar'
FOUR_HOURS_IN_SECONDS = 14400
SIX_HOURS_IN_SECONDS = 21600
NINE_AM = int(datetime(2021, 3, 1, 9, 0, 0, tzinfo=timezone.utc).timestamp())
TEN_AM = int(datetime(2021, 3, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp())
ELEVEN_AM = int(datetime(2021, 3, 1, 11, 0, 0, tzinfo=timezone.utc).timestamp())
FRIENDLY_DT_FORMAT = '%b %d %Y, %I %p'


def create_test_data(test_data: Optional[SessionInstanceBase] = None):
    if test_data is None:
        test_data = SessionDictInstance()
    test_data[EXPECTED_KEY] = EXPECTED_VALUE
    return test_data


class TestIntegration:

    @pytest.fixture(autouse=True)
    def _dynamodb_local(self, dynamodb_table):
        return

    def test_dictionary_save_load(self):
        import os
        x = os.getcwd()
        session = create_test_session()
        test_data = create_test_data(session.create())

        session.save(test_data)
        actual_data = session.load(test_data.session_id)
        assert actual_data[EXPECTED_KEY] == EXPECTED_VALUE

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
        mock_current_datetime(mocker, FUTURE_DATETIME)

        actual = session.load(session_instance.session_id)

        assert isinstance(actual, NullSessionInstance)
        assert actual.session_id == session_instance.session_id

    def test_save_sets_all_expected_attributes(self, mocker):
        session = create_test_session()
        initial_datetime = datetime(1977, 12, 28, 12, 40, 0, 0, tzinfo=timezone.utc)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create()
        session.save(session_instance)
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
        assert actual_record['accessed'] == initial_datetime.isoformat()
        assert actual_record['created'] == initial_datetime.isoformat()
        assert actual_record['idle_timeout'] == DEFAULT_IDLE_TIMEOUT
        assert actual_record['absolute_timeout'] == DEFAULT_ABSOLUTE_TIMEOUT

    @pytest.mark.parametrize(
        'created, accessed, expected_expires_post_created, expected_expires_post_accessed', [
            param('Mar 1 2021, 5 AM', 'Mar 1 2021, 6 AM', NINE_AM, TEN_AM, id='Idle expires before absolute'),
            param('Mar 1 2021, 5 AM', 'Mar 1 2021, 8 AM', NINE_AM, ELEVEN_AM, id='Absolute causes expiration'),
        ]
    )
    def test_created_accessed_expires_value_for_create_load(
            self, mocker, created, accessed, expected_expires_post_created, expected_expires_post_accessed):
        """
        Tests that accessing a session an hour after creation updates the `accessed` field, but `created` is not
        affected. `expires` *may* be updated, depending on how close the update is to the timeouts.

        IMPORTANT - Timeouts used are:
            IDLE     - 4 hours
            ABSOLUTE - 6 hours

        The inputs are roughly the same as in the `test_expiration.test_expiration` test, here we're just making sure
        the values are persisted and used.
        """
        initial_dt = datetime.strptime(created, FRIENDLY_DT_FORMAT).replace(tzinfo=timezone.utc)
        accessed_dt = datetime.strptime(accessed, FRIENDLY_DT_FORMAT).replace(tzinfo=timezone.utc)
        expected_created = initial_dt.isoformat()

        session = create_test_session()
        mock_current_datetime(mocker, initial_dt)

        # Create Test
        session_instance = session.create(idle_timeout=FOUR_HOURS_IN_SECONDS, absolute_timeout=SIX_HOURS_IN_SECONDS)
        self.assert_actual_record_values(session_instance.session_id,
                                         exp_created=expected_created,
                                         exp_expired=expected_expires_post_created,
                                         exp_accessed=initial_dt.isoformat())

        # Load Test for new datetime
        mock_current_datetime(mocker, accessed_dt)
        session.load(session_instance.session_id)
        self.assert_actual_record_values(session_instance.session_id,
                                         exp_created=expected_created,
                                         exp_expired=expected_expires_post_accessed,
                                         exp_accessed=accessed_dt.isoformat())

    @pytest.mark.parametrize(
        'created, accessed, expected_expires_post_created, expected_expires_post_accessed', [
            param('Mar 1 2021, 5 AM', 'Mar 1 2021, 6 AM', NINE_AM, TEN_AM, id='Idle expires before absolute'),
            param('Mar 1 2021, 5 AM', 'Mar 1 2021, 8 AM', NINE_AM, ELEVEN_AM, id='Absolute causes expiration'),
        ]
    )
    def test_created_accessed_expires_value_for_create_save(
            self, mocker, created, accessed, expected_expires_post_created, expected_expires_post_accessed):
        """
        Tests that accessing a session an hour after creation updates the `accessed` field, but `created` is not
        affected. `expires` *may* be updated, depending on how close the update is to the timeouts.

        IMPORTANT - Timeouts used are:
            IDLE     - 4 hours
            ABSOLUTE - 6 hours

        The inputs are roughly the same as in the `test_expiration.test_expiration` test, here we're just making sure
        the values are persisted and used.
        """
        initial_dt = datetime.strptime(created, FRIENDLY_DT_FORMAT).replace(tzinfo=timezone.utc)
        accessed_dt = datetime.strptime(accessed, FRIENDLY_DT_FORMAT).replace(tzinfo=timezone.utc)
        expected_created = initial_dt.isoformat()

        session = create_test_session()
        mock_current_datetime(mocker, initial_dt)

        # Create Test
        session_instance = session.create(idle_timeout=FOUR_HOURS_IN_SECONDS, absolute_timeout=SIX_HOURS_IN_SECONDS)
        self.assert_actual_record_values(session_instance.session_id,
                                         exp_created=expected_created,
                                         exp_expired=expected_expires_post_created,
                                         exp_accessed=initial_dt.isoformat())

        # Load Test for new datetime
        mock_current_datetime(mocker, accessed_dt)
        session.save(session_instance)
        self.assert_actual_record_values(session_instance.session_id,
                                         exp_created=expected_created,
                                         exp_expired=expected_expires_post_accessed,
                                         exp_accessed=accessed_dt.isoformat())

    @staticmethod
    def assert_actual_record_values(session_id, exp_created, exp_expired, exp_accessed):
        actual_record = get_dynamo_record(session_id)

        assert actual_record['created'] == exp_created
        assert actual_record['expires'] == exp_expired
        assert actual_record['accessed'] == exp_accessed

    def test_new_session_object_uses_saved_timeouts_not_defaults(self, mocker):
        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        session = create_test_session()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0, tzinfo=timezone.utc)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create(
            idle_timeout=expected_idle_timeout,
            absolute_timeout=expected_absolute_timeout
        )
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
        assert actual_record['idle_timeout'] == expected_idle_timeout
        assert actual_record['absolute_timeout'] == expected_absolute_timeout

    def test_changed_timeouts_are_allowed(self, mocker):
        session = create_test_session()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0, tzinfo=timezone.utc)
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
        expected_ttl = int(datetime.now(tz=timezone.utc).timestamp()) + DEFAULT_ABSOLUTE_TIMEOUT
        session = create_test_session()
        session_instance = session.create()

        actual_record = get_dynamo_record(session_instance.session_id)

        assert int(actual_record['expires']) - expected_ttl < 2
        assert datetime.fromisoformat(actual_record['accessed']) - expected_datetime < timedelta(seconds=2)
