import pytest
from dynamodb_session_web import SessionManager, SessionDictInstance, SessionInstanceBase


class TestSessionInstance:
    class ChildClass(SessionInstanceBase):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            pass

        def deserialize(self, data):
            pass

        def serialize(self):
            pass

    def test_default_settings(self):
        o = self.ChildClass()

        assert o.session_id is None
        assert o.idle_timeout_seconds == 7200
        assert o.absolute_timeout_seconds == 43200

    def test_overridden_settings(self):
        expected_session_id = 1
        expected_idle_timeout = 4
        expected_absolute_timeout = 5

        o = self.ChildClass(
            session_id=expected_session_id,
            idle_timeout_seconds=expected_idle_timeout,
            absolute_timeout_seconds=expected_absolute_timeout,
        )

        assert o.session_id == expected_session_id
        assert o.idle_timeout_seconds == expected_idle_timeout
        assert o.absolute_timeout_seconds == expected_absolute_timeout

    def test_non_int_idle_timeout_throws(self):
        with pytest.raises(ValueError):
            self.ChildClass(idle_timeout_seconds='a')

    def test_non_int_absolute_timeout_throws(self):
        with pytest.raises(ValueError):
            self.ChildClass(absolute_timeout_seconds='a')


class TestSessionCore:
    def test_default_settings(self):
        o = SessionManager(SessionDictInstance)

        assert o.sid_byte_length == 32
        assert o.table_name == 'app_session'
        assert o.endpoint_url is None

    @pytest.mark.usefixtures('mock_dynamo_set')
    def test_create(self):
        # Base64 of each byte is approximately 1.3 characters
        expected_sid_min_length = 32 * 1.2
        expected_sid_max_length = 32 * 1.4

        core_object = SessionManager(SessionDictInstance)
        instance_object = core_object.create()
        instance_object.test_m = 'f'
        actual_sid_length = len(instance_object.session_id)

        assert type(instance_object) is SessionDictInstance
        assert expected_sid_min_length < actual_sid_length < expected_sid_max_length

    @pytest.mark.usefixtures('mock_dynamo_set')
    def test_overridden_settings(self):
        expected_sid_byte_length = 1
        expected_table_name = 'some name'
        expected_dynamodb_endpoint_url = 'some URL'

        o = SessionManager(
            SessionDictInstance,
            sid_byte_length=expected_sid_byte_length,
            table_name=expected_table_name,
            endpoint_url=expected_dynamodb_endpoint_url,
        )

        assert o.sid_byte_length == expected_sid_byte_length
        assert o.table_name == expected_table_name
        assert o.endpoint_url == expected_dynamodb_endpoint_url
        assert type(o.create()) == SessionDictInstance
