#!/usr/bin/env bash

cur_dir=$(dirname $(realpath "$0"))
source .env

touch "${WORK_DIR}/data/bot.db"

docker compose --project-directory ${cur_dir} build --pull
docker compose --project-directory ${cur_dir} up -d
