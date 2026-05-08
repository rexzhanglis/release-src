"""
author: zhixiong.zeng
python version: 3
time: 2021/10/11 13:24
"""
import logging
import subprocess
import time

import yaml
import os, django

deploy_logger = logging.getLogger('deploy')

# 模块级注册表：追踪每个 release_detail 正在运行的 ansible-playbook 子进程
# key: release_detail.id  value: subprocess.Popen
# 用于在 fail_retry / fail_skip 时强制终止旧进程，防止并发部署互相干扰
import threading as _reg_lock_mod
_ansible_proc_registry: dict = {}
_ansible_proc_lock = _reg_lock_mod.Lock()

try:
    import ansible_runner
except Exception:
    import subprocess as _subprocess
    import platform as _platform

    class AnsibleRunnerMock:
        @staticmethod
        def run_command(executable_cmd, cmdline_args, **kwargs):
            if _platform.system() == 'Windows':
                print(f"[MOCK] Executing: {executable_cmd} {' '.join(cmdline_args)}")
                return "Mock Ansible Success\nSkipping actual execution on Windows.", "", 0
            env = kwargs.get('envvars', kwargs.get('env', os.environ.copy()))
            cwd = kwargs.get('cwd', None)
            res = _subprocess.run([executable_cmd] + cmdline_args,
                                  capture_output=True, text=True, env=env, cwd=cwd)
            return res.stdout, res.stderr, res.returncode

    ansible_runner = AnsibleRunnerMock()

from external.consul_client import ConsulClient
from external.gitlab_client import GitlabClient
from external.ssh_client import SshClient

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "release.settings")
django.setup()

from django.db import close_old_connections, connection as db_connection

from api.models import MdlReleaseContent
from api.services.release_detail_service import ReleaseDetailService
from const.models import Constance
from mdl.models import MdlServer


