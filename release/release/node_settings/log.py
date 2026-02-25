import os

from release.settings import PROD_ENV

if PROD_ENV:
    LOG_ROOT = "/var/log/release"
    if not os.path.exists(LOG_ROOT):
        os.mkdir(LOG_ROOT)
else:
    LOG_ROOT = "D:\\devops\\release\\log"
# LOG_ROOT = "C:\\Users\\zxzeng\\Desktop\\project\\release\\log"
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(funcName)s'
                      ' line:%(lineno)d %(message)s'
        },
        'simple': {
            'format': '%(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'global_exception': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_ROOT, 'global_exception.log'),
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 5,
            'formatter': 'verbose'
        },
        'access': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_ROOT, 'access.log'),
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 5,
            'formatter': 'verbose'
        },
        'cron': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_ROOT, 'cron.log'),
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 5,
            'formatter': 'verbose'
        },

    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'global_exception': {
            'handlers': ['global_exception'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'access': {
            'handlers': ['access'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'cron': {
            'handlers': ['cron'],
            'level': 'DEBUG',
            'propagate': True,
        },
    }
}
