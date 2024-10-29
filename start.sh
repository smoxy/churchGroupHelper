#!/usr/bin/env bash

source .env

touch "${WORK_DIR}/data/whitelist.json"

docker compose --project-directory ${WORK_DIR} build --pull
docker compose --project-directory ${WORK_DIR} up -d
