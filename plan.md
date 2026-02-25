Claude’s Plan
集成计划：将 demo 配置管理功能集成到 release-src 发布系统
Context
参考 demo/pictures/release.png，目标是在现有 release-src 发布系统的 "MDL管理" 侧边栏下新增一个 "配置管理" 子页面（路由 /mdl/config_management），功能来自 demo 工程。

该页面是一个 Consul KV 风格的配置浏览/编辑器，支持：

层次结构浏览：服务类型 → 实例 → 配置文件
JSON 配置在线编辑（Monaco Editor）
批量修改、结构化批量修改
Git 同步/提交
Consul KV 推送
Ansible 部署
导入/导出
关键约束
维度	demo 工程	release-src 工程
后端框架	Django 4.2 + Python 3.12	Django 3.2 + Python 3.9.5
前端框架	Vue 3 + Vite + Element Plus	Vue 2 + Vue CLI + Element UI
状态管理	Pinia	Vuex 3
已有 Consul 客户端	demo 内置	release/external/consul_client.py
已有 GitLab 客户端	demo 内置	release/external/gitlab_client.py
已有 Ansible	demo 内置	release/ansi/mdl/
数据库	SQLite	MySQL
一、后端改动
1.1 在 mdl app 中新增模型
文件: release/mdl/models.py（追加，不修改已有 MdlServer、Label）

新增 4 个模型：


class ServiceType(TimestampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    # e.g. aliforward, forward, barcal

class ConfigInstance(TimestampedModel):
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)  # e.g. 10.121.21.219_19013
    host_ip = models.CharField(max_length=50, null=True, blank=True)
    port = models.IntegerField(null=True, blank=True)
    config_path = models.CharField(max_length=300, null=True, blank=True)
    service_name = models.CharField(max_length=100, null=True, blank=True)
    install_dir = models.CharField(max_length=200, null=True, blank=True)
    backups_dir = models.CharField(max_length=200, null=True, blank=True)
    consul_space = models.CharField(max_length=300, null=True, blank=True)
    consul_files = models.CharField(max_length=100, default="feeder_handler.cfg")
    remote_python = models.CharField(max_length=100, default="/usr/bin/python3")
    class Meta:
        unique_together = ('service_type', 'name')

class ConfigFile(TimestampedModel):
    instance = models.ForeignKey(ConfigInstance, on_delete=models.CASCADE)
    filename = models.CharField(max_length=200)
    content = models.JSONField(null=True)
    raw_content = models.TextField(null=True, blank=True)
    git_path = models.CharField(max_length=500, null=True, blank=True)
    class Meta:
        unique_together = ('instance', 'filename')

class ConfigDeployTask(TimestampedModel):
    STATUS_CHOICES = [('pending','pending'),('running','running'),('success','success'),('failed','failed')]
    instances = models.ManyToManyField(ConfigInstance, blank=True)
    operator = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    log = models.TextField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
1.2 生成并运行迁移

python manage.py makemigrations mdl
python manage.py migrate
1.3 新建 viewset 文件
新文件: release/api/viewsets/config_mgmt_viewset.py

实现以下 ViewSets（参考 demo 的 apps/configs/views.py 和 apps/instances/views.py，适配 Django 3.2 语法）：

ConfigTreeViewSet — GET /api/config-mgmt/tree/：返回 ServiceType→Instance→ConfigFile 树
ConfigFileViewSet — CRUD /api/config-mgmt/configs/：
list / retrieve / update
batch_update action — POST 批量修改同一 key
schema action — POST 获取多实例合并 schema
git_commit action — POST 提交到 GitLab（复用 release/external/gitlab_client.py）
push_consul action — POST 推送 Consul（复用 release/external/consul_client.py）
ConfigSyncViewSet — POST /api/config-mgmt/sync/：从 GitLab 同步（复用 external/gitlab_client.py）
ConfigDeployViewSet — POST/GET /api/config-mgmt/deploy/：触发 Ansible 部署（复用 release/ansi/mdl/ 中的 playbooks）
复用已有客户端：

