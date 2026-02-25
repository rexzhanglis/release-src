"""
author: zhixiong.zeng
python version: 3
time: 2021/8/31 18:02
"""

"""
gunicorn -c conf/gunicorn.conf.py release.wsgi:application 运行命令
"""
import multiprocessing

bind = '127.0.0.1:8000'
backlog = 512
chdir = '/datayes/release'
timeout = 5
worker_class = 'sync'

workers = multiprocessing.cpu_count()  # 进程数
threads = 2
loglevel = 'info'  # 日志级别，这个日志级别指的是错误日志的级别，而访问日志的级别无法设置
access_log_format = '%(t)s %(p)s %(h)s "%(r)s" %(s)s %(L)s %(b)s %(f)s" "%(a)s"'  # 设置gunicorn访问日志格式，错误日志无法设置

accesslog = "/var/log/release/gunicorn_access.log"  # 访问日志文件
errorlog = "/var/log/release/gunicorn_error.log"  # 错误日志文件
