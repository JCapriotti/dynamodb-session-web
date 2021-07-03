from datetime import datetime
from unittest.mock import Mock

import boto3
from dynamodb_session_web import SessionCore

TABLE_NAME = 'app_session'
LOCAL_ENDPOINT = 'http://localhost:8000'


def create_test_session(**kwargs):
    return SessionCore(endpoint_url=LOCAL_ENDPOINT, **kwargs)


def get_dynamo_resource():
    return boto3.resource('dynamodb', endpoint_url=LOCAL_ENDPOINT)


def get_dynamo_record(key):
    dynamodb = get_dynamo_resource()
    table = dynamodb.Table(TABLE_NAME)

    response = table.get_item(Key={'id': key})
    return response.get('Item', None)


def mock_current_datetime(mocker, val: datetime):
    mocker.patch('dynamodb_session_web.current_datetime', Mock(return_value=val))
