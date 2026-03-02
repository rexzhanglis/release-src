"""
测试专用 Django settings
- 使用 SQLite 替代 MySQL（无需外部数据库）
- 禁用 CAS 认证（使用 Django 内置 auth）
- 关闭 LDAP/EasyAudit 等依赖外部服务的组件
- 外部服务（GitLab/Consul/Ansible）使用 Mock 地址（测试时由 unittest.mock 拦截）
"""

from release.settings import *

# =========================================================
# 数据库：使用 SQLite 内存数据库，测试后自动销毁
# =========================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# =========================================================
# 去掉依赖外部服务或难以 mock 的 middleware
# =========================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'api.middleware.exception_middleware.ExceptionMiddleware',
    'api.middleware.disable_csrf_check.DisableCsrfCheck',
]

# =========================================================
# 认证后端：只用 Django 原生 ModelBackend，去掉 CAS
# =========================================================
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

# =========================================================
# 去掉 django_cas_ng（需要 CAS 服务器）和 easyaudit（会写审计表）
# =========================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'django_extensions',
    'django_filters',
    # 'django_crontab',  # 定时任务，测试不需要
    # 'easyaudit',       # 依赖数据库写入，测试时禁用以防干扰
    # 'django_cas_ng',   # CAS SSO，测试不需要
    'api',
    'account',
    'const',
    'app',
    'mdl',
]

# =========================================================
# 外部服务地址（测试时用 unittest.mock 拦截，这里设 mock 值）
# =========================================================
CONFIG_GITLAB_URL = 'http://mock-gitlab.test'
CONFIG_GITLAB_TOKEN = 'mock-token'
CONFIG_GITLAB_PROJECT_ID = '9999'
CONFIG_GITLAB_BRANCH = 'master'
CONFIG_GITLAB_ROOT_PATH = ''

CONFIG_CONSUL_URL = 'http://mock-consul.test'
CONFIG_CONSUL_TOKEN = 'mock-consul-token'
CONFIG_CONSUL_KV_PREFIX = 'configs/mdl'

# Ansible 目录（测试时 subprocess 会被 mock，不实际执行）
import os as _os
CONFIG_ANSIBLE_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'ansi', 'mdl')

ANSIBLE_SSH_USER = 'root'
ANSIBLE_SSH_PASS = 'test-pass'

DEPLOY_DEFAULT_INSTALL_DIR = '/datayes/app/bin'
DEPLOY_DEFAULT_BACKUPS_DIR = '/datayes/app/backups'

# =========================================================
# 关闭 LDAP（settings.py 末尾会 import ldap_auth，测试环境若无 python-ldap 则需覆盖）
# =========================================================
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

# 覆盖 LDAP 相关设置（防止 import 失败）
AUTH_LDAP_SERVER_URI = ''

# =========================================================
# 加快测试速度：使用简单密码哈希
# =========================================================
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# =========================================================
# 静默日志，避免测试输出混乱
# =========================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
        'level': 'CRITICAL',
    },
}
