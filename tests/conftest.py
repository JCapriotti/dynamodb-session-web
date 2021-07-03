import os

import pytest
from .helpers import get_dynamo_resource, TABLE_NAME

#
# def is_responsive(url):
#     try:
#         response = requests.get(url)
#         if response.status_code == 200:
#             return True
#     except ConnectionError:
#         return False

#
# @pytest.fixture(scope='session', autouse=True)
# def dynamodb_service(docker_ip, docker_services):
#     """Ensure that HTTP service is up and responsive."""
#     return
#     # # `port_for` takes a container port and returns the corresponding host port
#     # port = docker_services.port_for("httpbin", 80)
#     # url = "http://{}:{}".format(docker_ip, 8000)
#     # docker_services.
#     # docker_services.wait_until_responsive(
#     #     timeout=30.0, pause=0.1, check=lambda: is_responsive(url)
#     # )
#     # return url


@pytest.fixture(scope='function')
def dynamodb_table(docker_services):
    dynamodb = get_dynamo_resource()

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
