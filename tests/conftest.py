import botocore
import pytest
from pytest_mock import MockerFixture
from dynamodb_session_web import SessionManager
from .utility import get_dynamo_resource, TABLE_NAME


@pytest.fixture(scope='function')
def dynamodb_table(docker_services):  # pylint: disable=unused-argument
    dynamodb = get_dynamo_resource()

    # Remove table (if it exists)
    # noinspection PyUnresolvedReferences
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.delete()
    except botocore.exceptions.ClientError:
        pass

    # Create the DynamoDB table.
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{
            'AttributeName': 'id',
            'KeyType': 'HASH'
        }],
        AttributeDefinitions=[{
            'AttributeName': 'id',
            'AttributeType': 'S'
        }],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )

    # Wait until the table exists.
    table.meta.client.get_waiter('table_exists').wait(TableName=TABLE_NAME)
    yield
    table.delete()


@pytest.fixture
def mock_dynamo_set(mocker: MockerFixture):
    return mocker.patch.object(SessionManager, '_dynamo_set')


@pytest.fixture
def mock_dynamo_get(mocker: MockerFixture):
    return mocker.patch.object(SessionManager, '_dynamo_get')
