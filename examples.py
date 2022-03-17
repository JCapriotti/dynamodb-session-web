import json
from dataclasses import asdict, dataclass
from time import sleep

from dynamodb_session_web import SessionManager, SessionDictInstance, SessionInstanceBase

LOCAL_ENDPOINT = 'http://localhost:8000'
TABLE_NAME = 'app_session'


def recreate_database():
    import boto3
    import botocore
    dynamodb = boto3.resource('dynamodb', endpoint_url=LOCAL_ENDPOINT)

    # Remove table (if it exists)
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.delete()
    except botocore.exceptions.ClientError:
        pass

    # Create the DynamoDB table.
    return dynamodb.create_table(
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


def print_table_data(table):
    from decimal import Decimal

    class DecimalEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return str(obj)
            return json.JSONEncoder.default(self, obj)

    response = table.scan(
        Select='ALL_ATTRIBUTES',
        ConsistentRead=True
    )
    if len(response.get('Items', [])) > 0:
        print(json.dumps(response['Items'], indent=2, cls=DecimalEncoder))
    else:
        print('>>>> No Data in DynamoDB <<<<')


dynamo_table = recreate_database()


@dataclass
class MySession(SessionInstanceBase):
    fruit: str = ''
    color: str = ''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def deserialize(self, data):
        data_dict = json.loads(data)
        self.fruit = data_dict['fruit']
        self.color = data_dict['color']

    def serialize(self):
        return json.dumps(asdict(self))


def dataclass_example():
    """ Create a session manager using `MySession` as the data type """
    print('========== Data Class Example ==========')
    session = SessionManager(MySession, endpoint_url=LOCAL_ENDPOINT)

    # Create a new session object
    initial_data = session.create()
    session_id = initial_data.session_id

    initial_data.fruit = 'apple'
    initial_data.color = 'red'
    session.save(initial_data)

    print(f'Saved Data for {session_id}')
    print(f'The "loggable" session_id is: {initial_data.loggable_session_id}')
    print()
    print('Data from DynamoDB:')
    print_table_data(dynamo_table)
    print()

    loaded_data = session.load(session_id)
    print('Loaded data from Session record: ')
    print(f'Fruit: {loaded_data.fruit}')
    print(f'Color: {loaded_data.color}')
    print()

    session.clear(session_id)
    print('Cleared Data from DynamoDB:')
    print_table_data(dynamo_table)
    print()


def default_example():
    """ Create a session manager using default dictionary data type """
    print('========== Default Example ==========')
    session = SessionManager(endpoint_url=LOCAL_ENDPOINT)

    # Create a new session object
    initial_data = session.create()
    session_id = initial_data.session_id

    initial_data['foo'] = 'bar'
    initial_data['one'] = 1
    session.save(initial_data)

    print(f'Saved Data for {session_id}')
    print(f'The "loggable" session_id is: {initial_data.loggable_session_id}')
    print()
    print('Data from DynamoDB:')
    print_table_data(dynamo_table)
    print()

    loaded_data = session.load(session_id)
    print('Loaded data from Session record: ')
    print(f'foo: {loaded_data["foo"]}')
    print(f'one: {loaded_data["one"]}')
    print()

    session.clear(session_id)
    print('Cleared Data from DynamoDB:')
    print_table_data(dynamo_table)
    print()


def timeout_example():
    """ Example with extremely short timeout """
    print('========== Session Expiration Example ==========')
    session = SessionManager(SessionDictInstance, endpoint_url=LOCAL_ENDPOINT)

    # Create a new session object
    initial_data = session.create()
    initial_data.idle_timeout_seconds = 30
    initial_data.absolute_timeout_seconds = 30
    session_id = initial_data.session_id

    initial_data['foo'] = 'bar'
    session.save(initial_data)

    print(f'Saved Data for {session_id}')
    print(f'The "loggable" session_id is: {initial_data.loggable_session_id}')
    print()
    print('Data from DynamoDB:')
    print_table_data(dynamo_table)
    print()

    print('Sleeping for 35 seconds')
    sleep(35)

    loaded_data = session.load(session_id)
    print('Loaded data from Session record: ')
    print(loaded_data)
    print()

    print('Data from DynamoDB:')
    print_table_data(dynamo_table)


dataclass_example()
default_example()
timeout_example()
