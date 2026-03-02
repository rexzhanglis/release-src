# 自动化测试文档

## 概述

本测试套件覆盖 release-src 项目三个核心功能模块：

| 模块 | 测试文件 | 测试数量 | 覆盖场景 |
|------|----------|----------|----------|
| 配置管理 | `test_config_mgmt.py` | ~28 | 更新/批量/替换/Git提交/部署/回滚/历史 |
| 服务器初始化 | `test_server_init.py` | ~16 | 启动/状态查询/Ansible执行/CRUD |
| 发布流程 | `test_release.py` | ~14 | 发布/并发限制/暂停/回滚限制 |

---

## 快速开始

### 1. 安装测试依赖

```bash
cd release/
pip install pytest pytest-django
```

> `responses` 库用于 Mock HTTP（可选，当前测试使用 `unittest.mock`）：
> ```bash
> pip install responses
> ```

### 2. 运行所有测试

```bash
cd release/
python -m pytest tests/ -v
```

### 3. 运行单个模块测试

```bash
# 只跑配置管理测试
python -m pytest tests/test_config_mgmt.py -v

# 只跑服务器初始化测试
python -m pytest tests/test_server_init.py -v

# 只跑发布流程测试
python -m pytest tests/test_release.py -v
```

### 4. 运行单个测试类或测试方法

```bash
# 运行指定测试类
python -m pytest tests/test_config_mgmt.py::TestConfigFileUpdate -v

# 运行指定测试方法
python -m pytest tests/test_config_mgmt.py::TestConfigFileUpdate::test_update_config_content -v
```

### 5. 查看测试结果摘要

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

---

## 测试环境配置

### settings_test.py 说明

测试使用独立的 Django settings 文件 `release/release/settings_test.py`：

| 配置项 | 测试值 | 说明 |
|--------|--------|------|
| `DATABASES` | SQLite `:memory:` | 测试后自动销毁，无需外部 MySQL |
| `INSTALLED_APPS` | 去掉 django_cas_ng, easyaudit | 避免外部依赖 |
| `MIDDLEWARE` | 精简版 | 去掉 CAS/EasyAudit middleware |
| `CONFIG_GITLAB_URL` | `http://mock-gitlab.test` | 防止意外调用真实 GitLab |
| `CONFIG_CONSUL_URL` | `http://mock-consul.test` | 防止意外推送 Consul |

### pytest.ini 说明

```ini
[pytest]
DJANGO_SETTINGS_MODULE = release.settings_test
python_files = tests/test_*.py
addopts = -v --tb=short
```

---

## Mock 策略

测试中所有外部依赖均被 Mock，不会触碰真实服务：

### 1. Ansible / subprocess
```python
@patch('subprocess.run')
def test_xxx(self, mock_subproc):
    mock_subproc.return_value = MagicMock(returncode=0, stdout='PLAY RECAP ok=5\n')
```

### 2. 后台线程（让 `run()` 同步执行）
```python
captured_target = {}

def fake_thread(target=None, daemon=None, **kwargs):
    captured_target['fn'] = target
    return MagicMock(start=lambda: None)

with patch('threading.Thread', side_effect=fake_thread):
    # ... 发起请求 ...

# 手动同步执行线程函数
captured_target['fn']()
```

### 3. GitLab API
```python
@patch('api.viewsets.config_mgmt_viewset._commit_to_gitlab')
def test_git_commit(self, mock_commit):
    mock_commit.return_value = [{'file': 'f.cfg', 'status': 'ok'}]
```

### 4. MDL 发布服务
```python
@patch('api.viewsets.release_detail_viewset.MdlReleaseDetailService')
def test_deploy(self, mock_service_class):
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service
```

---

## 测试用例详情

### test_config_mgmt.py

| 测试类 | 测试方法 | 描述 |
|--------|----------|------|
| `TestConfigFileUpdate` | `test_update_config_content` | PUT 更新配置，验证 DB 内容 |
| | `test_update_config_preserves_raw_content` | raw_content 正确保存 |
| | `test_update_without_raw_content_does_not_clear_existing` | 不传 raw_content 不清空已有值 |
| | `test_update_creates_history_snapshot` | 更新后自动创建快照 |
| | `test_update_snapshot_stores_old_content` | 快照保存的是旧内容 |
| `TestBatchUpdate` | `test_batch_update_same_key_across_instances` | 批量修改多实例同一 key |
| | `test_batch_update_delete_key` | `__DELETE__` 删除 key |
| | `test_batch_update_creates_history_snapshots` | 批量操作创建快照 |
| | `test_batch_update_missing_params_returns_400` | 缺参数返回 400 |
| `TestTextReplace` | `test_text_replace_preview_does_not_save` | 预览模式不保存 |
| | `test_text_replace_preview_returns_diff` | 预览返回 diff |
| | `test_text_replace_save_updates_db` | 保存模式更新 DB |
| | `test_text_replace_no_match_returns_unchanged` | 无匹配时 changed=False |
| | `test_text_replace_missing_search_text_returns_400` | 空 search_text 返回 400 |
| `TestGitCommit` | `test_git_commit_success` | Git 提交成功 |
| | `test_git_commit_partial_failure` | 部分失败时消息准确 |
| | `test_git_commit_without_config_ids_returns_400` | 缺参数返回 400 |
| `TestConfigDeploy` | `test_create_deploy_task_returns_task_id` | 部署返回 task_id |
| | `test_deploy_task_creates_snapshot_before_deploy` | 部署前创建快照 |
| | `test_get_deploy_task_detail` | 查询任务详情 |
| | `test_get_nonexistent_deploy_task_returns_404` | 任务不存在返回 404 |
| | `test_deploy_missing_instance_ids_returns_400` | 缺参数返回 400 |
| `TestDeployRollback` | `test_rollback_restores_config_content` | 回滚恢复配置内容 |
| | `test_rollback_returns_rolled_back_files` | 响应包含文件列表 |
| | `test_rollback_nonexistent_task_returns_404` | 任务不存在返回 404 |
| | `test_rollback_task_without_snapshot_returns_400` | 无快照返回 400 |
| `TestConfigHistory` | `test_list_history_returns_records` | 历史列表查询 |
| | `test_get_history_detail` | 历史详情含 content |
| | `test_rollback_to_history_version` | 回滚到历史版本 |
| `TestHelperFunctions` | `test_set_nested_value_*` | 嵌套 key 设置 |
| | `test_delete_nested_value` | 嵌套 key 删除 |

