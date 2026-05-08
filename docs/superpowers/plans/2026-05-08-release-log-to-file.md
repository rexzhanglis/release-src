# 发布日志写文件改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ReleaseDetail.set_log` 的 ansible 实时输出从 DB 切换为本地文件 `/datayes/release/logs/release_detail_{id}.log`，解决高频 DB 写入压力与 MySQL `gone away` 问题。

**Architecture:** `set_log` 内部改写为 append 文件；`prompt` 字段仍写库（仅当 `update_prompt=True`，且只 save `prompt` 字段）；DB `log` 列保留不删但不再写入。读取接口 `get_release_detail_info` 优先读文件，文件不存在时回退到 DB `log` 列以兼容旧记录。前端无任何改动。

**Tech Stack:** Django 3.2 / Python 3.9 / pytest / MySQL；Linux 部署。

**Spec:** `docs/superpowers/specs/2026-05-08-release-log-to-file-design.md`

---

## File Structure

| 文件 | 角色 |
|------|------|
| `release/api/models.py` | 引入模块常量 `RELEASE_LOG_DIR`；改写 `ReleaseDetail.set_log` 行为 |
| `release/api/viewsets/release_detail_viewset.py` | `get_release_detail_info` 改为读文件并填回 `data['log']`，文件缺失时回退 DB 列 |
| `release/tests/test_release_detail_log_file.py` | 新增：`set_log` 写文件的单元测试 + viewset 读取行为的集成测试 |

未涉及：DB schema、frontend、DeployTask 相关 viewset、日志清理 / 轮转。

---

## Task 1：`ReleaseDetail.set_log` 改写文件

**Files:**
- Modify: `release/api/models.py`（位置：模块顶部 import 区 + `ReleaseDetail.set_log` 方法，约 13–15 行 import / 190–197 行方法体）
- Test: `release/tests/test_release_detail_log_file.py`（新建）

### Step 1.1：写失败的单元测试

- [ ] **Step 1.1：写 set_log 写文件 + prompt 行为的失败测试**

新建 `release/tests/test_release_detail_log_file.py`，写入：

```python
"""
ReleaseDetail.set_log 写文件改造的单测。
覆盖：
  1. 首次调用：自动创建目录 + 写一行
  2. 多次调用：追加而非覆盖
  3. update_prompt=True：prompt 入库且 log DB 列保持空
  4. update_prompt=False：完全不写库
  5. 写文件抛异常：函数被吞掉异常，不向上抛（关键约束）
"""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from api import models as api_models
from api.models import ReleasePlan, ReleaseDetail

User = get_user_model()


class _SetLogFileBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='log_user', password='pw')
        self.plan = ReleasePlan.objects.create(
            name='log-plan-001', project='MDL', owner='log_user',
        )
        self.detail = ReleaseDetail.objects.create(
            release_plan=self.plan, user='log_user', status='升级中',
        )
        # 重定向日志目录到 pytest 提供的临时目录，避免污染 /datayes/release/logs
        self._tmp = self._make_tmp_dir()
        self._patch_dir = patch.object(api_models, 'RELEASE_LOG_DIR', self._tmp)
        self._patch_dir.start()

    def tearDown(self):
        self._patch_dir.stop()

    def _make_tmp_dir(self):
        import tempfile
        return tempfile.mkdtemp(prefix='release_log_test_')

    def _log_path(self):
        return os.path.join(self._tmp, 'release_detail_{}.log'.format(self.detail.id))


class TestSetLogWritesFile(_SetLogFileBase):
    def test_first_call_creates_file_and_writes_one_line(self):
        # 删掉 setUp 创建的 tmp 目录，验证首次调用会自动创建
        import shutil
        shutil.rmtree(self._tmp)

        self.detail.set_log("hello", self.user, update_prompt=False)

        self.assertTrue(os.path.exists(self._log_path()))
        with open(self._log_path(), encoding='utf-8') as f:
            content = f.read()
        self.assertIn("hello", content)
        self.assertIn("info", content)
        # 行末有换行
        self.assertTrue(content.endswith("\n"))

    def test_multiple_calls_append(self):
        self.detail.set_log("first", self.user, update_prompt=False)
        self.detail.set_log("second", self.user, update_prompt=False)

        with open(self._log_path(), encoding='utf-8') as f:
            content = f.read()
        self.assertIn("first", content)
        self.assertIn("second", content)
        self.assertEqual(content.count("\n"), 2)

    def test_update_prompt_true_writes_prompt_only(self):
        self.detail.set_log("step msg", self.user, update_prompt=True)

        # 重新从 DB 拉取
        self.detail.refresh_from_db()
        self.assertEqual(self.detail.prompt, "step msg")
        # log 列保持空（不再写）
        self.assertIn(self.detail.log, (None, ""))

    def test_update_prompt_false_does_not_touch_db(self):
        original_prompt = self.detail.prompt
        original_log = self.detail.log

        self.detail.set_log("stdout line", self.user, update_prompt=False)

        self.detail.refresh_from_db()
        self.assertEqual(self.detail.prompt, original_prompt)
        self.assertEqual(self.detail.log, original_log)

    def test_file_write_failure_is_swallowed(self):
        """
        关键约束：写文件异常必须被吞，否则 _read_stdout 线程崩溃，
        ansible stdout pipe 无人消费会导致整个部署卡死。
        """
        with patch('builtins.open', side_effect=OSError("disk full")):
            # 不应抛异常
            self.detail.set_log("line", self.user, update_prompt=False)
```

