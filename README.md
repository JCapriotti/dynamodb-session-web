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



## Development

### Prerequisites:

* Docker

### Tests

The integration tests will use the `docker-compose.yml` file to create a local DynamoDB instance.

## Useful Things

### Create session table

```shell
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema "AttributeName=id,KeyType=HASH" \
    --provisioned-throughput "ReadCapacityUnits=5,WriteCapacityUnits=5" \
    --table-name app_session 
```

### Get a record from local DynamoDB instance

```shell
export sid=Jh4f1zvVp9n-YaDbkpZ0Vtru6iCXnERZv40q_ocZ7BA
aws dynamodb query --table-name app_session --endpoint-url http://localhost:8000 \
  --key-condition-expression 'id = :id' \
  --expression-attribute-values '{ ":id": {"S": "'$sid'" }}'
```
