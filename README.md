# dynamodb-web-session

## Development

### Prerequisites:

* Docker

### Tests

The integration tests will use the `docker-compose.yml` file to create a local DynamoDB instance.


## Table
```shell script
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema "AttributeName=id,KeyType=HASH" \
    --provisioned-throughput "ReadCapacityUnits=5,WriteCapacityUnits=5" \
    --table-name app_session 
```
