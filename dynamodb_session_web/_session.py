import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from secrets import token_urlsafe
from typing import Any, Generic, List, NamedTuple, Optional, Type, TypeVar, overload

import boto3
from itsdangerous import BadSignature, Signer

from .exceptions import InvalidSessionIdError, SessionNotFoundError


DEFAULT_IDLE_TIMEOUT = 7200  # two hours
DEFAULT_ABSOLUTE_TIMEOUT = 43200  # twelve hours
DEFAULT_TABLE = 'app_session'
DEFAULT_SESSION_ID_BYTES = 32

T = TypeVar('T', bound='SessionInstanceBase')  # pylint: disable=invalid-name


class DynamoData(NamedTuple):
    data: Any
    idle_timeout: int
    absolute_timeout: int
    created: str


def create_session_id(byte_length: int, keys: List[str]) -> str:
    if len(keys) > 0:
        signer = Signer(keys)
        return signer.sign(token_urlsafe(byte_length)).decode('utf-8')
    return token_urlsafe(byte_length)


def validate_session_id(session_id, keys: List[str]) -> None:
    if not session_id:
        raise SessionNotFoundError(loggable_session_id(''))

    if len(keys) > 0:
        signer = Signer(keys)
        signer.unsign(session_id).decode('utf-8')


def current_datetime(datetime_value: Optional[datetime] = None) -> datetime:
    if datetime_value is None:
        datetime_value = datetime.now(tz=timezone.utc)
    return datetime_value


def current_timestamp(datetime_value: Optional[datetime] = None) -> int:
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


def loggable_session_id(sid: str) -> str:
    return hashlib.sha512(sid.encode()).hexdigest()


class SessionInstanceBase(ABC):
    def __init__(self, *,
                 session_id: str = '',
                 idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT,
                 absolute_timeout_seconds: int = DEFAULT_ABSOLUTE_TIMEOUT,
                 created: Optional[datetime] = None):
        self.session_id = session_id
        self.idle_timeout_seconds = int(idle_timeout_seconds)
        self.absolute_timeout_seconds = int(absolute_timeout_seconds)
        self.created = current_datetime() if created is None else created

    @abstractmethod
    def deserialize(self, data: str):
        pass

    @abstractmethod
    def serialize(self) -> str:
        pass

    @property
    def loggable_session_id(self):
        return loggable_session_id(self.session_id)


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


