#!/bin/bash

docker build -t dbcawa/itassets .
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
docker push dbcawa/itassets
