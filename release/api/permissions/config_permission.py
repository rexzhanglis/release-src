"""
MDL 配置管理权限分级

角色层级（从高到低）：
  config_admin    - 管理员：完整权限（查看、编辑、Git/Consul、部署、回滚、删除）
                    来源：Constance.admin 列表
  config_operator - 运维：可以编辑 + 提交 Git + 推送 Consul + 历史回滚，不能部署
                    来源：Django Group "team.devops"  或 Constance.deployer 列表
  config_viewer   - 只读：只能查看配置和审计日志，不能修改
                    来源：其他所有已登录用户

权限矩阵：
  操作                       viewer  operator  admin
  --------------------------------------------------
  查看配置树 / 详情            ✓       ✓         ✓
  查看审计日志 / 历史           ✓       ✓         ✓
  编辑 / 保存单文件             ✗       ✓         ✓
  批量修改 / 文本替换           ✗       ✓         ✓
  提交 Git                     ✗       ✓         ✓
  推送 Consul                  ✗       ✓         ✓
  同步 GitLab                  ✗       ✓         ✓
  历史回滚                     ✗       ✓         ✓
  一致性巡检（只读结果）         ✓       ✓         ✓
  部署（Ansible）               ✗       ✗         ✓
"""

from rest_framework import permissions

from const.models import Constance


def _get_constance_list(key):
    """安全读取 Constance 列表，key 不存在时返回空列表"""
    try:
        return Constance.get_value(key)
    except Exception:
        return []


class ConfigMgmtPermission(permissions.BasePermission):
    """
    基础权限类：所有配置管理接口都继承此类。
    只读操作（GET/HEAD/OPTIONS）对已登录用户全部放行。
    写操作需要 operator 及以上角色。
    """

    def _is_admin(self, user):
        return user.username in _get_constance_list('admin')

    def _is_operator(self, user):
        """operator = devops 组成员 OR deployer 列表"""
        if user.groups.filter(name='team.devops').exists():
            return True
        if user.username in _get_constance_list('deployer'):
            return True
        return False

    def has_permission(self, request, view):
        # 未登录拒绝
        if not request.user or not request.user.is_authenticated:
            return False
        # 只读操作放行
        if request.method in permissions.SAFE_METHODS:
            return True
        # 写操作需要 operator 及以上
        return self._is_admin(request.user) or self._is_operator(request.user)


class ConfigDeployPermission(ConfigMgmtPermission):
    """
    部署操作专用权限：只有 admin 才能执行 Ansible 部署。
    用于 ConfigDeployViewSet.create()
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        # 部署只允许 admin
        return self._is_admin(request.user)