- [ ] **Step 1.2：运行测试，确认失败**

```bash
cd release && pytest tests/test_release_detail_log_file.py -v
```

Expected: 5 个用例全部失败 —— 报错可能是 `AttributeError: module 'api.models' has no attribute 'RELEASE_LOG_DIR'`，或 `set_log` 仍按旧逻辑写 DB 列导致断言失败。

- [ ] **Step 1.3：实现 set_log 写文件**

修改 `release/api/models.py`：

**A. 文件顶部 import 区域（约第 13 行下方），改成：**

```python
import datetime
import logging
import os

from django.db import models

from common.basemodels import TimestampedModel

# ReleaseDetail 发布日志文件目录（按 release_detail_{id}.log 命名）
# Linux 部署写死，未来如需变更直接改这里
RELEASE_LOG_DIR = '/datayes/release/logs'

_log_writer_logger = logging.getLogger(__name__)
```

**B. 替换 `ReleaseDetail.set_log` 方法（约第 190–197 行）：**

```python
    def set_log(self, log, user, level="info", update_prompt=True):
        """
        发布日志写本地文件，DB 上不再追加 log 字段。

        - 文件路径：{RELEASE_LOG_DIR}/release_detail_{id}.log
        - 行格式：与历史一致 "{ts} {level} {user} {msg}\n"
        - 写文件异常必须被吞：_read_stdout 线程若抛会导致 ansible
          stdout pipe 无人消费，进而卡死整个部署进程。
        - prompt 仍按 update_prompt 入库；仅 save(update_fields=['prompt'])
          以减小写入体积，避免覆盖其他字段。
        """
        line = "{} {} {} {}\n".format(datetime.datetime.now(), level, user, log)
        try:
            os.makedirs(RELEASE_LOG_DIR, exist_ok=True)
            log_path = os.path.join(
                RELEASE_LOG_DIR, "release_detail_{}.log".format(self.id),
            )
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception as ex:
            # 关键：不向上抛，避免拖死 _read_stdout 线程导致 ansible 卡死
            _log_writer_logger.warning(
                "write release log file failed (detail_id=%s): %s", self.id, ex,
            )

        if update_prompt:
            self.prompt = log
            self.save(update_fields=['prompt'])
```

- [ ] **Step 1.4：运行测试，确认通过**

```bash
cd release && pytest tests/test_release_detail_log_file.py -v
```

