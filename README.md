# dynamodb-web-session

An implementation of a "web" session using DynamoDB as backend storage. This project has the following goals:
* Focus on core session handling concerns, rather than specific Python frameworks.
* Follow [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) 
best practices by default. Specifically, best practices for:
  * Session ID
    - [X] Length, value, and entropy: ID is a 32-byte secure random number. 
    - [X] Strict session management: ID generation can only occur within the framework.
  * Timeouts
    - [X] Absolute session timeout - default of 12 hours
    - [X] Idle session timeout - default of 2 hours
    - [X] Manual session timeout - i.e. there's delete/clear support

## Usage

Requires a DynamoDB table named `app_session` (can be changed in settings)

### Create session table

```shell
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema "AttributeName=id,KeyType=HASH" \
    --provisioned-throughput "ReadCapacityUnits=5,WriteCapacityUnits=5" \
    --table-name app_session 
```

### Default Example
```python
from dynamodb_session_web import SessionManager

session = SessionManager()

# Create a new session object, get the ID for later use
initial_data = session.create()
session_id = initial_data.session_id

initial_data['foo'] = 'bar'
initial_data['one'] = 1
session.save(initial_data)

print(session_id)
#> 'WaHnSSou4d5Rq0k11vFGafe4sjMrkwiVhNziIWLLwMc'
print(initial_data.loggable_session_id)
#> '517286da2682be08dc9975612dc86d65487f0990906656f631d419e64dcda6f41f5e0529c290663be315524a0b35777645e0e827d2e982a048b5e2b4bba4e02b'

loaded_data = session.load(session_id)
print(loaded_data['foo'])
#> 'bar'
print(loaded_data['one'])
#> 1

session.clear(session_id)
```

### Configurable Timeout and NullSession Response
```python
from time import sleep
from dynamodb_session_web import SessionManager

session = SessionManager()

# Create a new session object, get the ID for later use
initial_data = session.create()
initial_data.idle_timeout_seconds = 30
initial_data.absolute_timeout_seconds = 30
session_id = initial_data.session_id

initial_data['foo'] = 'bar'
session.save(initial_data)

sleep(35)

loaded_data = session.load(session_id)
print(loaded_data)
#> <dynamodb_session_web.NullSessionInstance object at 0x109a7da30>
```


### Custom Data Class Example
```python
import json
from dataclasses import asdict, dataclass

from dynamodb_session_web import SessionInstanceBase, SessionManager

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

session = SessionManager(MySession)

# Create a new session object, get the ID for later use
initial_data = session.create()
session_id = initial_data.session_id

initial_data.fruit = 'apple'
initial_data.color = 'red'
session.save(initial_data)

loaded_data = session.load(session_id)
print(loaded_data.fruit)
#> 'apple'
print(loaded_data.color)
#> 'red'

session.clear(session_id)
```

## Configuration

Several behaviors can be configured at the Session Manager level:
* Custom data class; must provide serialization and deserialization methods (see examples)
* Session ID length
* Table name
* DynamoDB URL

```python
from dynamodb_session_web import SessionInstanceBase, SessionManager

class MyCustomDataClass(SessionInstanceBase):
    def deserialize(self, data: str):
        pass

    def serialize(self) -> str:
        pass

SessionManager(
    MyCustomDataClass,
    sid_byte_length=128,
    table_name='my-dynamodb-table',
    endpoint_url='http://localhost:8000',
)
```

Additionally, session instances can have their own idle and absolute timeouts, specified in seconds:

```python
from dynamodb_session_web import SessionManager

session = SessionManager()

instance = session.create()
instance.idle_timeout_seconds = 30
instance.absolute_timeout_seconds = 30
```

## Development

### Prerequisites:

* Docker

### Tests

The integration tests will use the `docker-compose.yml` file to create a local DynamoDB instance.

## Useful Things

### Get a record from local DynamoDB instance

```shell
export sid=Jh4f1zvVp9n-YaDbkpZ0Vtru6iCXnERZv40q_ocZ7BA
aws dynamodb query --table-name app_session --endpoint-url http://localhost:8000 \
  --key-condition-expression 'id = :id' \
  --expression-attribute-values '{ ":id": {"S": "'$sid'" }}'
```
