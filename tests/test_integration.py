import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import pytest
from itsdangerous.exc import BadSignature
from pytest import param

from dynamodb_session_web import NullSessionInstance, SessionManager, SessionInstanceBase
from .utility import create_session_manager, get_dynamo_record, LOCAL_ENDPOINT, mock_current_datetime, str_param

DEFAULT_IDLE_TIMEOUT = 7200  # two hours
DEFAULT_ABSOLUTE_TIMEOUT = 43200  # twelve hours

FUTURE_DATETIME = datetime.utcnow() + timedelta(days=300)
FOUR_HOURS_IN_SECONDS = 14400
SIX_HOURS_IN_SECONDS = 21600
NINE_AM = int(datetime(2021, 3, 1, 9, 0, 0, tzinfo=timezone.utc).timestamp())
TEN_AM = int(datetime(2021, 3, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp())
ELEVEN_AM = int(datetime(2021, 3, 1, 11, 0, 0, tzinfo=timezone.utc).timestamp())
FRIENDLY_DT_FORMAT = '%b %d %Y, %I %p'

# pylint: disable=no-self-use
# pylint: disable=too-many-arguments


class TestIntegration:

    @pytest.fixture(autouse=True)
    def _dynamodb_local(self, dynamodb_table):  # pylint: disable=unused-argument
        return

    def test_create_doesnt_save(self):
        session = create_session_manager()
        session_instance = session.create()

        assert get_dynamo_record(session_instance.session_id) is None

    def test_dictionary_save_load(self):
        expected_key = str_param()
        expected_value = str_param()

        session = create_session_manager()
        session_instance = session.create()
        session_instance[expected_key] = expected_value
        session.save(session_instance)

        actual_data = session.load(session_instance.session_id)
        assert actual_data[expected_key] == expected_value

    def test_hmac_sid(self):
        expected_key = str_param()
        expected_value = str_param()

        session = create_session_manager(sid_keys=['foo'])
        session_instance = session.create()
        session_instance[expected_key] = expected_value
        session.save(session_instance)

        actual_data = session.load(session_instance.session_id)
        assert actual_data[expected_key] == expected_value

    def test_hmac_sid_invalid(self):
        expected_key = str_param()
        expected_value = str_param()

        session = create_session_manager(sid_keys=['foo'])
        session_instance = session.create()
        session_instance[expected_key] = expected_value
        session.save(session_instance)

        with pytest.raises(BadSignature):
            session.load('my string.wh6tMHxLgJqB6oY1uT73iMlyrOA')

    def test_example_custom_class(self):
        """ Test/Example code showing save/load with a custom session data class """
        @dataclass
        class MySession(SessionInstanceBase):
            fruit: str = ''
            color: str = ''

            def __init__(self, **kwargs):
                super().__init__(**kwargs)

            def deserialize(self, data):
                data_dict = json.loads(data)
                self.fruit = data_dict['fruit']
                self.color = data_dict['color']

            def serialize(self):
                return json.dumps(asdict(self))

        session = SessionManager(MySession, endpoint_url=LOCAL_ENDPOINT)
        initial_data = session.create()
        initial_data.fruit = 'apple'
        initial_data.color = 'red'

        session.save(initial_data)
        loaded_data = session.load(initial_data.session_id)
        session.clear(initial_data.session_id)

        assert loaded_data.fruit == initial_data.fruit
        assert loaded_data.color == initial_data.color

    def test_load_loads_instance_timeouts(self):
        """
        Test that a new SessionCore instance will load timeouts from a previously saved session.
        """
        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        session = create_session_manager()

        initial_session_data = session.create_and_save(
            idle_timeout_seconds=expected_idle_timeout,
            absolute_timeout_seconds=expected_absolute_timeout)

        new_session = create_session_manager()
        actual_data = new_session.load(initial_session_data.session_id)

        assert actual_data.idle_timeout_seconds == expected_idle_timeout
        assert actual_data.absolute_timeout_seconds == expected_absolute_timeout

    def test_load_loads_manager_overridden_timeouts(self):
        """
        Test that a new SessionCore instance will load timeouts from a previously saved session.
        """
        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        session = create_session_manager(idle_timeout_seconds=expected_idle_timeout,
                                         absolute_timeout_seconds=expected_absolute_timeout)

        initial_session_data = session.create_and_save()

        actual_data = session.load(initial_session_data.session_id)

        assert actual_data.idle_timeout_seconds == expected_idle_timeout
        assert actual_data.absolute_timeout_seconds == expected_absolute_timeout

    def test_random_session_id_load_returns_null_session(self):
        session = create_session_manager()
        sid = 'some_unknown_session_id'
        expected_loggable_sid = '4ee055b82b9f592c6a5a0bc8d2a0b59890b97c93cc68db0f6738df05c37089ab' \
                                'a958d405b82ec604209074a7a8d5b9fc55211b6ef1ed9e7832a58b05abadb04b'

        actual = session.load(sid)

        assert isinstance(actual, NullSessionInstance)
        assert actual.session_id == sid
        assert actual.loggable_session_id == expected_loggable_sid

    def test_expired_session_returns_null_session(self, mocker):
        session = create_session_manager()
        session_instance = session.create_and_save()
        expected_session_id = session_instance.session_id
        expected_loggable_id = hashlib.sha512(expected_session_id.encode()).hexdigest()
        mock_current_datetime(mocker, FUTURE_DATETIME)

        actual = session.load(session_instance.session_id)

        assert isinstance(actual, NullSessionInstance)
        assert actual.session_id == expected_session_id
        assert actual.loggable_session_id == expected_loggable_id

    def test_save_sets_all_expected_attributes(self, mocker):
        session = create_session_manager()
        initial_datetime = datetime(1977, 12, 28, 12, 40, 0, 0, tzinfo=timezone.utc)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create_and_save()
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
            self, mocker, created, accessed, expected_expires_post_created,
            expected_expires_post_accessed):
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

        session = create_session_manager()
        mock_current_datetime(mocker, initial_dt)

        # Create Test
        session_instance = session.create_and_save(idle_timeout_seconds=FOUR_HOURS_IN_SECONDS,
                                                   absolute_timeout_seconds=SIX_HOURS_IN_SECONDS)
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
            self, mocker, created, accessed, expected_expires_post_created,
            expected_expires_post_accessed):
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

        session = create_session_manager()
        mock_current_datetime(mocker, initial_dt)

        # Create Test
        session_instance = session.create_and_save(idle_timeout_seconds=FOUR_HOURS_IN_SECONDS,
                                                   absolute_timeout_seconds=SIX_HOURS_IN_SECONDS)
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
        session = create_session_manager()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0, tzinfo=timezone.utc)
        mock_current_datetime(mocker, initial_datetime)

        session_instance = session.create_and_save(idle_timeout_seconds=expected_idle_timeout,
                                                   absolute_timeout_seconds=expected_absolute_timeout)
        actual_record = get_dynamo_record(session_instance.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
        assert actual_record['idle_timeout'] == expected_idle_timeout
        assert actual_record['absolute_timeout'] == expected_absolute_timeout

    def test_changed_timeouts_are_allowed(self, mocker):
        session = create_session_manager()
        initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0, tzinfo=timezone.utc)
        mock_current_datetime(mocker, initial_datetime)

        first_session_data = session.create_and_save()
        actual_record = get_dynamo_record(first_session_data.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT

        expected_idle_timeout = 10
        expected_absolute_timeout = 20
        new_session = create_session_manager()
        new_session_data = new_session.load(first_session_data.session_id)
        new_session_data.idle_timeout_seconds = expected_idle_timeout
        new_session_data.absolute_timeout_seconds = expected_absolute_timeout

        new_session.save(new_session_data)
        actual_record = get_dynamo_record(first_session_data.session_id)

        assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
        assert actual_record['idle_timeout'] == expected_idle_timeout
        assert actual_record['absolute_timeout'] == expected_absolute_timeout

    def test_clear_removes_record(self):
        session = create_session_manager()
        session_instance = session.create_and_save()

        # Check that it was saved first
        actual_record = get_dynamo_record(session_instance.session_id)
        assert actual_record['id'] == session_instance.session_id

        session.clear(session_instance.session_id)

        actual_record = get_dynamo_record(session_instance.session_id)
        assert actual_record is None

    def test_actual_current_timestamps_are_within_two_seconds_of_now(self):
        expected_datetime = datetime.now(tz=timezone.utc)
        expected_ttl = int(datetime.now(tz=timezone.utc).timestamp()) + DEFAULT_ABSOLUTE_TIMEOUT
        session = create_session_manager()
        session_instance = session.create_and_save()

        actual_record = get_dynamo_record(session_instance.session_id)

        assert int(actual_record['expires']) - expected_ttl < 2
        assert datetime.fromisoformat(actual_record['accessed']) - expected_datetime < timedelta(seconds=2)
