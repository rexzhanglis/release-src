#!/usr/bin/env bash

set -e

source /datayes/release/docker/pre_run.sh

mkdir -p /var/log/release/

mkdir -p /datayes/mdl/packages/

rm -f /etc/nginx/sites-enabled/default
# conf
curl ${params}release_nginx.conf?raw > /etc/nginx/sites-enabled/release_nginx.conf
curl ${params}release_supervisor.conf?raw > /etc/supervisor/conf.d/release_supervisor.conf
curl ${params}settings.py?raw > /datayes/release/release/settings.py

service cron start

/usr/bin/supervisord