class SessionManager(Generic[T]):  # pylint: disable=too-many-instance-attributes
    _boto_client = None
    _data_type: Type[T]
    _idle_timeout: int = DEFAULT_IDLE_TIMEOUT
    _absolute_timeout: int = DEFAULT_ABSOLUTE_TIMEOUT
    _sid_keys: List[str] = []

    null_session_class: Type[SessionInstanceBase] = NullSessionInstance

    @overload
    def __init__(self: 'SessionManager[SessionDictInstance]', **kwargs) -> None:  # pragma: no cover
        self.sid_byte_length = kwargs.get('sid_byte_length', DEFAULT_SESSION_ID_BYTES)
        self.table_name = kwargs.get('table_name', DEFAULT_TABLE)
        self.endpoint_url = kwargs.get('endpoint_url', None)
        self.region_name = kwargs.get('region_name', None)
        self._idle_timeout = kwargs.get('idle_timeout', DEFAULT_IDLE_TIMEOUT)
        self._absolute_timeout = kwargs.get('absolute_timeout', DEFAULT_ABSOLUTE_TIMEOUT)
        self._sid_keys = kwargs.get('sid_keys', [])
        self._bad_session_id_raises = kwargs.get('bad_session_id_raises', False)
        self._data_type = SessionDictInstance

    @overload
    def __init__(self: 'SessionManager[T]', data_type: Type[T], **kwargs) -> None:  # pragma: no cover
        self.sid_byte_length = kwargs.get('sid_byte_length', DEFAULT_SESSION_ID_BYTES)
        self.table_name = kwargs.get('table_name', DEFAULT_TABLE)
        self.endpoint_url = kwargs.get('endpoint_url', None)
        self.region_name = kwargs.get('region_name', None)
        self._idle_timeout = kwargs.get('idle_timeout', DEFAULT_IDLE_TIMEOUT)
        self._absolute_timeout = kwargs.get('absolute_timeout', DEFAULT_ABSOLUTE_TIMEOUT)
        self._sid_keys = kwargs.get('sid_keys', [])
        self._bad_session_id_raises = kwargs.get('bad_session_id_raises', False)
        self._data_type = data_type

    def __init__(self, data_type: Type[T] = SessionDictInstance, **kwargs) -> None:  # type: ignore
        """ Creates a new SessionManager instance.

        :param data_type: The data type to use for session instances. Defaults to SessionDictInstance.
        :param kwargs: Supported keyword args:
            sid_byte_length - The session id length in bytes. Defaults to 32.
            table_name - The DynamoDB table name. Defaults to app_session.
            endpoint_url - The DynamoDB URL. Defaults to None.
            region_name - The DynamoDB Region. Defaults to None.
            idle_timeout - The timeout used to expire idle sessions. Defaults to 7200 seconds.
            absolute_timeout - The timeout used for absolute session expiration. Defaults to 43200 seconds.
        """
        self.sid_byte_length = kwargs.get('sid_byte_length', DEFAULT_SESSION_ID_BYTES)
        self.table_name = kwargs.get('table_name', DEFAULT_TABLE)
        self.endpoint_url = kwargs.get('endpoint_url', None)
        self.region_name = kwargs.get('region_name', None)
        self._idle_timeout = kwargs.get('idle_timeout_seconds', DEFAULT_IDLE_TIMEOUT)
        self._absolute_timeout = kwargs.get('absolute_timeout_seconds', DEFAULT_ABSOLUTE_TIMEOUT)
        self._sid_keys = kwargs.get('sid_keys', [])
        self._bad_session_id_raises = kwargs.get('bad_session_id_raises', False)
        self._data_type = data_type

    def create(self, *,
               idle_timeout_seconds: Optional[int] = None,
               absolute_timeout_seconds: Optional[int] = None) -> T:
        """ Creates a session instance. At this point, no session record is persisted.

        :param idle_timeout_seconds: Idle timeout specific to this session instance.
        Defaults to session manager's value.

        :param absolute_timeout_seconds: Absolute timeout specific to this session instance.
        Defaults to session manager's value.

        :return: A new session instance
        """
        idle = self._idle_timeout if idle_timeout_seconds is None else idle_timeout_seconds
        absolute = self._absolute_timeout if absolute_timeout_seconds is None else absolute_timeout_seconds
        return self._data_type(session_id=create_session_id(self.sid_byte_length, self._sid_keys),
                               idle_timeout_seconds=idle,
                               absolute_timeout_seconds=absolute)

    def create_and_save(self, *,
                        idle_timeout_seconds: Optional[int] = None,
                        absolute_timeout_seconds: Optional[int] = None) -> T:
        """ Creates a session instance, and persists it in the database.

        :param idle_timeout_seconds: Idle timeout specific to this session instance.
        Defaults to session manager's value.

        :param absolute_timeout_seconds: Absolute timeout specific to this session instance.
        Defaults to session manager's value.

        :return: A new session instance
        """
        idle = self._idle_timeout if idle_timeout_seconds is None else idle_timeout_seconds
        absolute = self._absolute_timeout if absolute_timeout_seconds is None else absolute_timeout_seconds
        sid = create_session_id(self.sid_byte_length, self._sid_keys)
        session_data_object = self._data_type(session_id=sid,
                                              idle_timeout_seconds=idle,
                                              absolute_timeout_seconds=absolute)

        dynamo_data = DynamoData(session_data_object.serialize(),
                                 session_data_object.idle_timeout_seconds,
                                 session_data_object.absolute_timeout_seconds,
                                 current_datetime().isoformat())
        self._dynamo_set(dynamo_data, sid, modified=True)
        return session_data_object

    def load(self, session_id) -> T:
        data = None
        try:
            validate_session_id(session_id, self._sid_keys)
        except BadSignature as exc:
            if self._bad_session_id_raises:
                raise InvalidSessionIdError(loggable_session_id(session_id)) from exc
        else:
            data = self._perform_get(session_id)
            if data is None and self._bad_session_id_raises:
                raise SessionNotFoundError(loggable_session_id(session_id))

        if data is None:
            return self.null_session_class(session_id=session_id)  # type: ignore

        self._dynamo_set(data, session_id, modified=False)
        session_object = self._data_type(session_id=session_id,
                                         idle_timeout_seconds=data.idle_timeout,
                                         absolute_timeout_seconds=data.absolute_timeout,
                                         created=datetime.fromisoformat(data.created))
        session_object.deserialize(data.data)
        return session_object

    def save(self, data: T):
        dynamo_data = DynamoData(data.serialize(),
                                 data.idle_timeout_seconds,
                                 data.absolute_timeout_seconds,
                                 data.created.isoformat())
        self._dynamo_set(dynamo_data, data.session_id, modified=True)

    def clear(self, session_id):
        self._dynamo_remove(session_id)

    def _dynamo_remove(self, session_id):
        self.boto_client().delete_item(
            TableName=self.table_name,
            Key={'id': {'S': session_id}})

    def _perform_get(self, session_id) -> Optional[DynamoData]:
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
            idle_timeout = int(res.get('Items')[0]['idle_timeout'].get('N', self._idle_timeout))
            absolute_timeout = int(res.get('Items')[0]['absolute_timeout'].get('N', self._absolute_timeout))
            created: str = res.get('Items')[0]['created'].get('S', current_datetime().isoformat())

            if res.get('Items')[0]['data']:
                data = res.get('Items')[0]['data']
                return DynamoData(data.get('S', '{}'), idle_timeout, absolute_timeout, created)

        return None

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
        for key, val in fields.items():
            attr = f'#attr_{key}'
            token = f':{key}'
            update_expression.append(f'{attr} = {token}')
            attr_values[token] = val
            attr_names[attr] = key

        self.boto_client().update_item(TableName=self.table_name,
                                       Key={'id': {'S': session_id}},
                                       ExpressionAttributeNames=attr_names,
                                       ExpressionAttributeValues=attr_values,
                                       UpdateExpression=f'SET {", ".join(update_expression)}',
                                       ReturnValues='NONE')

    def boto_client(self):
        if self._boto_client is None:
            boto_client_kwargs = {}
            if self.endpoint_url is not None:
                boto_client_kwargs["endpoint_url"] = self.endpoint_url
            if self.region_name is not None:
                boto_client_kwargs["region_name"] = self.region_name
            self._boto_client = boto3.client('dynamodb', **boto_client_kwargs)
        return self._boto_client
