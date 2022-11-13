import pytest
from dynamodb_session_web import SessionManager, SessionDictInstance


# noinspection PyClassHasNoInit
class TestSessionInstance:
    def test_default_settings(self):
        actual = SessionDictInstance()

        assert actual.session_id == ''
        assert actual.idle_timeout_seconds == 7200
        assert actual.absolute_timeout_seconds == 43200

    def test_overridden_settings(self):
        expected_session_id = 1
        expected_idle_timeout = 4
        expected_absolute_timeout = 5

        actual = SessionDictInstance(
            session_id=expected_session_id,
            idle_timeout_seconds=expected_idle_timeout,
            absolute_timeout_seconds=expected_absolute_timeout,
        )

        assert actual.session_id == expected_session_id
        assert actual.idle_timeout_seconds == expected_idle_timeout
        assert actual.absolute_timeout_seconds == expected_absolute_timeout

    def test_non_int_idle_timeout_throws(self):
        with pytest.raises(ValueError):
            SessionDictInstance(idle_timeout_seconds='a')

    def test_non_int_absolute_timeout_throws(self):
        with pytest.raises(ValueError):
            SessionDictInstance(absolute_timeout_seconds='a')


class TestSessionCore:
    def test_default_settings(self):
        actual = SessionManager(SessionDictInstance)

        assert actual.sid_byte_length == 32
        assert actual.table_name == 'app_session'
        assert actual.endpoint_url is None
        assert actual.region_name is None

    def test_create(self):
        # Base64 of each byte is approximately 1.3 characters
        expected_sid_min_length = 32 * 1.2
        expected_sid_max_length = 32 * 1.4

        core_object = SessionManager(SessionDictInstance)
        instance_object = core_object.create()
        instance_object.test_m = 'f'
        actual_sid_length = len(instance_object.session_id)

        assert isinstance(instance_object, SessionDictInstance)
        assert expected_sid_min_length < actual_sid_length < expected_sid_max_length

    def test_overridden_settings(self):
        expected_sid_byte_length = 1
        expected_table_name = 'some name'
        expected_dynamodb_endpoint_url = 'some URL'
        expected_dynamodb_region_name = 'us-east-1'
        expected_idle_timeout = 4
        expected_absolute_timeout = 5

        actual = SessionManager(
            SessionDictInstance,
            sid_byte_length=expected_sid_byte_length,
            table_name=expected_table_name,
            endpoint_url=expected_dynamodb_endpoint_url,
            region_name=expected_dynamodb_region_name,
            idle_timeout_seconds=expected_idle_timeout,
            absolute_timeout_seconds=expected_absolute_timeout
        )

        assert actual.sid_byte_length == expected_sid_byte_length
        assert actual.table_name == expected_table_name
        assert actual.endpoint_url == expected_dynamodb_endpoint_url
        assert actual.region_name == expected_dynamodb_region_name
        assert actual._idle_timeout == expected_idle_timeout  # pylint: disable=protected-access
        assert actual._absolute_timeout == expected_absolute_timeout  # pylint: disable=protected-access
        assert isinstance(actual.create(), SessionDictInstance)
