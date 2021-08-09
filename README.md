# dynamodb-web-session

## Development

### Prerequisites:

* Docker

### Tests

The integration tests will use the `docker-compose.yml` file to create a local DynamoDB instance.

### TODO

* Use exceptions?
* Test NullSession
* Logger

## Table
```shell
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema "AttributeName=id,KeyType=HASH" \
    --provisioned-throughput "ReadCapacityUnits=5,WriteCapacityUnits=5" \
    --table-name app_session 
```

Get a record
```shell
export sid=Jh4f1zvVp9n-YaDbkpZ0Vtru6iCXnERZv40q_ocZ7BA
aws dynamodb query --table-name app_session --endpoint-url http://localhost:8000 \
  --key-condition-expression 'id = :id' \
  --expression-attribute-values '{ ":id": {"S": "'$sid'" }}'
```