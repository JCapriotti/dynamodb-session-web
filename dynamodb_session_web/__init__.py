import hashlib
import json
import secrets
from datetime import datetime, timezone

import boto3

DEFAULT_IDLE_TIMEOUT = 7200  # two hours
DEFAULT_ABSOLUTE_TIMEOUT = 43200  # twelve hours
DEFAULT_TABLE = 'app_session'
DEFAULT_SESSION_ID_BYTES = 32


def create_session_id(byte_length: int) -> str:
    return secrets.token_urlsafe(byte_length)


def current_datetime(datetime_value: datetime = None) -> datetime:
    if datetime_value is None:
        datetime_value = datetime.now(tz=timezone.utc)
    return datetime_value


def current_timestamp(datetime_value: datetime = None) -> int:
    return int(current_datetime(datetime_value).timestamp())


def expiration_datetime(idle_timeout: int, absolute_timeout: int, created: str, accessed: str) -> int:
    created_dt = datetime.fromisoformat(created)
    if created_dt.tzname() != 'UTC':
        raise ValueError("'created' must be UTC ")

    accessed_dt = datetime.fromisoformat(accessed)
    if accessed_dt.tzname() != 'UTC':
        raise ValueError("'accessed' must be UTC ")

    absolute_expiration = absolute_timeout + int(created_dt.timestamp())
    idle_expiration = idle_timeout + int(accessed_dt.timestamp())

    return min(absolute_expiration, idle_expiration)


class SessionCore:
    _boto_client = None

    def __init__(self, **kwargs):
        if 'ttl' in kwargs:
            raise RuntimeError
        if 'session_id_bytes' in kwargs:
            raise RuntimeError

        self.sid_byte_length = kwargs.get('sid_byte_length', DEFAULT_SESSION_ID_BYTES)
        self.session_id = str(kwargs.get('session_id', create_session_id(self.sid_byte_length)))
        self.table_name = kwargs.get('table_name', DEFAULT_TABLE)
        self.idle_timeout = int(kwargs.get('idle_timeout', DEFAULT_IDLE_TIMEOUT))
        self.absolute_timeout = int(kwargs.get('absolute_timeout', DEFAULT_ABSOLUTE_TIMEOUT))
        self.endpoint_url = kwargs.get('endpoint_url', None)

        self.loggable_sid = self._loggable_session_id()

    def _loggable_session_id(self):
        return hashlib.sha512(self.session_id.encode()).hexdigest()

    def load(self):
        data = self._perform_get()
        return json.loads(data)

    def save(self, data=None):
        if data is None:
            data = {}
        serialized = json.dumps(data)
        self._dynamo_set(serialized, modified=True)

    def clear(self):
        self._dynamo_remove()

    def _dynamo_remove(self):
        self.boto_client().delete_item(
            TableName=self.table_name,
            Key={'id': {'S': self.session_id}})

    def _perform_get(self):
        data = self._dynamo_get()
        self._dynamo_set(data, False)
        return data

    def _dynamo_get(self):
        res = self.boto_client().query(TableName=self.table_name,
                                       ExpressionAttributeValues={
                                           ':sid': {
                                               'S': self.session_id,
                                           },
                                           ':now': {
                                               'N': str(current_timestamp())
                                           },
                                       },
                                       KeyConditionExpression='id = :sid',
                                       FilterExpression='expires > :now',
                                       ConsistentRead=True)
        if res.get('Items') and len(res.get('Items')) == 1:
            self.idle_timeout = int(res.get('Items')[0]['idle_timeout'].get('N', DEFAULT_IDLE_TIMEOUT))
            self.absolute_timeout = int(res.get('Items')[0]['absolute_timeout'].get('N', DEFAULT_ABSOLUTE_TIMEOUT))

            if res.get('Items')[0]['data']:
                data = res.get('Items')[0]['data']
                return data.get('S', '{}')
        else:
            raise SessionNotFoundError(self.loggable_sid)

    def _dynamo_set(self, data, modified):
        current_dt = current_datetime().isoformat()
        fields = {
            'accessed': {'S': current_dt},
            'expires': {'N': str(current_timestamp() + self.idle_timeout)},
        }

        if modified:
            fields['idle_timeout'] = {'N': str(self.idle_timeout)}
            fields['absolute_timeout'] = {'N': str(self.absolute_timeout)}
            fields['data'] = {'S': data}

        attr_names = {}
        attr_values = {}
        update_expression = []
        for k, v in fields.items():
            attr = "#attr_{}".format(k)
            token = ":{}".format(k)
            update_expression.append("{} = {}".format(attr, token))
            attr_values[token] = v
            attr_names[attr] = k

        self.boto_client().update_item(TableName=self.table_name,
                                       Key={'id': {'S': self.session_id}},
                                       ExpressionAttributeNames=attr_names,
                                       ExpressionAttributeValues=attr_values,
                                       UpdateExpression='SET '
                                                        'created = if_not_exists(created, :accessed), '
                                                        '{}'.format(', '.join(update_expression)),
                                       ReturnValues='NONE')

    def boto_client(self):
        if self._boto_client is None:
            self._boto_client = boto3.client('dynamodb', endpoint_url=self.endpoint_url)

        return self._boto_client


class SessionNotFoundError(Exception):
    loggable_sid: str

    def __init__(self, loggable_sid: str = ''):
        self.loggable_sid = loggable_sid

    def __str__(self):
        return f'SessionNotFoundError, SID = {self.loggable_sid}'
