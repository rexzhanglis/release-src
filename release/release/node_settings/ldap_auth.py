"""
author: zhixiong.zeng
python version: 3
time: 2021/4/29 14:16
"""

import ldap

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)


from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

AUTH_LDAP_SERVER_URI = 'ldap://sh-it-ad02.datayes.com:389'
AUTH_LDAP_BIND_DN = "CN=SVC-Jenkins,OU=SVC,OU=ServiceAccounts,DC=datayes,DC=com"
AUTH_LDAP_BIND_PASSWORD = "wjOl8Tf1tCuD"
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    "CN=Users,DC=datayes,DC=com", ldap.SCOPE_SUBTREE, "(sAMAccountName=%(user)s)"
)

AUTH_LDAP_GROUP_SEARCH = LDAPSearch("OU=Groups,DC=datayes,DC=com",
                                    ldap.SCOPE_SUBTREE, "(objectClass=groupOfNames)"
                                    )

AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(name_attr="cn")

AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    # 定义用户可以登录admin后台的组是哪个，前面ldap中已经创建了这个组，并加入了指定用户
    # 默认创建的django用户是不能登录admin后台的
    "is_staff": "CN=Allstaff,OU=Groups,DC=datayes,DC=com",
}

AUTH_LDAP_ALWAYS_UPDATE_USER = True

# AUTHENTICATION_BACKENDS = (
#     'django.contrib.auth.backends.ModelBackend',
#     'django_auth_ldap.backend.LDAPBackend',
# )

AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": "givenName",
    "last_name": "sn",
    "email": "mail",
    "mobile": "mobile"
}
