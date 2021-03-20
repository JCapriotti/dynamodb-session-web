from datetime import datetime, timedelta, timezone

import pytest
from .helpers import create_test_session, get_dynamo_record, mock_current_datetime
from dynamodb_session_web import SessionNotFoundError, DEFAULT_IDLE_TIMEOUT, DEFAULT_ABSOLUTE_TIMEOUT

future_datetime = datetime.utcnow() + timedelta(days=300)


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


def test_load_loads_timeouts():
    expected_idle_timeout = 10
    expected_absolute_timeout = 20
    session = create_test_session(idle_timeout=expected_idle_timeout, absolute_timeout=expected_absolute_timeout)

    session.save()
    new_session = create_test_session(session_id=session.session_id)
    new_session.load()

    assert new_session.idle_timeout == expected_idle_timeout
    assert new_session.absolute_timeout == expected_absolute_timeout


def test_new_session_load_raises():
    session = create_test_session()

    with pytest.raises(SessionNotFoundError) as exc:
        session.load()

    assert exc.value.loggable_sid == session.loggable_sid


def test_expired_session_raises(mocker):
    session = create_test_session()
    session.save()

    mock_current_datetime(mocker, future_datetime)
    with pytest.raises(SessionNotFoundError) as exc:
        session.load()

    assert exc.value.loggable_sid == session.loggable_sid


def test_save_sets_all_expected_attributes(mocker):
    session = create_test_session()
    initial_datetime = datetime(1977, 12, 28, 12, 40, 0, 0)
    mock_current_datetime(mocker, initial_datetime)

    session.save()
    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
    assert actual_record['accessed'] == initial_datetime.isoformat()
    assert actual_record['created'] == initial_datetime.isoformat()
    assert actual_record['idle_timeout'] == DEFAULT_IDLE_TIMEOUT
    assert actual_record['absolute_timeout'] == DEFAULT_ABSOLUTE_TIMEOUT


def test_get_updates_accessed_expires_but_not_created(mocker):
    session = create_test_session()
    initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0)
    mock_current_datetime(mocker, initial_datetime)

    session.save()
    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
    assert actual_record['accessed'] == initial_datetime.isoformat()
    assert actual_record['created'] == initial_datetime.isoformat()

    new_datetime = datetime(2020, 3, 11, 1, 0, 0, 0)
    mock_current_datetime(mocker, new_datetime)

    session.load()
    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert actual_record['expires'] == int(new_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT
    assert actual_record['accessed'] == new_datetime.isoformat()
    assert actual_record['created'] == initial_datetime.isoformat()


def test_new_session_object_uses_saved_timeouts_not_defaults(mocker):
    expected_idle_timeout = 10
    expected_absolute_timeout = 20
    session = create_test_session(idle_timeout=expected_idle_timeout, absolute_timeout=expected_absolute_timeout)
    initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0)
    mock_current_datetime(mocker, initial_datetime)

    session.save()
    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout

    new_session = create_test_session(session_id=session.session_id)
    new_session.load()
    actual_record = get_dynamo_record(new_session.session_id, new_session.table_name)

    assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
    assert actual_record['idle_timeout'] == expected_idle_timeout
    assert actual_record['absolute_timeout'] == expected_absolute_timeout


def test_changed_timeouts_are_allowed(mocker):
    session = create_test_session()
    initial_datetime = datetime(2020, 3, 11, 0, 0, 0, 0)
    mock_current_datetime(mocker, initial_datetime)

    session.save()
    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert actual_record['expires'] == int(initial_datetime.timestamp()) + DEFAULT_IDLE_TIMEOUT

    expected_idle_timeout = 10
    expected_absolute_timeout = 20
    new_session = create_test_session(session_id=session.session_id)
    new_session.idle_timeout = expected_idle_timeout
    new_session.absolute_timeout = expected_absolute_timeout

    new_session.save()
    actual_record = get_dynamo_record(new_session.session_id, new_session.table_name)

    assert actual_record['expires'] == int(initial_datetime.timestamp()) + expected_idle_timeout
    assert actual_record['idle_timeout'] == expected_idle_timeout
    assert actual_record['absolute_timeout'] == expected_absolute_timeout


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
    expected_ttl = int(datetime.now(tz=timezone.utc).timestamp()) + DEFAULT_IDLE_TIMEOUT
    session = create_test_session()
    session.save()

    actual_record = get_dynamo_record(session.session_id, session.table_name)

    assert int(actual_record['expires']) - expected_ttl < 2
    assert datetime.fromisoformat(actual_record['accessed']) - expected_datetime < timedelta(seconds=2)