class MdlReleaseDetailService(ReleaseDetailService):

    def upgrade(self, modules):
        import threading
        from django.db import connection

        # 动态超时：每台机器预留 5 分钟（可在 Constance 中配置 mdl_deploy_timeout_per_machine），至少 10 分钟
        try:
            timeout_per_machine = max(60, int(Constance.get_value("mdl_deploy_timeout_per_machine")))
        except Exception:
            timeout_per_machine = 300
        # 每台机器除 ansible 本身外还有 GitLab/Consul/SSH/DB 等操作，额外预留 60s buffer
        UPGRADE_TIMEOUT = max(600, len(list(modules)) * (timeout_per_machine + 60))

        self.release_detail.set_status("发布中")

        def _run():
            connection.close()
            self._do_upgrade(modules)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        def _watchdog():
            t.join(timeout=UPGRADE_TIMEOUT)
            if t.is_alive():
                # 主动终止遗留的 ansible-playbook 子进程，防止僵尸进程占用资源
                with _ansible_proc_lock:
                    stale_proc = _ansible_proc_registry.pop(self.release_detail.id, None)
                if stale_proc and stale_proc.poll() is None:
                    stale_proc.kill()
                    deploy_logger.warning(
                        "[watchdog] 发布超时，强制终止 ansible-playbook pid=%s release_detail=%s",
                        stale_proc.pid, self.release_detail.id,
                    )
                self.release_detail.set_log(
                    "发布超时（超过 {} 秒），自动标记为发布失败，请检查目标机器后点击失败重试或失败跳过".format(UPGRADE_TIMEOUT),
                    self.user,
                    level="error",
                )
                self.release_detail.set_status("发布失败")

        threading.Thread(target=_watchdog, daemon=True).start()

    def _kill_stale_ansible(self, action: str):
        """终止当前 release_detail 上一次遗留的 ansible-playbook 子进程"""
        with _ansible_proc_lock:
            old_proc = _ansible_proc_registry.pop(self.release_detail.id, None)
        if old_proc and old_proc.poll() is None:
            old_proc.kill()
            deploy_logger.warning(
                "[%s] %s: 强制终止旧 ansible-playbook 进程 pid=%s release_detail=%s",
                self.user, action, old_proc.pid, self.release_detail.id,
            )

    def fail_skip(self):
        """
        MDL失败跳过：支持发布失败、回滚失败，以及发布中/升级中卡住的恢复
        """
        self._kill_stale_ansible("fail_skip")
        self.release_detail.refresh_from_db()
        if self.release_detail.status in ("发布中", "升级中"):
            self.release_detail.set_log("检测到发布中状态卡住，执行失败跳过", self.user)
            self.release_detail.set_status("发布失败")
        super().fail_skip()

    def fail_retry(self):
        """
        MDL失败重试：支持发布失败、回滚失败，以及发布中/升级中卡住的恢复
        """
        self._kill_stale_ansible("fail_retry")
        self.release_detail.refresh_from_db()
        if self.release_detail.status in ("发布中", "升级中"):
            self.release_detail.set_log("检测到发布中状态卡住，执行失败重试", self.user)
            self.release_detail.set_status("发布失败")
        super().fail_retry()

    def _do_upgrade(self, modules):
        # 每次部署用独立的临时 hosts/host_vars 文件，避免并发部署互相覆盖
        self._temp_ansible_files: list = []
        try:
            # 1. 发布
            deploy_start = time.time()
            for module in modules:
                # 只有当is_release = true时，才被允许发布
                if MdlReleaseContent.objects.filter(release_plan=module.release_plan,
                                                    release_object=module.release_object,
                                                    is_release=True).exists():
                    self.release_detail.set_active(module.index)
                    self.deploy_config(module)
                    self.release_detail.set_log("{} {} 开始升级".format(module.release_object, module.release_version),
                                                self.user)
                    deploy_logger.info("[%s] plan=%s module=%s version=%s 开始升级",
                                       self.user, self.release_plan.name, module.release_object, module.release_version)
                    module.set_status("process")
                    module_start = time.time()
                    self._upgrade(module)
                    module_elapsed = time.time() - module_start
                    self.release_detail.set_log(
                        "{} {} 升级成功，耗时 {:.1f}s".format(module.release_object, module.release_version, module_elapsed),
                        self.user)
                    deploy_logger.info("[%s] plan=%s module=%s version=%s 升级成功 elapsed=%.1fs",
                                       self.user, self.release_plan.name, module.release_object, module.release_version, module_elapsed)
                    module.set_status("success")
            # 3 结束打日志
            total_elapsed = time.time() - deploy_start
            if not MdlReleaseContent.objects.filter(release_plan=self.release_plan, is_release=False).exists():
                self.release_detail.set_log("全部模块发布完成，总耗时 {:.1f}s".format(total_elapsed), self.user)
                deploy_logger.info("[%s] plan=%s 全部模块发布完成 total_elapsed=%.1fs",
                                   self.user, self.release_plan.name, total_elapsed)
                self.release_detail.set_status("发布成功")
            else:
                # 这一步是因为mysql 存储的特性决定的
                self.release_detail.set_status("暂停")

        except Exception as ex:
            # MySQL gone away 时连接已断，必须先强制关闭连接，否则后续 set_log/set_status 也会抛异常
            # 导致状态永远卡在"发布中"。close_old_connections() 对 errors_occurred=False 的死连接
            # 无效，必须用 db_connection.close() 强制关闭，保证下次查询重建。
            db_connection.close()
            deploy_logger.error("[%s] plan=%s module=%s version=%s 升级失败 error=%s",
                                self.user, self.release_plan.name, module.release_object, module.release_version, ex)
            try:
                self.release_detail.set_log(
                    "{} {} 升级失败，错误：{}".format(module.release_object, module.release_version, ex),
                    user=self.user, level="error")
            except Exception as _log_ex:
                deploy_logger.error("[%s] set_log failed in except block: %s", self.user, _log_ex)
            try:
                self.release_detail.set_status("发布失败")
            except Exception as _st_ex:
                deploy_logger.error("[%s] set_status(发布失败) failed: %s — status may be stuck", self.user, _st_ex)
            try:
                module.set_status("error")
            except Exception as _mod_ex:
                deploy_logger.error("[%s] module.set_status(error) failed: %s", self.user, _mod_ex)
            raise ex
        finally:
            # 清理本次部署产生的临时 hosts/host_vars 文件
            for _f in getattr(self, '_temp_ansible_files', []):
                try:
                    os.remove(_f)
                except Exception:
                    pass

    def _run_ansible(self, cmdline_args, env):
        """
        执行 ansible-playbook，带超时控制 + 实时日志输出。
        stdout/stderr 实时流式读取并写入发布日志，超时后强制 kill 进程。
        返回 (out, err, rc)，超时则抛异常（异常信息包含最后几行输出，方便排查卡在哪步）。

        注意：长时间部署（多台机器）会导致 MySQL 连接空闲超时（error 2006 gone away），
        在关键节点调用 close_old_connections() 让 Django 自动重建连接。
        """
        import threading as _threading

        try:
            timeout_per_machine = max(60, int(Constance.get_value("mdl_deploy_timeout_per_machine")))
        except Exception:
            timeout_per_machine = 300

        # 启动前先清理可能已失效的连接
        close_old_connections()

        proc = subprocess.Popen(
            ['ansible-playbook'] + cmdline_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        # 注册子进程，供 fail_retry / fail_skip 在超时前强制终止
        with _ansible_proc_lock:
            _ansible_proc_registry[self.release_detail.id] = proc

        stdout_lines = []
        stderr_lines = []

        def _read_stdout(pipe):
            _last_conn_reset = time.monotonic()
            for i, line in enumerate(pipe):
                line = line.rstrip('\n')
                stdout_lines.append(line)
                # 每 30 秒（基于时间而非行数）主动重置连接，防止 MySQL 空闲超时
                _now = time.monotonic()
                if _now - _last_conn_reset >= 30:
                    close_old_connections()
                    _last_conn_reset = _now
                # 实时写入发布日志，方便用户看到当前卡在哪个 task
                # 必须捕获异常：set_log 失败若不处理会导致线程崩溃，
                # stdout pipe 无人消费，ansible 写满缓冲区后卡死整个部署
                try:
                    self.release_detail.set_log(line, self.user, update_prompt=False)
                except Exception as _e:
                    deploy_logger.warning("set_log failed (stdout line %d): %s, reconnect and retry", i, _e)
                    try:
                        close_old_connections()
                        _last_conn_reset = time.monotonic()
                        self.release_detail.set_log(line, self.user, update_prompt=False)
                    except Exception as _e2:
                        deploy_logger.warning("set_log retry failed (stdout line %d): %s", i, _e2)

        def _read_stderr(pipe):
            for line in pipe:
                stderr_lines.append(line.rstrip('\n'))
            # stderr 不实时写日志，避免与 stdout 并发写 DB 冲突
            # 失败时统一在 _upgrade 里通过 err 输出

        t_out = _threading.Thread(target=_read_stdout, args=(proc.stdout,), daemon=True)
        t_err = _threading.Thread(target=_read_stderr, args=(proc.stderr,), daemon=True)
        t_out.start()
        t_err.start()

        try:
            proc.wait(timeout=timeout_per_machine)
            t_out.join(timeout=5)
            t_err.join(timeout=5)
            # ansible 执行期间主线程无 DB 操作，连接可能已被 MySQL 服务端关闭。
            # close_old_connections() 只关闭 Django 认为"已出错"的连接，无法覆盖
            # 服务端单方面断开的情况（errors_occurred=False）。
            # 用 db_connection.close() 强制关闭，保证后续 DB 操作使用新连接。
            db_connection.close()
            return '\n'.join(stdout_lines), '\n'.join(stderr_lines), proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            t_out.join(timeout=5)
            t_err.join(timeout=5)
            db_connection.close()
            last_lines = stdout_lines[-10:] or stderr_lines[-10:]
            raise Exception(
                "ansible-playbook 执行超时（超过 {}s），进程已终止。最后输出：\n{}".format(
                    timeout_per_machine, '\n'.join(last_lines)
                )
            )
        finally:
            with _ansible_proc_lock:
                # 仅当注册的还是本次进程时才移除（避免 fail_retry 已 pop 后再次删除）
                if _ansible_proc_registry.get(self.release_detail.id) is proc:
                    _ansible_proc_registry.pop(self.release_detail.id, None)

    def _upgrade(self, module, is_rollback=False):
        """
        1. 获取当前版本信息
        2. 升级
        3. 校验
        发布对象 test1_10.42.16.157_mdl-test  fqdn_ip_serviceName
        """
        # 1. 生成对应hosts和host_vars文件
        obj_list = module.release_object.split("__")
        if len(obj_list) != 3:
            raise Exception("发布对象的格式异常")
        server_fqdn = obj_list[0]
        service_name = obj_list[2]
        executable = getattr(module, "executable", None) or "feeder_handler"
        self._create_ansible_host(server_fqdn, service_name)
        self._create_ansible_host_vars(server_fqdn, service_name, executable=executable)
        # 2. 如果是回滚操作则回退配置
        if is_rollback:
            self.rollback_config(module)
        # 3.第一次升级时 获取升级前的版本 用于回滚操作
        if not module.current_version and not is_rollback and module.type == 'version':
            module.current_version = self._get_current_version(server_fqdn, service_name)
            module.save()
        # 4. 升级
        _env = os.environ.copy()
        _env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'
        if module.type == 'version':
            release_version = module.release_version.split(":")[1].strip()
            srv = MdlServer.objects.select_related('host').get(host__fqdn=server_fqdn, service_name=service_name)
            self.release_detail.set_log("{} 部署目录：{}，将从 consul 拉取配置文件：{}".format(
                module.release_object, srv.install_dir, srv.consul_files or 'feeder_handler.cfg'), self.user)
            self.release_detail.set_log(
                "{} [ansible] 开始执行 deploy_feeder.yml，version={}，executable={}".format(
                    module.release_object, release_version, executable),
                self.user, update_prompt=False)
            deploy_logger.info("[%s] plan=%s module=%s ansible=deploy_feeder.yml version=%s executable=%s START",
                               self.user, self.release_plan.name, module.release_object, release_version, executable)
            ansible_start = time.time()
            out, err, rc = self._run_ansible(
                ['ansi/mdl/deploy_feeder.yml', '-i', getattr(self, '_ansible_inventory_path', 'ansi/mdl/hosts'),
                 '--extra-vars', 'version={} executable={}'.format(release_version, executable)],
                env=_env,
            )
            ansible_elapsed = time.time() - ansible_start
            self.release_detail.set_log(
                "{} [ansible] deploy_feeder.yml 执行完毕，耗时 {:.1f}s，returncode={}".format(
                    module.release_object, ansible_elapsed, rc),
                self.user, update_prompt=False)
            deploy_logger.info("[%s] plan=%s module=%s ansible=deploy_feeder.yml DONE elapsed=%.1fs rc=%s",
                               self.user, self.release_plan.name, module.release_object, ansible_elapsed, rc)
        elif module.type == 'config':
            srv = MdlServer.objects.select_related('host').get(host__fqdn=server_fqdn, service_name=service_name)
            self.release_detail.set_log("{} 开始从 consul 拉取配置到 {}".format(module.release_object, srv.install_dir), self.user)
            self.release_detail.set_log(
                "{} [ansible] 开始执行 deploy_config.yml".format(module.release_object),
                self.user, update_prompt=False)
            deploy_logger.info("[%s] plan=%s module=%s ansible=deploy_config.yml START",
                               self.user, self.release_plan.name, module.release_object)
            ansible_start = time.time()
            out, err, rc = self._run_ansible(
                ['ansi/mdl/deploy_config.yml', '-i', getattr(self, '_ansible_inventory_path', 'ansi/mdl/hosts')],
                env=_env,
            )
            ansible_elapsed = time.time() - ansible_start
            self.release_detail.set_log(
                "{} [ansible] deploy_config.yml 执行完毕，耗时 {:.1f}s，returncode={}".format(
                    module.release_object, ansible_elapsed, rc),
                self.user, update_prompt=False)
            deploy_logger.info("[%s] plan=%s module=%s ansible=deploy_config.yml DONE elapsed=%.1fs rc=%s",
                               self.user, self.release_plan.name, module.release_object, ansible_elapsed, rc)
        if rc != 0:
            self.release_detail.set_log(
                "{} [ansible] stderr: {}".format(module.release_object, err),
                self.user, level="error", update_prompt=False)
            deploy_logger.error("[%s] plan=%s module=%s ansible FAILED rc=%s\nstdout=%s\nstderr=%s",
                                self.user, self.release_plan.name, module.release_object, rc, out, err)
            raise Exception(out)
        if module.type == 'config':
            self.release_detail.set_log("{} consul 配置已拉取到目标机器 {}".format(module.release_object, srv.install_dir), self.user)
        # 日志抓取异步执行，不阻塞主发布流程，失败只记录警告
        import threading as _threading
        _threading.Thread(
            target=self._get_upgrade_log_safe,
            args=(server_fqdn, service_name),
            daemon=True,
        ).start()

    def _rollback(self, modules):
        try:
            self.release_detail.set_status("回滚中")
            for module in modules:
                if module.current_version:
                    self.release_detail.set_active(module.index)
                    self.release_detail.set_log("{} 开始回滚到 {}".format(module.release_object, module.current_version),
                                                self.user)
                    module.set_status("process")
                    self._upgrade(module, is_rollback=True)
                    self.release_detail.set_log("{} 回滚成功".format(module.release_object), self.user)
                    module.set_status("wait")
            self.release_detail.set_status("回滚成功")
        except Exception as ex:
            self.release_detail.set_log("{} 回滚失败，错误：{}".format(module.release_object, ex), user=self.user,
                                        level="error")
            module.set_status("error")
            self.release_detail.set_status("回滚失败")
            raise ex

    def _create_ansible_host(self, server, service_name):
        """
        创建ansible 主机文件
        1. 生成获取主机信息
        2. 生成对应的文件（路径含 release_detail.id，避免并发部署互相覆盖）
        3. 验证文件
        """
        # 1. 生成获取主机信息
        base_hosts_path = Constance.get_value("ansible_hosts_path")
        # 唯一化文件路径，防止多个并发部署共用同一文件
        ansible_hosts_path = "{}_{}".format(base_hosts_path, self.release_detail.id)
        self._ansible_inventory_path = ansible_hosts_path
        if not hasattr(self, '_temp_ansible_files'):
            self._temp_ansible_files = []
        if ansible_hosts_path not in self._temp_ansible_files:
            self._temp_ansible_files.append(ansible_hosts_path)

        ip = MdlServer.objects.select_related('host').get(host__fqdn=server, service_name=service_name).host.ip
        ansible_ssh_user = Constance.get_value("ansible_ssh_user")
        ansible_ssh_pass = Constance.get_value("ansible_ssh_pass")
        # host 别名也含 id，确保 ansible 读取匹配的 host_vars 文件
        self._ansible_host_alias = "release_{}".format(self.release_detail.id)
        host_info = (
            "{} ansible_ssh_host={} ansible_ssh_user={} ansible_ssh_pass={}"
            " ansible_ssh_common_args='-o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=3'"
        ).format(self._ansible_host_alias, ip, ansible_ssh_user, ansible_ssh_pass)
        # 2. 生成对应的文件
        with open(ansible_hosts_path, "w") as f:
            f.write(host_info)
        # 3. 验证是否正确
        with open(ansible_hosts_path) as f:
            line = f.read().strip()
            if line == host_info:
                return
            raise Exception("ansible hosts文件生成异常")

    def _create_ansible_host_vars(self, server, service_name, executable=None):
        """
        创建ansible 主机文件
        1. 生成获取主机信息
        2. 生成对应的文件（文件名与 host 别名匹配，含 release_detail.id）
        3. 验证文件
        """
        # 1. 生成主机部署信息
        base_host_vars_path = Constance.get_value("ansible_host_vars_path")
        # host_vars 文件名必须与 inventory 中的 host 别名一致
        # base 形如 /path/to/host_vars/release.yml → /path/to/host_vars/release_<id>.yml
        import os as _os
        vars_dir = _os.path.dirname(base_host_vars_path)
        ansible_host_vars_path = _os.path.join(vars_dir, "{}.yml".format(
            getattr(self, '_ansible_host_alias', 'release_{}'.format(self.release_detail.id))
        ))
        if not hasattr(self, '_temp_ansible_files'):
            self._temp_ansible_files = []
        if ansible_host_vars_path not in self._temp_ansible_files:
            self._temp_ansible_files.append(ansible_host_vars_path)

        srv = MdlServer.objects.select_related('host').get(host__fqdn=server, service_name=service_name)
        #  2. 生成对应的文件
        _os.makedirs(vars_dir, exist_ok=True)
        host_vars = {
            'user': srv.host.user,
            'remote_python': srv.host.remote_python,
            'consul_space': srv.consul_space,
            'consul_token': srv.consul_token,
            'install_dir': srv.install_dir,
            'backups_dir': srv.backups_dir,
            'service_name': srv.service_name,
            'consul_files': srv.consul_files,
        }
        if executable:
            host_vars["executable"] = executable
        with open(ansible_host_vars_path, "w") as f:
            yaml.dump(host_vars, f)
        # 3. 验证是否正确
        with open(ansible_host_vars_path) as f:
            file_data = yaml.load(f, Loader=yaml.FullLoader)
            if file_data == host_vars:
                return
            raise Exception("ansible host_vars文件生成异常")

    def _get_current_version(self, server, service_name):
        import concurrent.futures
        srv = MdlServer.objects.select_related('host').get(host__fqdn=server, service_name=service_name)
        ip = srv.host.ip
        username = Constance.get_value("ansible_ssh_user")
        password = Constance.get_value("ansible_ssh_pass")
        install_dir = srv.install_dir
        cmd = 'cat {}/version'.format(install_dir)

        deploy_logger.debug(
            "[%s] _get_current_version: start  server=%s service=%s ip=%s cmd=%s release_detail=%s",
            self.user, server, service_name, ip, cmd, self.release_detail.id,
        )

        def _ssh_get():
            t0 = time.time()
            deploy_logger.debug(
                "[%s] _get_current_version: connecting  ip=%s release_detail=%s",
                self.user, ip, self.release_detail.id,
            )
            client = SshClient(ip=ip, username=username, password=password)
            deploy_logger.debug(
                "[%s] _get_current_version: connected (%.1fs)  ip=%s release_detail=%s — executing cmd",
                self.user, time.time() - t0, ip, self.release_detail.id,
            )
            result = client.send_cmd(cmd)
            deploy_logger.debug(
                "[%s] _get_current_version: done (%.1fs)  ip=%s result=%r release_detail=%s",
                self.user, time.time() - t0, ip, result, self.release_detail.id,
            )
            return result

        # SshClient.connect(timeout=5) 只覆盖 TCP 握手，SSH 认证阶段可能无限挂住。
        # 用线程池套硬超时，超时后返回空串（等同于首次部署，不影响主流程）。
        #
        # 不能用 `with ThreadPoolExecutor(...) as ex:` —— with 块退出时会调
        # executor.shutdown(wait=True)，即使 future.result() 已经超时，它仍会
        # 等待 SSH 线程真正结束。若 paramiko 卡在 TCP 层，OS 超时需 10~30 分钟，
        # 导致整个部署主线程沉默 15 分钟，并顺带让 MySQL 连接空闲超时断掉。
        # 改用 finally 里 shutdown(wait=False)，超时后立即放弃线程，主流程继续。
        t_start = time.time()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(_ssh_get)
            try:
                res = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                deploy_logger.warning(
                    "[%s] _get_current_version: SSH timeout after %.1fs  server=%s service=%s ip=%s cmd=%s "
                    "release_detail=%s — treating as first deploy",
                    self.user, time.time() - t_start, server, service_name, ip, cmd, self.release_detail.id,
                )
                return ''
            except Exception as e:
                deploy_logger.warning(
                    "[%s] _get_current_version: SSH error after %.1fs  server=%s service=%s ip=%s "
                    "error=%s(%s) release_detail=%s — treating as first deploy",
                    self.user, time.time() - t_start, server, service_name, ip,
                    type(e).__name__, e, self.release_detail.id,
                )
                return ''
        finally:
            executor.shutdown(wait=False)
        return res[0].strip() if res else ''

    def _resolve_log_file(self, install_dir, consul_files, ssh_client):
        """
        从目标机器上的配置文件中解析实际日志文件路径。
        配置文件是 JSON，找 feeder_handler_log.LogFiles[].FileName 中不含 .trace. 的 .log 文件。
        找不到则回退到 install_dir/../logs/feeder_handler.log。
        """
        import json
        cfg_file = consul_files.split(",")[0].strip() if consul_files else None
        if cfg_file:
            cfg_path = "{}/{}".format(install_dir, cfg_file)
            try:
                res = ssh_client.send_cmd("cat {}".format(cfg_path))
                content = "\n".join(res).strip()
                cfg = json.loads(content)
                # 找所有 LogFiles 里的 FileName
                for key, val in cfg.items():
                    if isinstance(val, dict) and "LogFiles" in val:
                        for lf in val["LogFiles"]:
                            fname = lf.get("FileName", "")
                            if fname.endswith(".log") and ".trace." not in fname:
                                # FileName 通常是相对路径如 ../logs/feeder_handlerTEST.log
                                # 基于 install_dir 解析绝对路径
                                import posixpath
                                abs_path = posixpath.normpath(posixpath.join(install_dir, fname))
                                return abs_path
            except Exception as e:
                self.release_detail.set_log("解析配置文件日志路径失败：{}，使用默认路径".format(e), self.user)
        # 回退：install_dir/../logs/feeder_handler.log
        base = "/".join(install_dir.rstrip("/").split("/")[:-1])
        return "{}/logs/feeder_handler.log".format(base)

    def _get_upgrade_log_safe(self, server, service_name):
        """异步日志抓取，失败只打警告，不影响发布结果"""
        try:
            self._get_upgrade_log(server, service_name)
        except Exception as e:
            try:
                self.release_detail.set_log(
                    "日志抓取失败（不影响发布结果）：{}".format(e), self.user, level="error"
                )
            except Exception:
                pass

    def _get_upgrade_log(self, server, service_name):
        """
        获取最近1分钟内的日志
        """
        import concurrent.futures as _cf
        mdl_server = MdlServer.objects.select_related('host').get(host__fqdn=server, service_name=service_name)
        ip = mdl_server.host.ip
        self.release_detail.set_log("开始抓取{}_{}_{}日志信息....".format(server, ip, service_name), self.user, update_prompt=False)
        time.sleep(15)
        username = Constance.get_value("ansible_ssh_user")
        password = Constance.get_value("ansible_ssh_pass")
        install_dir = mdl_server.install_dir

        def _do_ssh():
            _ssh = SshClient(ip=ip, username=username, password=password)
            _log_file = self._resolve_log_file(install_dir, mdl_server.consul_files, _ssh)
            _cmd = """grep -a $(date '+%Y-%m-%d') {} | awk -v dt="$(date '+%Y-%m-%d %T' -d '-1 minutes')" -F, '$1 > dt'""".format(
                _log_file)
            _res = _ssh.send_cmd(_cmd)
            _ssh.close()
            return _log_file, _res

        # 同 _get_current_version：不用 with，避免 shutdown(wait=True) 在 SSH 卡住时阻塞
        _ex = _cf.ThreadPoolExecutor(max_workers=1)
        try:
            _future = _ex.submit(_do_ssh)
            log_file, res = _future.result(timeout=60)
        finally:
            _ex.shutdown(wait=False)

        log_name = log_file.split("/")[-1]
        self.release_detail.set_log("读取日志文件：{}".format(log_file), self.user, update_prompt=False)
        # 用 set_log 追加，避免直接赋值与 _read_stdout 并发写产生竞态覆盖 ansible 输出
        self.release_detail.set_log(
            "{}信息如下：\n".format(log_name) + "\n".join(res),
            self.user,
            update_prompt=False,
        )

    def deploy_config(self, module):
        """
        发布配置：列出 GitLab 目录下所有配置文件，全部推送到 Consul
        """
        obj_list = module.release_object.split("__")
        if len(obj_list) != 3:
            raise Exception("发布对象的格式异常")
        server_fqdn = obj_list[0]
        service_name = obj_list[2]
        mdl_server_obj = MdlServer.objects.select_related('host').get(host__fqdn=server_fqdn, service_name=service_name)

        # consul_space: http://consul.wmcloud.com/v1/kv/configs/mdl/forward/forward_xxx/
        # consul_kv_prefix: configs/mdl/forward/forward_xxx/
        consul_kv_prefix = mdl_server_obj.consul_space.split("/v1/kv/")[-1]
        # git_dir: forward/forward_xxx  (去掉顶层 configs/mdl/ 前缀，去掉末尾斜杠)
        git_dir = "/".join(consul_kv_prefix.rstrip("/").split("/")[2:])

        gitlab_client = GitlabClient()
        filenames = gitlab_client.list_directory_files(git_dir)
        if not filenames:
            # Git 目录为空：STG 等环境配置直接维护在 Consul，无需 Git→Consul 同步。
            # 跳过本步骤，后续 ansible 会直接从 Consul 拉取配置到目标机器。
            self.release_detail.set_log(
                "{} Git目录 '{}' 无文件，跳过 Git→Consul 同步，将直接从 Consul 拉取配置".format(
                    module.release_object, git_dir),
                self.user)
            return

        self.release_detail.set_log("{} 开始配置发布，目录：{}，文件：{}".format(
            module.release_object, git_dir, ", ".join(filenames)), self.user)
        consul_client = ConsulClient()
        for filename in filenames:
            file_content = gitlab_client.get_project_file(file_path="{}/{}".format(git_dir, filename))
            consul_key = consul_kv_prefix + filename
            consul_client.put(key=consul_key, value=file_content.encode("utf-8"))
            self.release_detail.set_log("{} {} 推送成功 → consul: {}".format(module.release_object, filename, consul_key), self.user)
        self.release_detail.set_log("{} 配置发布完成，共推送 {} 个文件到 consul: {}".format(module.release_object, len(filenames), consul_kv_prefix), self.user)

    def rollback_config(self, module):
        """
        回滚配置
        """
        raise Exception("暂时不支持回滚配置")
        # if module.config_file:
        #     self.release_detail.set_log("{} 开始配置回滚".format(module.release_version), self.user)
        #     if module.release_plan.project == 'MDL':
        #         name = module.release_plan.name + "_" + module.server
        #     else:
        #         name = module.release_plan.name + "_" + module.issue_key
        #     # ConfClient().rollback(name=name)
        #     self.release_detail.set_log("{} 配置回滚成功".format(module.release_version), self.user)
        # else:
        #     self.release_detail.set_log("{} 无配置回滚".format(module.release_version), self.user)


if __name__ == '__main__':
    pass
