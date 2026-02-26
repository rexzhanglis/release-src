# 阶段一：构建前端应用
#FROM node:14 AS builder
FROM registry.datayes.com/base/ubuntu-node18:1.0.0-1483 AS builder

WORKDIR /app

# 复制 package.json 和 lock 文件
COPY package*.json ./

# 设置 npm 源（可选，根据网络情况）
# RUN npm config set registry https://npm.wmcloud.com/

# 安装依赖
RUN npm install

# 确保 node_modules/.bin 下的可执行文件有执行权限
RUN chmod +x node_modules/.bin/*

# 复制源代码
COPY . .

# 设置 OpenSSL Legacy Provider 以兼容 Node 18
ENV NODE_OPTIONS=--openssl-legacy-provider

# 构建生产环境代码
RUN npm run build

# 阶段二：部署到 Nginx
#FROM nginx:1.20.0
FROM registry.datayes.com/base/nginx:1.20.0
LABEL maintainer="yinyin.zhang"
ARG VERSION

# 修复 apt 源问题 (Debian Buster 已归档)
RUN echo "deb http://mirrors.aliyun.com/debian-archive/debian/ buster main non-free contrib" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-archive/debian/ buster-backports main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-archive/debian-security/ buster/updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-archive/debian/ buster main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-archive/debian/ buster-backports main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-archive/debian-security/ buster/updates main non-free contrib" >> /etc/apt/sources.list

RUN apt update -o Acquire::Check-Valid-Until=false && apt install -y -o Acquire::Check-Valid-Until=false procps net-tools dos2unix

# 从构建阶段复制 dist 目录到 Nginx
COPY --from=builder /app/dist /usr/share/nginx/html

COPY ./docker /datayes/vue-release-web/docker

WORKDIR /datayes/vue-release-web/

# 转换换行符，解决 Windows 下编辑导致的 CRLF 问题
RUN dos2unix ./docker/*.sh && chmod +x ./docker/*.sh

CMD ["bash", "./docker/entrypoint.sh"]
