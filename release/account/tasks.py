from account.ldap_sync import sync_ldap_users
from common.decorator import cron_log


@cron_log
def ldap_sync_user_task():
    sync_ldap_users()


if __name__ == '__main__':
    ldap_sync_user_task()
