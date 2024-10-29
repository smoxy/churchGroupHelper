#!/usr/bin/env bash

source .env

mkdir -p "${WORK_DIR}/data/whisper"
touch "${WORK_DIR}/data/bot.db"

docker compose --project-directory ${WORK_DIR} build --pull
docker compose --project-directory ${WORK_DIR} up -d
