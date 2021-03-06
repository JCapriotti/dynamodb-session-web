from datetime import datetime
from random import randrange
from unittest.mock import Mock

import boto3
from dynamodb_session_web import SessionManager, SessionDictInstance

TABLE_NAME = 'app_session'
LOCAL_ENDPOINT = 'http://localhost:8000'
LOCAL_REGION_NAME = 'us-east-1'


def create_session_manager(**kwargs) -> SessionManager[SessionDictInstance]:
    """
    Creates a SessionCore object configured for integration testing
    """
    return SessionManager(SessionDictInstance, endpoint_url=LOCAL_ENDPOINT, region_name=LOCAL_REGION_NAME, **kwargs)


def get_dynamo_resource():
    return boto3.resource('dynamodb', endpoint_url=LOCAL_ENDPOINT, region_name=LOCAL_REGION_NAME)


def get_dynamo_record(key):
    dynamodb = get_dynamo_resource()
    table = dynamodb.Table(TABLE_NAME)

    response = table.get_item(Key={'id': key})
    return response.get('Item', None)


def mock_current_datetime(mocker, val: datetime):
    mocker.patch('dynamodb_session_web._session.current_datetime', Mock(return_value=val))


def str_param() -> str:
    return str(randrange(100000))
