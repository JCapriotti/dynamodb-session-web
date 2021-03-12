from dynamodb_session import SessionCore


def test_default_settings():
    expected_byte_length = 32
    # Base64 of each byte is approximately 1.3 characters
    expected_sid_min_length = expected_byte_length * 1.2
    expected_sid_max_length = expected_byte_length * 1.4
    o = SessionCore()

    assert o.sid_byte_length == 32
    assert expected_sid_min_length < len(o.session_id) < expected_sid_max_length
    assert o.table_name == 'app_session'
    assert o.ttl == 7200
    assert len(o.loggable_sid) == 128
    assert o.dynamodb_endpoint_url is None