Expected: 5/5 PASS。

- [ ] **Step 1.5：跑回归测试，确认未打破现有用例**

```bash
cd release && pytest tests/test_mdl_release_detail_service.py tests/test_release_detail_viewset.py -v
```

Expected: 全部 PASS（这些测试主要 patch 了 `set_log`，不依赖其内部实现）。

- [ ] **Step 1.6：commit**

```bash
git add release/api/models.py release/tests/test_release_detail_log_file.py
git commit -m "refactor: ReleaseDetail.set_log 写文件，DB 仅保留 prompt 字段"
```

---

## Task 2：`get_release_detail_info` 读文件 + 兼容旧数据

**Files:**
- Modify: `release/api/viewsets/release_detail_viewset.py:35-51`（`get_release_detail_info` action）
- Test: `release/tests/test_release_detail_log_file.py`（追加用例）

- [ ] **Step 2.1：追加失败的集成测试**

在 `release/tests/test_release_detail_log_file.py` 末尾追加：

```python
from rest_framework.test import APIRequestFactory, force_authenticate

from api.viewsets.release_detail_viewset import ReleaseDetailViewSet


class TestGetReleaseDetailInfoLogSource(_SetLogFileBase):
    """
    get_release_detail_info 响应里 data['log'] 的来源：
      - 文件存在 → 文件内容
      - 文件不存在 → 回退 DB log 列（兼容旧记录）
    """

    def _call_get_release_detail_info(self):
        factory = APIRequestFactory()
        request = factory.get(
            '/api/releaseDetail/get_release_detail_info/',
            {'name': self.plan.name},
        )
        force_authenticate(request, user=self.user)
        view = ReleaseDetailViewSet.as_view({'get': 'get_release_detail_info'})
        response = view(request)
        return response

    def test_log_comes_from_file_when_file_exists(self):
        # 写一行触发文件创建
        self.detail.set_log("from-file", self.user, update_prompt=False)

        response = self._call_get_release_detail_info()
        self.assertEqual(response.status_code, 200)
        log_value = response.data['data']['log']
        self.assertIn("from-file", log_value)

    def test_log_falls_back_to_db_column_when_file_missing(self):
        # 模拟旧记录：文件不存在，DB log 列有值
        self.assertFalse(os.path.exists(self._log_path()))
        ReleaseDetail.objects.filter(id=self.detail.id).update(
            log="legacy-from-db\n",
        )

        response = self._call_get_release_detail_info()
        self.assertEqual(response.status_code, 200)
        log_value = response.data['data']['log']
        self.assertIn("legacy-from-db", log_value)
```

- [ ] **Step 2.2：运行测试，确认失败**

```bash
cd release && pytest tests/test_release_detail_log_file.py::TestGetReleaseDetailInfoLogSource -v
```

Expected: `test_log_comes_from_file_when_file_exists` 失败（响应里 `log` 仍是 DB 列值，即 `None` / `""`）。

- [ ] **Step 2.3：修改 `get_release_detail_info` 读文件**

`release/api/viewsets/release_detail_viewset.py` 顶部 import 区追加：

```python
import os

from api.models import RELEASE_LOG_DIR
```

替换 `get_release_detail_info` 方法（第 35–51 行）的方法体为：

