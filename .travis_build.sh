#!/bin/bash

docker build -t dbcawa/it-assets .
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
docker push dbcawa/it-assets
