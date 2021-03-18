from unittest.mock import Mock

import boto3
from dynamodb_session_web import SessionCore

DYNAMODB_LOCAL_ENDPOINT = 'http://localhost:8000'


def create_test_session(**kwargs):
    return SessionCore(dynamodb_endpoint_url=DYNAMODB_LOCAL_ENDPOINT, **kwargs)


def get_dynamo_record(key, table):
    dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMODB_LOCAL_ENDPOINT)
    table = dynamodb.Table(table)

    response = table.get_item(Key={'id': key})
    return response.get('Item', None)


def mock_current_timestamp(mocker, val: int):
    mocker.patch('dynamodb_session_web.current_timestamp', Mock(return_value=val))


def mock_current_datetime(mocker, val: str):
    mocker.patch('dynamodb_session_web.current_datetime', Mock(return_value=val))
