# MDL 发布系统

企业级软件发布管理平台，支持 **Rancher**（容器化）和 **MDL**（自研服务）两种发布类型，并内置 MDL **配置管理**功能。

---

## 目录

- [功能概述](#功能概述)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速启动](#快速启动)
- [MDL 配置管理](#mdl-配置管理)
- [API 文档](#api-文档)
- [配置说明](#配置说明)

---

## 功能概述

| 模块 | 功能 |
|------|------|
| **Rancher 发布** | 创建/编辑发布计划，关联 Jira 工单，执行 Rancher 工作负载升级，支持回滚 |
| **MDL 发布** | MDL 服务版本发布或纯配置变更，通过 Ansible 部署，支持暂停/重试/回滚 |
| **MDL 配置管理** | 浏览/编辑三级配置树（服务类型→实例→配置文件），批量修改，Git 提交，Consul 推送，Ansible 部署 |
| **权限控制** | LDAP/CAS 认证，区分 Admin / Deployer / 普通用户角色 |
| **审计日志** | 全操作记录，邮件/企业微信通知 |

---

## 技术栈

### 后端
| 组件 | 版本 |
|------|------|
| Python | 3.9.5 |
| Django | 3.2 |
| Django REST Framework | 3.12.4 |
| 数据库 | MySQL |
| 认证 | django-auth-ldap + django-cas-ng |
| 自动化 | Ansible 5.1.0 + ansible-runner 2.1.1 |
| 外部集成 | GitLab、Consul、Rancher、Jira |

### 前端
| 组件 | 版本 |
|------|------|
| Vue | 2.6.10 |
| Element UI | 2.15.6 |
| Vue Router | 3.0.6 |
| Vuex | 3.1.0 |
| Monaco Editor | 0.36.x |
| Axios | 0.18.1 |

---

## 项目结构

```
release-src/
├── release/                        # Django 后端
│   ├── api/                        # 核心 API 应用
│   │   ├── models.py               # ReleasePlan, ReleaseContent, ReleaseDetail
│   │   ├── viewsets/               # REST API ViewSets
│   │   │   ├── release_plan_viewset.py
│   │   │   ├── release_detail_viewset.py
│   │   │   ├── config_mgmt_viewset.py   # ← MDL 配置管理
│   │   │   ├── jira_viewset.py
│   │   │   └── cmdb_viewset.py
│   │   ├── services/               # 发布业务逻辑
│   │   │   ├── rancher_release_detail_service.py
│   │   │   └── mdl_release_detail_service.py
│   │   └── urls.py
│   ├── mdl/                        # MDL 相关模型
│   │   └── models.py               # MdlServer, Label, ServiceType, ConfigInstance, ConfigFile, ConfigDeployTask
│   ├── app/                        # Rancher 相关模型
│   ├── external/                   # 外部服务客户端
│   │   ├── gitlab_client.py
│   │   ├── consul_client.py
│   │   ├── rancher_client.py
│   │   ├── jira_client.py
│   │   └── ssh_client.py
│   ├── ansi/mdl/                   # Ansible Playbooks
│   │   ├── deploy_config.yml       # 配置部署
│   │   └── deploy_feeder.yml       # 版本部署
│   ├── common/                     # 公共工具
│   ├── const/                      # 系统配置常量
│   └── release/
│       └── settings.py             # Django 配置
│
└── vue-release-web/                # Vue2 前端
    └── src/
        ├── router/index.js         # 路由配置
        ├── api/
        │   ├── releasePlan.js
        │   ├── releaseDetail.js
        │   └── configMgmt.js       # ← MDL 配置管理 API
        └── views/
            ├── release/            # Rancher 发布计划
            ├── mdl/
            │   ├── index.vue               # MDL 发布计划列表
            │   ├── configManagement.vue    # ← MDL 配置管理主页面
            │   └── components/
            │       ├── ConfigEditor.vue    # Monaco JSON 编辑器
            │       ├── BatchEditModal.vue  # 批量修改弹窗
            │       └── DeployModal.vue     # 部署弹窗
            └── dashboard/
```

---

## 快速启动

### 前置条件

- Python 3.9.5
- Node.js 14+
- MySQL（已创建 `release_qa` 数据库）
- 可访问 GitLab、Consul、Rancher（可选）

### 后端

```bash
cd release-src/release

# 安装依赖
pip install -r docker/requirements.txt

# 数据库迁移
python manage.py migrate

# 启动开发服务器
python manage.py runserver 0.0.0.0:8000
```

### 前端

```bash
cd release-src/vue-release-web

# 安装依赖（首次或新增包后执行）
npm install

# 启动开发服务器（默认端口 9528）
npm run dev

# 生产构建
npm run build
```

### Docker 部署

```bash
cd release-src/release
bash docker_build.sh
```

---

## MDL 配置管理

> 对应截图：`demo/pictures/release.png`
> 集成自 `demo` 工程，入口：侧边栏 **MDL管理 → 配置管理**，路由 `/#/mdl/config_management`

### 数据层次结构

```
GitLab 仓库 (consul/mdl/)
└── 服务类型/          ← ServiceType（如 aliforward）
    └── 实例名/        ← ConfigInstance（如 10.121.21.219_19013）
        └── xxx.cfg   ← ConfigFile（JSON 格式）
```

### 主要功能

| 功能 | 入口 | 说明 |
|------|------|------|
| **同步** | 顶部「同步」按钮 | 从 GitLab 下载 archive 并同步到数据库 |
| **浏览** | 左侧配置树 | 服务类型 → 实例 → 配置文件 三级树，支持搜索 |
| **编辑** | 右侧 Monaco 编辑器 | 点击配置文件节点加载，修改后点「保存」 |
| **批量修改** | 勾选实例后点「批量修改」 | 跨实例修改同一 key，支持结构化 Schema 对比 |
| **提交 Git** | 勾选配置后点「提交 Git」 | 将修改提交到 GitLab 仓库 |
| **推送 Consul** | 勾选配置后点「推送 Consul」 | 推送到 Consul KV Store |
| **部署** | 勾选实例后点「部署」 | 推送 Consul + Ansible 部署到远端服务器 |

### 首次使用

1. 在 `release/release/settings.py` 中配置 GitLab、Consul 信息（`CONFIG_GITLAB_*`、`CONFIG_CONSUL_*`）
2. 运行数据库迁移：`python manage.py makemigrations mdl && python manage.py migrate`
3. 打开「配置管理」页面，点击「同步」从 GitLab 导入配置数据

---

## API 文档

后端启动后访问 DRF Browsable API：`http://localhost:8000/api/`

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/releasePlan/` | GET/POST | 发布计划列表/创建 |
| `/api/releaseDetail/deploy/` | POST | 执行发布 |
| `/api/releaseDetail/rollback/` | POST | 回滚 |
| `/api/config-mgmt/tree/` | GET | 配置树 |
| `/api/config-mgmt/configs/` | GET/PUT | 配置文件 CRUD |
| `/api/config-mgmt/configs/batch_update/` | POST | 批量修改 |
| `/api/config-mgmt/configs/git_commit/` | POST | 提交 GitLab |
| `/api/config-mgmt/configs/push_consul/` | POST | 推送 Consul |
| `/api/config-mgmt/sync/` | POST | 从 GitLab 同步 |
| `/api/config-mgmt/deploy/` | POST | 触发 Ansible 部署 |

---

## 配置说明

关键配置均在 `release/release/settings.py`：

```python
# MySQL 数据库
DATABASES = { 'default': { 'NAME': 'release_qa', ... } }

# MDL 配置管理 - GitLab
CONFIG_GITLAB_URL = 'http://git.datayes.com'
CONFIG_GITLAB_TOKEN = '...'
CONFIG_GITLAB_PROJECT_ID = '6481'
CONFIG_GITLAB_BRANCH = 'master'

# MDL 配置管理 - Consul
CONFIG_CONSUL_URL = 'http://consul.wmcloud.com'
CONFIG_CONSUL_TOKEN = '...'
CONFIG_CONSUL_KV_PREFIX = 'configs/mdl'

# MDL 配置管理 - Ansible 部署目录
CONFIG_ANSIBLE_DIR = os.path.join(BASE_DIR, 'ansi', 'mdl')
```

前端接口代理配置在 `vue-release-web/src/utils/request.js`，开发时 API 请求默认代理到 `http://localhost:8000`。
