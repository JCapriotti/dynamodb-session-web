import hashlib
import json
import secrets
from datetime import datetime, timezone

import boto3

DEFAULT_TTL = 7200  # two hours
DEFAULT_TABLE = 'app_session'
DEFAULT_SESSION_ID_BYTES = 32


def create_session_id(byte_length: int) -> str:
    return secrets.token_urlsafe(byte_length)


def current_datetime(datetime_value: datetime = None) -> datetime:
    if datetime_value is None:
        datetime_value = datetime.now(tz=timezone.utc)
    return datetime_value


def current_timestamp(datetime_value: datetime = None) -> int:
    if datetime_value is None:
        datetime_value = datetime.now(tz=timezone.utc)
    return int(datetime_value.timestamp())


class SessionCore:
    _boto_client = None

    def __init__(self, **kwargs):
        self.sid_byte_length = kwargs.get('session_id_bytes', DEFAULT_SESSION_ID_BYTES)
        self.session_id = kwargs.get('session_id', create_session_id(self.sid_byte_length))
        self.table_name = kwargs.get('table_name', DEFAULT_TABLE)
        self.ttl = kwargs.get('ttl', DEFAULT_TTL)
        self.dynamodb_endpoint_url = kwargs.get('dynamodb_endpoint_url', None)

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
        self._dynamo_set(serialized, True)

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
                                       ExpressionAttributeNames={
                                           '#ttl': 'ttl',
                                       },
                                       KeyConditionExpression='id = :sid',
                                       FilterExpression='#ttl > :now',
                                       ConsistentRead=True)
        if res.get('Items') and len(res.get('Items')) == 1 and res.get('Items')[0]['data']:
            data = res.get('Items')[0]['data']
            return data.get('S', '{}')
        else:
            raise SessionNotFoundError(self.loggable_sid)

    def _dynamo_set(self, data, modified):
        fields = {
            'accessed': {'S': current_datetime().isoformat()},
            'ttl': {'N': str(current_timestamp() + self.ttl)},
        }
        if modified:
            fields['data'] = {'S': data}

        attr_names = {}
        attr_values = {}
        ud_exp = []
        for k, v in fields.items():
            attr = "#attr_{}".format(k)
            token = ":{}".format(k)
            ud_exp.append("{} = {}".format(attr, token))
            attr_values[token] = v
            attr_names[attr] = k

        self.boto_client().update_item(TableName=self.table_name,
                                       Key={'id': {'S': self.session_id}},
                                       ExpressionAttributeNames=attr_names,
                                       ExpressionAttributeValues=attr_values,
                                       UpdateExpression='SET {}'.format(', '.join(ud_exp)),
                                       ReturnValues='NONE')

    def boto_client(self):
        if self._boto_client is None:
            self._boto_client = boto3.client('dynamodb', endpoint_url=self.dynamodb_endpoint_url)

        return self._boto_client


class SessionNotFoundError(Exception):
    loggable_sid: str

    def __init__(self, loggable_sid: str = ''):
        self.loggable_sid = loggable_sid

    def __str__(self):
        return f'SessionNotFoundError, SID = {self.loggable_sid}'
