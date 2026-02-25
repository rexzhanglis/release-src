#!/usr/bin/env bash

set -e

source /datayes/vue-release-web/docker/pre_run.sh

curl ${params}config.js?raw > /usr/share/nginx/html/config.js

nginx -g "daemon off;"
