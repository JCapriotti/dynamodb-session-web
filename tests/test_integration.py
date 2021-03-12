from datetime import datetime, timedelta, timezone

import pytest
from .helpers import create_test_session, get_dynamo_record, mock_current_timestamp, mock_current_datetime
from dynamodb_session import SessionNotFoundError, DEFAULT_TTL

future_timestamp = int((datetime.utcnow() + timedelta(days=300)).timestamp())


def test_dictionary_save_load():
    test_data = {'foo': 'bar'}
    session = create_test_session()

    session.save(test_data)
    actual_data = session.load()

    assert actual_data == test_data


def test_empty_session_saves_loads():
    session = create_test_session()

    session.save()
    actual_data = session.load()

    assert actual_data == {}


def test_new_session_load_raises():
    session = create_test_session()

    with pytest.raises(SessionNotFoundError) as exc:
        session.load()

    assert exc.value.loggable_sid == session.loggable_sid


def test_expired_ttl_session_raises(mocker):
    session = create_test_session()
    session.save()

    mock_current_timestamp(mocker, future_timestamp)
    with pytest.raises(SessionNotFoundError) as exc:
        session.load()

    assert exc.value.loggable_sid == session.loggable_sid


def test_save_sets_ttl_and_accessed(mocker):
    session = create_test_session()
    initial_timestamp = 3000
    initial_time_string = datetime(1977, 12, 28, 12, 40, 0, 0)
    mock_current_timestamp(mocker, initial_timestamp)
    mock_current_datetime(mocker, initial_time_string)

    session.save()
    actual_record = get_dynamo_record(session.session_id, session.table_name)
    assert actual_record['ttl'] == initial_timestamp + DEFAULT_TTL
    assert actual_record['accessed'] == initial_time_string.isoformat()


def test_get_updates_accessed_ttl(mocker):
    session = create_test_session()
    initial_timestamp = 3000
    initial_time_string = datetime(1977, 12, 28, 12, 40, 0, 0)
    mock_current_timestamp(mocker, initial_timestamp)
    mock_current_datetime(mocker, initial_time_string)
    session.save()

    actual_record = get_dynamo_record(session.session_id, session.table_name)
    assert actual_record['ttl'] == initial_timestamp + DEFAULT_TTL
    assert actual_record['accessed'] == initial_time_string.isoformat()

    new_timestamp = 8000
    new_time_string = datetime(2020, 3, 11, 0, 0, 0, 0)
    mock_current_timestamp(mocker, new_timestamp)
    mock_current_datetime(mocker, new_time_string)
    session.load()

    actual_record = get_dynamo_record(session.session_id, session.table_name)
    assert actual_record['ttl'] == new_timestamp + DEFAULT_TTL
    assert actual_record['accessed'] == new_time_string.isoformat()


def test_clear_removes_record():
    session = create_test_session()
    session.save()

    # Check that it was saved first
    actual_record = get_dynamo_record(session.session_id, session.table_name)
    assert actual_record['id'] == session.session_id

    session.clear()

    actual_record = get_dynamo_record(session.session_id, session.table_name)
    assert actual_record is None


def test_actual_current_timestamps_are_within_two_seconds_of_now():
    expected_datetime = datetime.now(tz=timezone.utc)
    expected_ttl = int(datetime.now(tz=timezone.utc).timestamp()) + DEFAULT_TTL
    session = create_test_session()
    session.save()

    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert int(actual_record['ttl']) - expected_ttl < 2
    assert datetime.fromisoformat(actual_record['accessed']) - expected_datetime < timedelta(seconds=2)
