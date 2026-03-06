#!/bin/sh
set -eu

docker compose up -d postgres redis
docker compose run --rm migrate
