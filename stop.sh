#!/usr/bin/env bash

cur_dir=$(dirname $(realpath "$0"))
source .env

docker compose --project-directory "${cur_dir}" down --rmi all
