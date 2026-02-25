'''
LDAP search result example

{
  "primaryGroupID": ["513"],
  "logonCount": ["3931"],
  "cn": ["Han.Bao"],
  "objectClass": ["top", "person", "organizationalPerson", "user"],
  "lastLogonTimestamp": ["131708870477222917"],
  "manager": ["CN=Yuyi.Miao,CN=Users,DC=datayes,DC=com"],
  "instanceType": ["4"],
  "userCertificate": ["..."],
  "objectSid": ["..."],
  "mail": ["han.bao@datayes.com"],
  "badPasswordTime": ["131709150101869567"],
  "sAMAccountName": ["han.bao"],
  "whenChanged": ["20180515194415.0Z"],
  "badPwdCount": ["0"],
  "accountExpires": ["0"],
  "physicalDeliveryOfficeName": ["SH"],
  "name": ["Han.Bao"],
  "memberOf": [
    "CN=team.mktbiz,CN=Users,DC=datayes,DC=com",
    "CN=ZabbixOffice_Access,OU=Groups,DC=datayes,DC=com",
    "CN=team.docker,CN=Users,DC=datayes,DC=com",
    "CN=dataplatform_viewer,OU=Groups,DC=datayes,DC=com",
    "CN=service.grafanaedit,OU=Groups,DC=datayes,DC=com",
    "CN=team.automation,CN=Users,DC=datayes,DC=com",
    "CN=rocketaccounts,OU=Groups,DC=datayes,DC=com",
    "CN=devopsgroups,CN=Users,DC=datayes,DC=com",
    "CN=team.vpc,CN=Users,DC=datayes,DC=com",
    "CN=team.devops,CN=Users,DC=datayes,DC=com",
    "CN=dept.ops,CN=Users,DC=datayes,DC=com",
    "CN=office.shanghai,CN=Users,DC=datayes,DC=com",
    "CN=IM-ywbzzx,OU=Groups,DC=datayes,DC=com",
    "CN=Allstaff,OU=Groups,DC=datayes,DC=com",
    "CN=SVCAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=RemoteAccess-IT,OU=Groups,DC=datayes,DC=com",
    "CN=OpenFireAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=JiraAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=Wifi-DtaYes-Office,OU=Groups,DC=datayes,DC=com",
    "CN=MailAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=eng.infra,OU=Engineer,OU=Groups,DC=datayes,DC=com",
    "CN=JenkinsAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=eng.ops,OU=Engineer,OU=Groups,DC=datayes,DC=com",
    "CN=ISAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=VoipAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=ConfluenceAccounts,OU=Groups,DC=datayes,DC=com",
    "CN=Lan-DataYes-Office,OU=Groups,DC=datayes,DC=com"
  ],
  "codePage": ["0"],
  "sAMAccountType": ["805306368"],
  "uSNChanged": ["164155127"],
  "givenName": ["Han"],
  "lastLogoff": ["0"],
  "employeeID": ["0197"],
  "countryCode": ["0"],
  "userPrincipalName": ["han.bao@datayes.com"],
  "msTSLicenseVersion": ["393216"],
  "distinguishedName": ["CN=Han.Bao,CN=Users,DC=datayes,DC=com"],
  "dSCorePropagationData": ["20161205072516.0Z", "20160104014936.0Z", "20141008084126.0Z", "20141008084005.0Z", "16010714223648.0Z"],
  "msTSExpireDate": ["20180330133847.0Z"],
  "whenCreated": ["20140425065144.0Z"],
  "uSNCreated": ["18851"],
  "department": ["B003"],
  "lockoutTime": ["0"],
  "pwdLastSet": ["131698758129301168"],
  "description": ["Data.User"],
  "msTSManagingLS": ["55041-246-6334615-84561"],
  "objectCategory": ["CN=Person,CN=Schema,CN=Configuration,DC=datayes,DC=com"],
  "objectGUID": ["..."],
  "telephoneNumber": ["8216572"],
  "displayName": ["..."],
  "mobile": ["13736853330"],
  "userAccountControl": ["512"],
  "lastLogon": ["131709150145469659"],
  "sn": ["Bao"]
}
'''
import logging, ldap, os, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from ldap.ldapobject import LDAPObject
from ldap.controls import SimplePagedResultsControl
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.models import Group

from account.models import User

logger = logging.getLogger(__name__)

ATTRS_MAPPING = {
    'username': 'sAMAccountName',
    'last_name': 'sn',
    'first_name': 'givenName',
    'chinese_name': 'displayName',
    'email': 'mail',
    'mobile': 'mobile',
    'manager': 'manager',
}


