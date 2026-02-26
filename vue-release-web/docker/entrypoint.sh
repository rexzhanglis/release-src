#!/usr/bin/env bash

set -e

# 如果提供了 CONSUL_SERVER，则尝试从 Consul 拉取配置（原有逻辑）
if [ ! -z "${CONSUL_SERVER}" ]; then
    source /datayes/vue-release-web/docker/pre_run.sh
    curl ${params}config.js?raw > /usr/share/nginx/html/config.js
else
    # 否则，使用环境变量直接生成 config.js
    echo "Generating config.js from environment variables..."
    
    # 设置默认值
    API_URL=${BACKEND_API_URL:-"http://localhost:8000/api"}
    WEB_URL=${WEB_LOGIN_URL:-"http://localhost:9528/"}
    LOGIN_URL=${BACKEND_LOGIN_URL:-"http://localhost:8000/login"}
    
    cat <<EOF > /usr/share/nginx/html/config.js
window.config = {
  BACKEND_BASE_API: "${API_URL}",
  WEB_LOGIN_URL: "${WEB_URL}",
  CAS_LOGOUT_URL: "https://cas.wmcloud.com/cas/logout",
  BACKEND_LOGIN_URL: "${LOGIN_URL}",
  DASHBOARD_GRAFANA_MONITOR_URL: "http://grafana.devops2.wmcloud.com/d/OLK0tU8nk/fa-bu-dashboard?orgId=1&theme=light&kiosk=tv",
  MDL_LABEL_URL:"${API_URL}".replace('/api', '/adminmdl/label/'),
}
EOF
fi

nginx -g "daemon off;"