Consul: release/external/consul_client.py → ConsulClient
GitLab: release/external/gitlab_client.py → GitLabClient
Ansible: release/ansi/mdl/deploy_config.yml（与 demo 的 backend/ansible/deploy_config.yml 功能相同）
1.4 注册路由
文件: release/api/urls.py


from api.viewsets.config_mgmt_viewset import (
    ConfigTreeViewSet, ConfigFileViewSet, ConfigSyncViewSet, ConfigDeployViewSet
)

router.register(r'config-mgmt/tree', ConfigTreeViewSet, basename="config-tree")
router.register(r'config-mgmt/configs', ConfigFileViewSet, basename="config-file")
router.register(r'config-mgmt/sync', ConfigSyncViewSet, basename="config-sync")
router.register(r'config-mgmt/deploy', ConfigDeployViewSet, basename="config-deploy")
1.5 依赖检查
release/docker/requirements.txt 已有：

ansible==5.1.0 ✓
python-consul2==0.1.5 ✓
python-gitlab==3.0.0 ✓
ansible-runner==2.1.1 ✓
无需新增 Python 依赖。

二、前端改动
2.1 安装 Monaco Editor
文件: vue-release-web/package.json


"monaco-editor": "^0.36.1",
"monaco-editor-webpack-plugin": "^7.0.1"
并在 vue.config.js 中启用 webpack plugin（参考 monaco-editor-webpack-plugin 文档）。

2.2 重构路由：MDL管理 改为嵌套路由
文件: vue-release-web/src/router/index.js

将现有 /mdl 路由改为父路由（带 alwaysShow: true），添加两个子路由：


{
  path: '/mdl',
  component: Layout,
  alwaysShow: true,
  meta: { title: 'MDL管理', icon: 'dashboard' },
  children: [
    {
      path: 'index',           // /mdl/index → 原发布计划页面
      name: 'mdl',
      component: () => import('@/views/mdl/index'),
      meta: { title: '发布计划', icon: 'dashboard' }
    },
    {
      path: 'config_management',  // /mdl/config_management → 新配置管理页面
      name: 'mdlConfigManagement',
      component: () => import('@/views/mdl/configManagement'),
      meta: { title: '配置管理', icon: 'dashboard' }
    }
  ]
}
同时将 releaseDetail 路由的 activeMenu 指向 /mdl/index。

2.3 新建配置管理主页面
新文件: vue-release-web/src/views/mdl/configManagement.vue

参考 demo 的 frontend/src/views/MainPage.vue（Vue3），改写为 Vue2 Options API：

布局：左侧 el-tree（服务类型→实例→配置文件）+ 右侧 Monaco 编辑器
顶部工具栏：路径前缀显示、搜索、+ 新建、批量修改、结构化批量修改、批量部署、上传、导出、回滚
使用 el-tree 替代 Vue3 的 <el-tree>（API 兼容，写法小调整）
2.4 新建子组件（Vue2 版本）
新文件（参考 demo frontend/src/components/）：

新文件	参考来源	说明
vue-release-web/src/views/mdl/components/ConfigEditor.vue	demo/frontend/src/components/ConfigEditor.vue	Monaco 编辑器，Vue2 适配
vue-release-web/src/views/mdl/components/BatchEditModal.vue	demo/frontend/src/components/BatchEditModal.vue	批量修改弹窗，Vue2 适配
vue-release-web/src/views/mdl/components/DeployModal.vue	demo/frontend/src/components/DeployModal.vue	部署弹窗，Vue2 适配
Vue2 适配要点：

v-model 语法不变，但子组件用 $emit('input') 替代 Vue3 的 emit('update:modelValue')
<script setup> → Options API data() / methods / computed
import { ref, reactive } → data() 返回对象
Element UI 用 el-dialog 替代 Element Plus 的 el-dialog（API 基本相同）
2.5 新建 API 客户端
新文件: vue-release-web/src/api/configMgmt.js