def sync_ldap_users():
    """
    Synchronize users from ldap
    """
    success_count = 0
    failure_count = 0
    success_list = []

    ldap_users = ldap_search('(&(objectclass=person))', list(ATTRS_MAPPING.values()).append('memberOf'))

    for cname, attrs in ldap_users:
        # In some cases with AD, attrs is a list instead of a
        # dict; these are not valid users, so skip them
        if not isinstance(attrs, dict):
            continue

        # Extract user attributes from LDAP response
        user_data = {
            'is_active': True
        }
        for k, v in ATTRS_MAPPING.items():
            try:
                if k == "manager":
                    user_data[k] = attrs[v][0].decode('utf-8').split(",")[0].split("=")[1]
                else:
                    user_data[k] = attrs[v][0].decode('utf-8')
            except:
                pass
        username = user_data.pop('username')
        try:
            user, created = User.objects.update_or_create(username=username, defaults=user_data)
            # groups
            groups = []
            for group_info in attrs['memberOf']:
                group_info = group_info.decode("utf-8")
                cn, _ = group_info.split(',', 1)
                _, name = cn.split('=')
                if name.startswith(('dept.', 'team.')):
                    group, _ = Group.objects.get_or_create(name=name)
                    groups.append(group)
            user.groups.set(groups)
        except:
            failure_count += 1
            continue
        else:
            success_count += 1
            success_list.append(username)

    if success_list:  # in case of no success at all, stop changing all profile to inactive
        User.objects.all().exclude(username__in=success_list).update(is_active=False)

    return success_count, failure_count


def ldap_search(filter, attributes):
    """
    Query the configured LDAP server with the provided search
    filter and attribute list. Returns a list of the results
    returned.
    """
    uri = getattr(settings, 'AUTH_LDAP_SERVER_URI', None)
    if not uri:
        error_msg = ("LDAP_URI must be specified in your Django "
                     "settings file")
        raise ImproperlyConfigured(error_msg)

    base_user = getattr(settings, 'AUTH_LDAP_BIND_DN', None)
    if not base_user:
        error_msg = ("LDAP_SYNC_BIND_DN must be specified in your "
                     "Django settings file")
        raise ImproperlyConfigured(error_msg)

    base_pass = getattr(settings, 'AUTH_LDAP_BIND_PASSWORD', None)
    if not base_pass:
        error_msg = ("LDAP_SYNC_BIND_PASSWORD must be specified in your "
                     "Django settings file")
        raise ImproperlyConfigured(error_msg)

    base = 'CN=Users,DC=datayes,DC=com'

    ldap.set_option(ldap.OPT_REFERRALS, 0)
    l = PagedLDAPObject(uri)
    l.protocol_version = 3
    try:
        l.simple_bind_s(base_user, base_pass)
    except ldap.LDAPError:
        logger.error("Error connecting to LDAP server %s" % uri)
        raise

    results = l.paged_search_ext_s(base,
                                   ldap.SCOPE_SUBTREE,
                                   filter,
                                   attrlist=attributes,
                                   serverctrls=None)
    l.unbind_s()
    return results


class PagedResultsSearchObject:
    """
    Taken from the python-ldap paged_search_ext_s.py demo, showing how to use
    the paged results control: https://bitbucket.org/jaraco/python-ldap/
    """
    page_size = getattr(settings, 'LDAP_SYNC_PAGE_SIZE', 100)

    def paged_search_ext_s(self, base, scope, filterstr='(objectClass=*)',
                           attrlist=None, attrsonly=0, serverctrls=None,
                           clientctrls=None, timeout=-1, sizelimit=0):
        """
        Behaves exactly like LDAPObject.search_ext_s() but internally uses the
        simple paged results control to retrieve search results in chunks.
        """
        req_ctrl = SimplePagedResultsControl(True, size=self.page_size,
                                             cookie='')

        # Send first search request
        msgid = self.search_ext(base, ldap.SCOPE_SUBTREE, filterstr,
                                attrlist=attrlist,
                                serverctrls=(serverctrls or []) + [req_ctrl])
        results = []

        while True:
            rtype, rdata, rmsgid, rctrls = self.result3(msgid)
            results.extend(rdata)
            # Extract the simple paged results response control
            pctrls = [c for c in rctrls if c.controlType ==
                      SimplePagedResultsControl.controlType]

            if pctrls:
                if pctrls[0].cookie:
                    # Copy cookie from response control to request control
                    req_ctrl.cookie = pctrls[0].cookie
                    msgid = self.search_ext(base, ldap.SCOPE_SUBTREE,
                                            filterstr, attrlist=attrlist,
                                            serverctrls=(serverctrls or []) +
                                                        [req_ctrl])
                else:
                    break

        return results


class PagedLDAPObject(LDAPObject, PagedResultsSearchObject):
    pass


if __name__ == '__main__':
    sync_ldap_users()
