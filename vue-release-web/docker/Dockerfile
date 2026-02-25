FROM nginx:1.20.0
LABEL maintainer="zhixiong.zeng"
ARG VERSION

ADD docker/sources.list /etc/apt/
RUN apt update && apt install -y procps net-tools

COPY /dist /usr/share/nginx/html

COPY /docker /datayes/vue-release-web/docker

WORKDIR /datayes/vue-release-web/

CMD ["bash", "./docker/entrypoint.sh"]
