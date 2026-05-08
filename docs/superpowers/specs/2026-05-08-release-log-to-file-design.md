# 发布日志写文件改造设计

- 日期：2026-05-08
- 范围：仅 `ReleaseDetail.log`（不含 DeployTask 的 `task.log`）

## 背景与动机

发布过程中 `_read_stdout` 线程逐行读取 ansible 输出，每行调用一次
`ReleaseDetail.set_log`，该方法把整段日志拼回 `log` TextField 后 `self.save()`
整对象写库。结果：

- DB 写压力随日志行数线性增长，单条记录的 `UPDATE` payload 越来越大；
- ansible 长时间运行期间主线程无 DB 操作，MySQL 服务端可能单方面断开连接，
  下一次 `set_log` 抛 `MySQL server has gone away`；
- 已有重试 / `close_old_connections()` / `db_connection.close()` 等多处补丁
  围绕这一点打补丁，根因没消除。

## 目标

把 ansible 实时输出从 DB 切换为本地文件，彻底消除该写路径上的 DB 压力与
gone-away 问题；前端零改动；旧记录可继续展示。

## 非目标（YAGNI）

- DeployTask（`mdl_server_viewset` / `config_mgmt_viewset`）里的 `task.log`
  暂不动。后续可按相同套路再做一遍。
- 不实现日志清理 / 轮转 / 压缩。文件按 `release_detail_{id}.log` 命名集中
  在一个目录，未来需要清理时一行 `find -mtime +N -delete` 即可。
- 不实现 SSE 流式推送 / 增量 offset 读取。前端继续轮询，整段返回。
- 路径不做配置化（项目部署一律 Linux）。

## 设计

### 文件路径与格式

- 路径：`/datayes/release/logs/release_detail_{id}.log`
- 目录不存在时，首次写入由 `os.makedirs(path, exist_ok=True)` 创建。
- 写入模式：`open(path, 'a', encoding='utf-8')`。
- 行格式与现状保持一致：

  ```
  {timestamp} {level} {user} {log_message}\n
  ```

  例：`2026-05-08 11:23:45.678 info zhangsan TASK [feeder : restart] ...`

### `ReleaseDetail.set_log` 行为

- DB 上 `log` 字段保留不删（保留向后回溯的可能），但 `set_log` **不再写
  `log` 列**。
- `prompt` 字段（"当前步骤"提示）仍写库，但仅在 `update_prompt=True` 时写：
  - 调用 `self.save(update_fields=['prompt'])`，避免整对象 UPDATE 覆盖其他
    字段，也减小写入体积。
- 写文件失败时：捕获异常，`deploy_logger.warning(...)` 降级，**不抛**。
  这是关键约束——`_read_stdout` 抛异常会让 stdout pipe 无人消费，ansible
  写满 pipe 缓冲区后整个部署卡死。当前代码已经按这条规则在做，必须保持。

### 读取（`get_release_detail_info`）

- 响应 JSON 仍含 `log` 键，前端无感。
- 读取顺序：
  1. 尝试 `open('/datayes/release/logs/release_detail_{id}.log').read()`；
  2. 文件不存在 → 回退到 DB `log` 列（兼容旧记录）。
- `model_to_dict` 后用读到的内容覆盖 `data['log']`。

### `_read_stderr` 改进（可选）

当前 `_read_stderr` 注释明确说"不实时写日志，避免与 stdout 并发写 DB
冲突"。改文件后，Linux append 写在 PIPE_BUF=4KB 内是原子的（ansible 单行
通常远小于此），所以 stdout / stderr 并发 append 同一文件是安全的。

不过这是改进项，不是本次必做。本次保持 stderr 现状即可，后续可单独提交一
个小改动放开 stderr 实时写入。

## 数据流

```
[主线程 set_log("开始升级", update_prompt=True)]  ─┐
[_read_stdout 线程 set_log(line, update_prompt=False)]  ─┤
                                                         ├─→ open(file, 'a').write(line)
                                                         │
                                                         └─→ 仅当 update_prompt=True：
                                                             self.save(update_fields=['prompt'])

[前端轮询 get_release_detail_info]
   └─→ model_to_dict + open(file).read()  → data['log'] → 返回
```

## 兼容性

- DB schema 不变，`log` 字段保留，无需 migration。
- 旧 ReleaseDetail（文件不存在）：读取走 DB 列回退路径，原样显示。
- 新 ReleaseDetail：写文件，DB `log` 列恒为空或保留默认值。
- 前端 (`vue-release-web`) 零改动。

## 边界 / 错误处理

| 场景 | 行为 |
|------|------|
| 写文件抛异常（磁盘满 / 权限） | `deploy_logger.warning`，丢弃该行，**不向 `_read_stdout` 抛** |
| 读文件抛异常（除文件不存在） | `deploy_logger.warning`，回退 DB 列 |
| 文件不存在 | 回退 DB 列（兼容旧数据） |
| `update_prompt=True` save 失败 | 沿用现有 `set_log` 的异常传播策略，不在本次改动范围内调整 |
| 目录不存在 | `os.makedirs(..., exist_ok=True)` 首次写入时创建 |

## 测试

新增 / 调整：

- `set_log` 单元测试：
  - 文件不存在时首次调用会创建文件并写一行；
  - 多次调用追加而非覆盖；
  - `update_prompt=True` 时 `prompt` 字段更新且仅 `prompt` 入库；
  - `update_prompt=False` 时 DB 完全不被写；
  - 写文件抛异常时函数返回正常（被捕获）。
- `get_release_detail_info` 集成测试：
  - 文件存在 → 返回文件内容；
  - 文件不存在 → 返回 DB `log` 列内容（兼容旧数据）。
- 现有 `release/tests/test_mdl_release_detail_service.py` 中对
  `release_detail.log` 的断言需调整为读文件断言（或通过测试夹具临时
  redirect 到 tmp 目录）。

## 实施步骤概要（细节交给后续 plan）

1. 在 `ReleaseDetail` 上引入文件写入逻辑（修改 `set_log`）。
2. 修改 `get_release_detail_info` 读文件并填回 `log` 字段。
3. 调整现有测试，新增前述用例。
4. 验证：本地 Linux 环境跑一次完整发布流程，确认日志在文件里、前端能看到、
   DB 上 `log` 列保持空。