### test_server_init.py

| 测试类 | 测试方法 | 描述 |
|--------|----------|------|
| `TestInitServerStart` | `test_init_returns_task_id` | 立即返回 task_id |
| | `test_init_creates_deploy_task_in_db` | 创建 DB 任务，status=running |
| | `test_init_starts_background_thread` | 启动后台线程 |
| | `test_init_nonexistent_server_returns_404` | 服务器不存在返回 404 |
| | `test_init_egress_false_by_default` | 默认非出口机器正常启动 |
| `TestInitServerStatus` | `test_init_status_returns_running` | 运行中状态查询 |
| | `test_init_status_returns_log` | 响应包含日志 |
| | `test_init_status_missing_task_id_returns_400` | 缺 task_id 返回 400 |
| | `test_init_status_nonexistent_task_returns_404` | 任务不存在返回 404 |
| | `test_init_status_success_after_completion` | 完成后状态为 success |
| `TestInitServerThread` | `test_ansible_subprocess_called_on_init` | Ansible 被调用 |
| | `test_task_status_becomes_success_on_returncode_0` | rc=0 → status=success |
| | `test_task_status_becomes_failed_on_nonzero_returncode` | rc!=0 → status=failed |
| | `test_ansible_env_has_host_key_checking_disabled` | 禁用 host key checking |
| `TestMdlServerCRUD` | `test_list_servers` | 服务器列表 |
| | `test_get_server_detail` | 服务器详情 |
| | `test_create_server` | 创建服务器 |
| | `test_update_server` | 更新服务器 |
| | `test_delete_server` | 删除服务器 |

### test_release.py

| 测试类 | 测试方法 | 描述 |
|--------|----------|------|
| `TestReleasePlanCRUD` | `test_list_release_plans` | 计划列表 |
| | `test_create_mdl_release_plan` | 创建 MDL 计划 |
| | `test_get_release_plan_detail` | 计划详情 |
| | `test_duplicate_plan_name_fails` | 重复名称创建失败 |
| `TestMdlDeploy` | `test_deploy_mdl_plan_success` | 触发 MDL 发布 |
| | `test_deploy_creates_release_detail` | 创建发布详情 |
| | `test_deploy_nonexistent_plan_returns_error` | 计划不存在返回错误 |
| `TestMdlConcurrentDeployLimit` | `test_second_mdl_deploy_is_rejected` | 并发发布被拒绝 |
| `TestReleaseSuspend` | `test_suspend_mdl_plan` | 暂停发布 |
| `TestMdlRollback` | `test_mdl_rollback_is_rejected` | MDL 不支持回滚 |
| | `test_rancher_rollback_within_7days` | Rancher 7天内可回滚 |
| `TestGetReleaseDetailInfo` | `test_get_release_detail_info_by_name` | 查询发布详情 |
| | `test_get_release_detail_without_name_returns_error` | 缺参数返回错误 |
| | `test_get_release_detail_with_step_status` | 包含 step_status |
| `TestMdlReleaseContent` | `test_release_content_status_choices` | 状态字段值 |
| | `test_plan_get_all_contents_returns_list` | 获取发布内容列表 |
| | `test_plan_delete_release_contents` | 删除发布内容 |

---

## 常见问题

### Q: `ModuleNotFoundError: No module named 'django_cas_ng'`
A: 安装 `pip install django-cas-ng`，或确认 `settings_test.py` 已从 `INSTALLED_APPS` 中移除。

### Q: `OperationalError: no such table: ...`
A: 测试使用 SQLite 内存数据库，pytest-django 会自动运行 `migrate`。如果报错，检查 `pytest.ini` 中 `DJANGO_SETTINGS_MODULE` 是否正确。

### Q: `ImportError: cannot import name 'xxx' from 'api.viewsets.config_mgmt_viewset'`
A: 检查对应函数是否存在于 `config_mgmt_viewset.py` 中（`set_nested_value`, `_delete_nested_value` 等）。

### Q: 测试通过但实际功能失败
A: 部分测试 Mock 了 Ansible subprocess。需在真实 Linux 环境上运行集成测试验证完整流程。

---

## 扩展测试

如需新增测试，请在 `tests/` 目录下创建 `test_xxx.py` 文件，继承 `django.test.TestCase`，命名以 `test_` 开头即可被 pytest 自动发现。

```python
from django.test import TestCase
from rest_framework.test import APIClient

class TestNewFeature(TestCase):
    def setUp(self):
        # 初始化数据
        pass

    def test_my_case(self):
        # 断言
        self.assertEqual(1 + 1, 2)
```
