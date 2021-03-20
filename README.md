# dynamodb-web-session

## 

```shell script
aws dynamodb delete-table --table-name app_session --endpoint-url http://localhost:8000
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema "AttributeName=id,KeyType=HASH" \
    --provisioned-throughput "ReadCapacityUnits=5,WriteCapacityUnits=5" \
    --table-name app_session \
    --endpoint-url http://localhost:8000
```