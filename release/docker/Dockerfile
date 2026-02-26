FROM registry.datayes.com/base/python3-base:3.9.5
#FROM python:3.9.5
LABEL maintainer="yinyin.zhang"
ARG VERSION
# 更新apt update and base install
# 使用默认源或者修复后的 sources.list
# ADD docker/sources.list /etc/apt/
# 替换为清华源或者阿里源的 Debian 10 (buster) archive，因为 buster 已经 archived
RUN echo "deb http://mirrors.aliyun.com/debian-archive/debian/ buster main non-free contrib" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-archive/debian/ buster-backports main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-archive/debian-security/ buster/updates main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-archive/debian/ buster main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-archive/debian/ buster-backports main non-free contrib" >> /etc/apt/sources.list && \
    echo "deb-src http://mirrors.aliyun.com/debian-archive/debian-security/ buster/updates main non-free contrib" >> /etc/apt/sources.list

# 增加 -o Acquire::Check-Valid-Until=false 以防止 Release file expired 错误
RUN apt update -o Acquire::Check-Valid-Until=false && apt install -y -o Acquire::Check-Valid-Until=false tzdata sshpass gcc cron aptitude libxml2 libxml2-dev libxslt1-dev net-tools git nginx supervisor vim libsasl2-dev python-dev libldap2-dev libssl-dev dos2unix --fix-missing

# 设置时区为上海
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
RUN echo "Asia/Shanghai" > /etc/timezone

# 更新 pip
RUN pip install pip -U -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
# 依赖包安装
COPY ./docker/requirements.txt requirements.txt
RUN pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
# RUN pip --proxy=http://shidcproxy2.wmcloud.com:8888 install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

ADD . /datayes/release/
WORKDIR /datayes/release/

# 转换换行符，解决 Windows 下编辑导致的 CRLF 问题
RUN dos2unix ./docker/*.sh && chmod +x ./docker/*.sh

CMD ["bash", "./docker/entrypoint.sh"]