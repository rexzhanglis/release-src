#!/bin/bash
# 一键部署脚本，在目标机器上以 root 执行
# 用法: bash deploy.sh

set -e

INSTALL_DIR=/opt/release-agent
SERVICE_NAME=release-agent

echo "==> 创建目录 $INSTALL_DIR"
mkdir -p $INSTALL_DIR

echo "==> 复制文件"
cp agent.py   $INSTALL_DIR/
cp config.ini $INSTALL_DIR/

# 如果 servers.txt 不存在则复制示例文件
if [ ! -f "$INSTALL_DIR/servers.txt" ]; then
    cp servers.txt.example $INSTALL_DIR/servers.txt
    echo "    已创建 $INSTALL_DIR/servers.txt（请编辑填入实际转发机列表）"
fi

echo "==> 安装 systemd 服务"
cp release-agent.service /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable $SERVICE_NAME

echo ""
echo "====================================================="
echo " 部署完成！后续步骤："
echo "  1. 编辑 $INSTALL_DIR/config.ini  填写 center.url 和 token"
echo "  2. 编辑 $INSTALL_DIR/servers.txt 填写本环境转发机列表"
echo "  3. systemctl start $SERVICE_NAME"
echo "  4. journalctl -u $SERVICE_NAME -f  查看日志"
echo "====================================================="
