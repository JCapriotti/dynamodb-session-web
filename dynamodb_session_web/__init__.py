import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from secrets import token_urlsafe
from typing import Any, Generic, NamedTuple, Optional, Type, TypeVar

import boto3
from botocore.exceptions import ClientError

DEFAULT_IDLE_TIMEOUT = 7200  # two hours
DEFAULT_ABSOLUTE_TIMEOUT = 43200  # twelve hours
DEFAULT_TABLE = 'app_session'
DEFAULT_SESSION_ID_BYTES = 32

SessionInstanceType = TypeVar('SessionInstanceType')


class DynamoData(NamedTuple):
    data: Any
    idle_timeout: int
    absolute_timeout: int
    created: str


def create_session_id(byte_length: int) -> str:
    return token_urlsafe(byte_length)


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


class SessionInstanceBase(ABC):
    def __init__(self, *,
                 session_id: str = None,
                 idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT,
                 absolute_timeout_seconds: int = DEFAULT_ABSOLUTE_TIMEOUT):
        # TODO Handle non-int and None for timeouts
        self.session_id = session_id
        self.idle_timeout_seconds = int(idle_timeout_seconds)
        self.absolute_timeout_seconds = int(absolute_timeout_seconds)

    @abstractmethod
    def deserialize(self, data: str):
        pass

    @abstractmethod
    def serialize(self) -> str:
        pass

    @property
    def loggable_session_id(self):
        return hashlib.sha512(self.session_id.encode()).hexdigest()


class SessionDictInstance(SessionInstanceBase, dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def deserialize(self, data: str):
        self.update(json.loads(data))

    def serialize(self) -> str:
        return json.dumps(self)


class NullSessionInstance(SessionInstanceBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def deserialize(self, data):
        pass

    def serialize(self):
        pass


class SessionManager(Generic[SessionInstanceType]):
    _boto_client = None
    _dynamodb_table = None

    def __init__(self, data_type: Type[SessionInstanceType] = SessionDictInstance, **kwargs):
        self.sid_byte_length = kwargs.get('sid_byte_length', DEFAULT_SESSION_ID_BYTES)
        self.table_name = kwargs.get('table_name', DEFAULT_TABLE)
        self.endpoint_url = kwargs.get('endpoint_url', None)
        self._data_type = data_type

    def create(self, **kwargs) -> SessionInstanceType:
        sid = create_session_id(self.sid_byte_length)
        kwargs['session_id'] = sid
        session_data_object = self._data_type(**kwargs)
        dynamo_data = DynamoData(session_data_object.serialize(),
                                 session_data_object.idle_timeout_seconds,
                                 session_data_object.absolute_timeout_seconds,
                                 current_datetime().isoformat())
        self._dynamo_set(dynamo_data, sid, modified=True)
        return session_data_object

    def load(self, session_id) -> SessionInstanceType:
        data = self._perform_get(session_id)
        if data is not None:
            self._dynamo_set(data, session_id, modified=False)
            session_object = self._data_type(session_id=session_id,
                                             idle_timeout_seconds=data.idle_timeout,
                                             absolute_timeout_seconds=data.absolute_timeout)
            session_object.deserialize(data.data)
            return session_object

        return NullSessionInstance(session_id=session_id)

    def save(self, data: SessionInstanceType):
        created = self._dynamo_get_created(data.session_id)
        dynamo_data = DynamoData(data.serialize(), data.idle_timeout_seconds, data.absolute_timeout_seconds, created)
        self._dynamo_set(dynamo_data, data.session_id, modified=True)

    def clear(self, session_id):
        self._dynamo_remove(session_id)

    def _dynamo_remove(self, session_id):
        self.boto_client().delete_item(
            TableName=self.table_name,
            Key={'id': {'S': session_id}})

    def _perform_get(self, session_id):
        return self._dynamo_get(session_id)

    def _dynamo_get(self, session_id) -> Optional[DynamoData]:
        res = self.boto_client().query(TableName=self.table_name,
                                       ExpressionAttributeValues={
                                           ':sid': {
                                               'S': session_id,
                                           },
                                           ':now': {
                                               'N': str(current_timestamp())
                                           },
                                       },
                                       KeyConditionExpression='id = :sid',
                                       FilterExpression='expires > :now',
                                       ConsistentRead=True)
        if res.get('Items') and len(res.get('Items')) == 1:
            idle_timeout = int(res.get('Items')[0]['idle_timeout'].get('N', DEFAULT_IDLE_TIMEOUT))
            absolute_timeout = int(res.get('Items')[0]['absolute_timeout'].get('N', DEFAULT_ABSOLUTE_TIMEOUT))
            created = res.get('Items')[0]['created'].get('S', current_datetime())

            if res.get('Items')[0]['data']:
                data = res.get('Items')[0]['data']
                return DynamoData(data.get('S', '{}'), idle_timeout, absolute_timeout, created)
        else:
            return None

    def _dynamo_get_created(self, session_id) -> str:
        try:
            response = self.dynamodb_table().get_item(Key={'id': session_id})
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            return response['Item']['created']

    def _dynamo_set(self, data: DynamoData, session_id, modified):
        current_dt = current_datetime().isoformat()
        fields = {
            'accessed': {'S': current_dt},
            'expires': {'N': str(
                expiration_datetime(data.idle_timeout, data.absolute_timeout, data.created, current_dt)
            )},
            'created': {'S': data.created},
        }

        if modified:
            fields['idle_timeout'] = {'N': str(data.idle_timeout)}
            fields['absolute_timeout'] = {'N': str(data.absolute_timeout)}
            fields['data'] = {'S': data.data}

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
                                       Key={'id': {'S': session_id}},
                                       ExpressionAttributeNames=attr_names,
                                       ExpressionAttributeValues=attr_values,
                                       UpdateExpression='SET '
                                                      #  'created = if_not_exists(created, :created), '
                                                        '{}'.format(', '.join(update_expression)),
                                       ReturnValues='NONE')

    def boto_client(self):
        if self._boto_client is None:
            self._boto_client = boto3.client('dynamodb', endpoint_url=self.endpoint_url)

        return self._boto_client

    def dynamodb_table(self):
        if self._dynamodb_table is None:
            dynamodb = boto3.resource('dynamodb', endpoint_url=self.endpoint_url)
            self._dynamodb_table = dynamodb.Table(self.table_name)

        return self._dynamodb_table


__all__ = [
    'SessionManager',
    'SessionDictInstance',
    'SessionInstanceBase',
    'NullSessionInstance',
]
