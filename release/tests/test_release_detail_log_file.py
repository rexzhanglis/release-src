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
