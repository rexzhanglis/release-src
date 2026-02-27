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

# 自动执行数据库迁移（新表建表、字段变更等）
python manage.py migrate --noinput

/usr/bin/supervisord

