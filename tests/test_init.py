import pytest
from dynamodb_session_web import SessionCore


def test_default_settings():
    expected_byte_length = 32
    # Base64 of each byte is approximately 1.3 characters
    expected_sid_min_length = expected_byte_length * 1.2
    expected_sid_max_length = expected_byte_length * 1.4
    o = SessionCore()

    assert o.sid_byte_length == 32
    assert expected_sid_min_length < len(o.session_id) < expected_sid_max_length
    assert o.table_name == 'app_session'
    assert o.idle_timeout == 7200
    assert o.absolute_timeout == 43200
    assert len(o.loggable_sid) == 128
    assert o.dynamodb_endpoint_url is None


def test_non_int_idle_timeout_throws():
    with pytest.raises(ValueError):
        SessionCore(idle_timeout='a')


def test_non_int_absolute_timeout_throws():
    with pytest.raises(ValueError):
        SessionCore(absolute_timeout='a')


def test_overridden_settings():
    expected_sid_byte_length = 1
    expected_session_id = '2'
    expected_table_name = 3
    expected_idle_timeout = 4
    expected_absolute_timeout = 5
    expected_dynamodb_endpoint_url = 6

    o = SessionCore(sid_byte_length=expected_sid_byte_length,
                    session_id=expected_session_id,
                    table_name=expected_table_name,
                    idle_timeout=expected_idle_timeout,
                    absolute_timeout=expected_absolute_timeout,
                    dynamodb_endpoint_url=expected_dynamodb_endpoint_url)

    assert o.sid_byte_length == expected_sid_byte_length
    assert o.session_id == expected_session_id
    assert o.table_name == expected_table_name
    assert o.idle_timeout == expected_idle_timeout
    assert o.absolute_timeout == expected_absolute_timeout
    assert o.dynamodb_endpoint_url == expected_dynamodb_endpoint_url


@pytest.mark.parametrize(
    'parameter',
    ['ttl', 'session_id_bytes']
)
def test_unexpected_parameters_raise(parameter):
    """
    This is a safety-check, mostly for retired parameters (if any)
    """
    kw = {
        parameter: 'foo'
    }
    with pytest.raises(RuntimeError):
        SessionCore(**kw)
