#!/usr/bin/env bash

set -e

if [ -z ${CONSUL_SERVER} ]; then
	echo "Error: missing CONSUL_SERVER in env";
	exit 1
fi

if [ -z ${CONSUL_TOKEN} ]; then
	echo "Warning: missing CONSUL_TOKEN in env";
	TOKEN_STRING=""
else
	TOKEN_STRING="--header X-Consul-Token:${CONSUL_TOKEN}"
fi

if [ -z ${OVERWRITE_CONSUL_PATH_FOLDER} ]; then
	echo "Error: OVERWRITE_CONSUL_PATH_FOLDER is required";
	exit 1
else
    CONSUL_PATH=/v1/kv${OVERWRITE_CONSUL_PATH_FOLDER}
fi

CONSUL_URL=${CONSUL_SERVER}${CONSUL_PATH}
echo "consul url: ${CONSUL_URL}"

params="$TOKEN_STRING ${CONSUL_URL}"
echo $params