import request from '@/utils/request'

export function getConfigTree(params) {
  return request({ url: '/api/config-mgmt/tree/', method: 'get', params })
}
export function getConfigs(params) {
  return request({ url: '/api/config-mgmt/configs/', method: 'get', params })
}
export function updateConfig(id, data) {
  return request({ url: `/api/config-mgmt/configs/${id}/`, method: 'put', data })
}
export function batchUpdateConfig(data) {
  return request({ url: '/api/config-mgmt/configs/batch_update/', method: 'post', data })
}
export function getConfigSchema(data) {
  return request({ url: '/api/config-mgmt/configs/schema/', method: 'post', data })
}
export function syncFromGitlab(params) {
  return request({ url: '/api/config-mgmt/sync/', method: 'post', params })
}
export function gitCommit(data) {
  return request({ url: '/api/config-mgmt/configs/git_commit/', method: 'post', data })
}
export function pushConsul(data) {
  return request({ url: '/api/config-mgmt/configs/push_consul/', method: 'post', data })
}
export function deployConfig(data) {
  return request({ url: '/api/config-mgmt/deploy/', method: 'post', data })
}
2.6 Vuex store（可选）
如果配置树需要跨组件共享，在 vue-release-web/src/store/modules/ 下新建 configMgmt.js 模块，存储 treeData、loading 状态。简单场景可直接在组件内维护本地 data。

三、关键文件清单
后端（release/）
文件	操作
release/mdl/models.py	修改：追加 4 个新模型
release/api/viewsets/config_mgmt_viewset.py	新建
release/api/urls.py	修改：注册 4 个新 router
release/external/consul_client.py	复用（不修改）
release/external/gitlab_client.py	复用（不修改）
release/ansi/mdl/deploy_config.yml	复用（不修改）
前端（vue-release-web/）
文件	操作
vue-release-web/package.json	修改：添加 monaco-editor 依赖
vue-release-web/vue.config.js	修改：添加 MonacoEditorPlugin
vue-release-web/src/router/index.js	修改：MDL 改嵌套路由
vue-release-web/src/views/mdl/configManagement.vue	新建
vue-release-web/src/views/mdl/components/ConfigEditor.vue	新建
vue-release-web/src/views/mdl/components/BatchEditModal.vue	新建
vue-release-web/src/views/mdl/components/DeployModal.vue	新建
vue-release-web/src/api/configMgmt.js	新建
四、实施顺序
后端：
a. 追加模型到 mdl/models.py
b. 运行 makemigrations mdl + migrate
c. 新建 config_mgmt_viewset.py（先实现 tree 和 configs CRUD）
d. 注册路由到 api/urls.py
e. 测试 API（curl 或浏览器 DRF browsable API）
f. 实现 sync、git_commit、push_consul、deploy actions

前端：
a. 安装 monaco-editor + monaco-editor-webpack-plugin，配置 vue.config.js
b. 修改路由，验证侧边栏显示 "MDL管理 > 发布计划 / 配置管理"
c. 新建 configManagement.vue（先做树形浏览，硬编码假数据验证布局）
d. 接通真实 API（configMgmt.js）
e. 新建子组件：ConfigEditor、BatchEditModal、DeployModal

五、验证方法
启动后端：python manage.py runserver
访问 DRF browsable API：http://localhost:8000/api/config-mgmt/tree/，验证返回树形数据
启动前端：npm run dev
浏览器打开，侧边栏应显示 "MDL管理" 折叠菜单，子项为 "发布计划" 和 "配置管理"
点击 "配置管理"，URL 跳转到 /#/mdl/config_management
左侧树显示服务类型列表（对应截图中的 aaa、aliforward、barcal 等）
点击服务类型 "进入"，展开实例列表
点击配置文件，右侧 Monaco Editor 显示 JSON 内容，可编辑保存
测试 "同步" 按钮（从 GitLab 同步）
测试 "批量修改" 弹窗
测试 "批量部署" 弹窗