```python
    @action(detail=False, methods=["get"], url_path="get_release_detail_info")
    def get_release_detail_info(self, request, *args, **kwargs):
        """
        获取发布的详细信息。

        log 字段来源：
          - 优先读文件 {RELEASE_LOG_DIR}/release_detail_{id}.log
          - 文件不存在时回退到 DB log 列（兼容旧记录）
        """
        name = request.query_params.get("name")
        if name:
            release_plan = ReleasePlan.objects.get(name=name)
            obj = ReleaseDetail.objects.filter(release_plan=release_plan)
            if obj:
                detail = obj[0]
                data = model_to_dict(detail)
                data["created_time"] = detail.created_time
                data["last_updated_time"] = detail.last_updated_time
                data["step_status"] = release_plan.get_all_release_contents_status()
                data["log"] = self._read_release_log(detail)
                return ApiResponse(data=data)
            return ApiResponse(data=None)
        raise CustomRuntimeException("请输入name字段")

    @staticmethod
    def _read_release_log(detail):
        """文件存在则读文件，否则回退 DB log 列。读异常一律回退。"""
        log_path = os.path.join(
            RELEASE_LOG_DIR, "release_detail_{}.log".format(detail.id),
        )
        try:
            with open(log_path, encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return detail.log or ""
        except Exception:
            # 读异常时回退 DB 列，不影响整个接口
            return detail.log or ""
```

- [ ] **Step 2.4：运行测试，确认通过**

```bash
cd release && pytest tests/test_release_detail_log_file.py -v
```

Expected: 7/7 PASS（Task 1 的 5 个 + Task 2 的 2 个）。

- [ ] **Step 2.5：跑全部相关测试**

```bash
cd release && pytest tests/test_release_detail_viewset.py tests/test_mdl_release_detail_service.py tests/test_release_detail_log_file.py -v
```

Expected: 全部 PASS。

- [ ] **Step 2.6：commit**

```bash
git add release/api/viewsets/release_detail_viewset.py release/tests/test_release_detail_log_file.py
git commit -m "refactor: get_release_detail_info 从文件读发布日志，旧记录回退 DB"
```

---

## Task 3：全套件回归 + 手工验证

**Files:** 无代码改动；只跑测试与人工核对。

- [ ] **Step 3.1：跑完整测试套件**

```bash
cd release && pytest -v
```

Expected: 全部 PASS。若有失败，按错误信息定位，不要绕过。

- [ ] **Step 3.2：人工 smoke check（部署到测试环境后）**

按以下清单核对：

1. 触发一次完整 MDL 发布。
2. 确认 `/datayes/release/logs/release_detail_{id}.log` 文件被创建，内容随 ansible 实时滚动。
3. 前端发布详情页能持续看到日志（与改造前一致），无空白、无报错。
4. 在数据库执行：

   ```sql
   SELECT id, log FROM api_releasedetail WHERE id = <本次 id>;
   ```

   `log` 列应为空 / NULL（不再被写入）。
5. `prompt` 列随发布步骤更新（验证 `update_prompt=True` 路径仍生效）。
6. 跑一条已有的旧 ReleaseDetail（文件不存在），前端打开详情页应能看到 DB 列里的历史日志（兼容回退）。

- [ ] **Step 3.3：若 smoke check 全过，无需额外 commit。**

如有发现，按反馈修复，新建 fix commit。

---

## Spec 覆盖核对

| Spec 要求 | 对应任务 |
|-----------|----------|
| 文件路径 `/datayes/release/logs/release_detail_{id}.log` | Task 1 Step 1.3 |
| 行格式 `{ts} {level} {user} {msg}\n` | Task 1 Step 1.3 |
| 目录自动创建 | Task 1 Step 1.3（`os.makedirs(..., exist_ok=True)`） |
| set_log 不再写 `log` 列 | Task 1 Step 1.3 |
| `prompt` 仅在 `update_prompt=True` 时入库 + `update_fields=['prompt']` | Task 1 Step 1.3 |
| 写文件异常被吞，不向上抛 | Task 1 Step 1.3 + Step 1.1 用例 5 |
| 读取优先文件，缺失时回退 DB 列 | Task 2 Step 2.3 |
| 前端零改动（响应仍含 `log` 键） | Task 2 Step 2.3（`data['log']` 仍设置） |
| DB schema 不变 | 全程未涉及 migration |
| 测试覆盖 set_log 各分支 + viewset 来源切换 | Task 1 Step 1.1 + Task 2 Step 2.1 |
| 旧 `_read_stderr` 限制（可选改进） | 显式不在本次范围（spec 与 plan 均明确） |
