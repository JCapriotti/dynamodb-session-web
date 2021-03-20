from datetime import datetime, timezone

import pytest
from dynamodb_session_web import expiration_datetime
from pytest import param


EIGHT_AM = int(datetime(2021, 3, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp())
FIVE_PM = int(datetime(2021, 3, 1, 17, 0, 0, tzinfo=timezone.utc).timestamp())

TWO_HOURS = 7200
TWELVE_HOURS = 43200


@pytest.mark.parametrize(
    'idle_timeout, absolute_timeout, created, accessed, expected', [
        param(TWO_HOURS, TWELVE_HOURS, 'Mar 1 2021, 5 AM', 'Mar 1 2021, 6 AM', EIGHT_AM, id='Idle expires before absolute'),
        param(TWO_HOURS, TWELVE_HOURS, 'Mar 1 2021, 5 AM', 'Mar 1 2021, 4 PM', FIVE_PM, id='Absolute causes expiration'),
    ]
)
def test_expiration(idle_timeout, absolute_timeout, created, accessed, expected):
    dt_format = '%b %d %Y, %I %p'
    created_dt = datetime.strptime(created, dt_format).replace(tzinfo=timezone.utc)
    accessed_dt = datetime.strptime(accessed, dt_format).replace(tzinfo=timezone.utc)

    actual = expiration_datetime(idle_timeout, absolute_timeout, created_dt.isoformat(), accessed_dt.isoformat())

    assert actual == expected


@pytest.mark.parametrize(
    'idle_timeout, absolute_timeout, created, accessed, expected', [
        param(TWO_HOURS, TWELVE_HOURS, 'Mar 1 2021, 5 AM', 'Mar 1 2021, 4 PM', FIVE_PM),
    ]
)
def test_expiration_created_must_be_utc(idle_timeout, absolute_timeout, created, accessed, expected):
    dt_format = '%b %d %Y, %I %p'
    created_dt = datetime.strptime(created, dt_format)
    accessed_dt = datetime.strptime(accessed, dt_format).replace(tzinfo=timezone.utc)

    with pytest.raises(ValueError, match='created'):
        expiration_datetime(idle_timeout, absolute_timeout, created_dt.isoformat(), accessed_dt.isoformat())


@pytest.mark.parametrize(
    'idle_timeout, absolute_timeout, created, accessed, expected', [
        param(TWO_HOURS, TWELVE_HOURS, 'Mar 1 2021, 5 AM', 'Mar 1 2021, 4 PM', FIVE_PM),
    ]
)
def test_expiration_accessed_must_be_utc(idle_timeout, absolute_timeout, created, accessed, expected):
    dt_format = '%b %d %Y, %I %p'
    created_dt = datetime.strptime(created, dt_format).replace(tzinfo=timezone.utc)
    accessed_dt = datetime.strptime(accessed, dt_format)

    with pytest.raises(ValueError, match='accessed'):
        expiration_datetime(idle_timeout, absolute_timeout, created_dt.isoformat(), accessed_dt.isoformat())
