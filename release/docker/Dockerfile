FROM registry.datayes.com/base/python3-base:3.9.5
#FROM python:3.9.5
LABEL maintainer="zhixiong.zeng"
ARG VERSION
# 更新apt update and base install
ADD docker/sources.list /etc/apt/
RUN apt update && apt install -y tzdata sshpass gcc cron aptitude libxml2 libxml2-dev libxslt1-dev net-tools git nginx supervisor vim libsasl2-dev python-dev libldap2-dev libssl-dev --fix-missing

# 设置时区为上海
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
RUN echo "Asia/Shanghai" > /etc/timezone

# 更新 pip
RUN pip install pip -U -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
# 依赖包安装
COPY docker/requirements.txt requirements.txt
RUN pip --proxy=http://shidcproxy2.wmcloud.com:8888 install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

ADD . /datayes/release/
WORKDIR /datayes/release/

CMD ["bash", "./docker/entrypoint.sh"]