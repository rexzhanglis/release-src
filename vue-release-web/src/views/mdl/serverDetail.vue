<template>
  <div class="server-detail">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:16px;font-size:13px">
      <el-breadcrumb-item :to="{ name: 'mdlServers' }">服务器管理</el-breadcrumb-item>
      <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 物理机信息卡片（host 模式） -->
    <el-card v-if="isHostMode && host" shadow="never" style="margin-bottom:16px">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">{{ host.fqdn }}</span>
        <el-tag type="info" size="small" effect="plain">物理机</el-tag>
      </div>
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="IP 地址">{{ host.ip }}</el-descriptions-item>
        <el-descriptions-item label="SSH 用户">{{ host.user || 'root' }}</el-descriptions-item>
        <el-descriptions-item label="远端 Python">
          <span class="mono">{{ host.remote_python || '-' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 服务实例列表（host 模式） -->
    <el-card v-if="isHostMode" shadow="never" style="margin-bottom:16px">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">服务实例</span>
        <div style="display:flex;gap:8px">
          <el-button size="small" type="primary" icon="el-icon-plus" @click="handleAddService">新增服务实例</el-button>
          <el-button size="small" icon="el-icon-refresh" :loading="servicesLoading" @click="fetchMdlServices">刷新</el-button>
        </div>
      </div>
      <el-table
        v-loading="servicesLoading"
        :data="mdlServices"
        border
        size="small"
        highlight-current-row
        :current-row-key="activeServerId"
        row-key="id"
        @current-change="handleServiceSelect"
        style="width:100%"
      >
        <el-table-column prop="service_name" label="服务名" min-width="160" show-overflow-tooltip />
        <el-table-column prop="role_name" label="角色" width="120" />
        <el-table-column prop="install_dir" label="安装目录" min-width="180" show-overflow-tooltip>
          <template slot-scope="{ row }">
            <span class="mono">{{ row.install_dir }}</span>
          </template>
        </el-table-column>
        <el-table-column label="初始化状态" width="110" align="center">
          <template slot-scope="{ row }">
            <el-tag :type="initStatusType(row.init_status)" size="mini" effect="plain">
              {{ initStatusLabel(row.init_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template slot-scope="{ row }">
            <el-button size="mini" type="text" @click.stop="handleServiceSelect(row)">
              <span :style="activeServerId === row.id ? 'color:#67c23a;font-weight:600' : ''">
                {{ activeServerId === row.id ? '✓ 已选中' : '选中' }}
              </span>
            </el-button>
            <el-button size="mini" type="text" icon="el-icon-edit" @click.stop="handleEditService(row)">编辑</el-button>
            <el-button
              v-if="row.init_status !== 'ready'"
              size="mini" type="text" icon="el-icon-setting"
              style="color:#409eff" @click.stop="handleInitService(row)"
            >初始化</el-button>
            <el-button
              size="mini" type="text" icon="el-icon-delete"
              style="color:#f56c6c" @click.stop="handleDeleteService(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!servicesLoading && mdlServices.length === 0" class="empty-placeholder" style="padding:24px 0">
        <p style="color:#909399;font-size:13px;text-align:center">暂无服务实例，点击「新增服务实例」开始</p>
      </div>
    </el-card>

    <!-- 服务实例基本信息（server 模式 - 兼容旧路由） -->
    <el-card v-if="!isHostMode && server" shadow="never" style="margin-bottom:16px">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">{{ server.fqdn }}</span>
        <el-tag :type="statusType" size="small" effect="plain">{{ statusLabel }}</el-tag>
      </div>
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="IP 地址">{{ server.ip }}</el-descriptions-item>
        <el-descriptions-item label="服务名">{{ server.service_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SSH 用户">{{ server.user || 'root' }}</el-descriptions-item>
        <el-descriptions-item label="安装目录">
          <span class="mono">{{ server.install_dir || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="备份目录">
          <span class="mono">{{ server.backups_dir || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="Python 路径">
          <span class="mono">{{ server.remote_python || '-' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- systemd 服务 -->
    <el-card shadow="never">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">
          systemd 服务
          <span v-if="isHostMode && activeServer" style="font-size:12px;color:#909399;font-weight:400;margin-left:8px">
            — {{ activeServer.service_name }}
          </span>
          <span v-if="systemdRefreshedAt" style="font-size:11px;color:#c0c4cc;font-weight:400;margin-left:10px">
            缓存更新: {{ systemdRefreshedAt }}
          </span>
        </span>
        <div style="display:flex;gap:8px">
          <el-button size="small" type="primary" icon="el-icon-plus" @click="openCreateDialog">新增服务</el-button>
          <el-button
            size="small"
            type="warning"
            icon="el-icon-refresh"
            :disabled="selectedServices.length === 0"
            @click="openBatchRestartDialog"
          >批量重启 {{ selectedServices.length > 0 ? '(' + selectedServices.length + ')' : '' }}</el-button>
          <el-button size="small" icon="el-icon-refresh" :loading="loading" @click="fetchServices">读缓存</el-button>
          <el-button size="small" type="primary" plain icon="el-icon-refresh" :loading="refreshing" @click="handleRefreshNow">实时刷新</el-button>
        </div>
      </div>

      <!-- host 模式下未选中服务实例时的提示 -->
      <div v-if="isHostMode && !activeServer" style="text-align:center;padding:40px 0;color:#909399">
        <i class="el-icon-arrow-up" style="font-size:24px"></i>
        <p style="margin-top:8px;font-size:13px">请在上方「服务实例」表格中选择一个服务实例，查看其 systemd 服务状态</p>
      </div>

      <div v-else-if="!activeServer && !server" style="text-align:center;padding:40px 0;color:#909399">
        <i class="el-icon-loading" style="font-size:24px"></i>
        <p style="margin-top:8px">加载中...</p>
      </div>

      <template v-else>
        <!-- 搜索 -->
        <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
          <el-input
            v-model="svcSearch"
            placeholder="过滤服务名"
            clearable
            size="small"
            prefix-icon="el-icon-search"
            style="width:220px"
          />
          <el-select v-model="svcStateFilter" placeholder="运行状态" clearable size="small" style="width:120px">
            <el-option label="active" value="active" />
            <el-option label="inactive" value="inactive" />
            <el-option label="failed" value="failed" />
          </el-select>
          <span style="font-size:12px;color:#909399;margin-left:auto">
            共 {{ filteredServices.length }} / {{ serviceList.length }} 个服务
          </span>
        </div>

        <el-table
          v-loading="loading"
          :data="filteredServices"
          border
          size="small"
          max-height="560"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column prop="name" label="服务名" min-width="220" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span class="mono" style="font-size:12px">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="运行状态" width="100" align="center">
            <template slot-scope="{ row }">
              <el-tag
                :type="row.active_state === 'active' ? 'success' : row.active_state === 'failed' ? 'danger' : 'info'"
                size="mini"
              >{{ row.active_state }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="子状态" width="90" align="center">
            <template slot-scope="{ row }">
              <span style="font-size:11px;color:#909399">{{ row.sub_state }}</span>
            </template>
          </el-table-column>
          <el-table-column label="自启动" width="90" align="center">
            <template slot-scope="{ row }">
              <el-tag
                v-if="row.enabled !== null"
                :type="row.enabled === 'enabled' ? 'success' : 'info'"
                size="mini"
              >{{ row.enabled === 'enabled' ? '已启用' : row.enabled || '-' }}</el-tag>
              <span v-else style="color:#c0c4cc;font-size:11px">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span style="font-size:11px;color:#606266">{{ row.description }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320" align="center" fixed="right">
            <template slot-scope="{ row }">
              <el-button
                v-if="row.active_state !== 'active'"
                size="mini" type="text" style="color:#67c23a"
                @click="handleControl(row, 'start')"
              >启动</el-button>
              <el-button
                v-else
                size="mini" type="text" style="color:#e6a23c"
                @click="handleControl(row, 'stop')"
              >停止</el-button>
              <el-button
                v-if="row.active_state === 'active'"
                size="mini" type="text"
                @click="openRestartDialog(row)"
              >重启</el-button>
              <el-divider direction="vertical" />
              <el-button
                v-if="row.enabled !== 'enabled'"
                size="mini" type="text" style="color:#409eff"
                @click="handleControl(row, 'enable')"
              >自启</el-button>
              <el-button
                v-else
                size="mini" type="text" style="color:#f56c6c"
                @click="handleControl(row, 'disable')"
              >禁用</el-button>
              <el-divider direction="vertical" />
              <el-button size="mini" type="text" @click="openEditDialog(row)">编辑</el-button>
              <el-button size="mini" type="text" @click="openRenameDialog(row)">重命名</el-button>
              <el-button size="mini" type="text" style="color:#f56c6c" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!loading && serviceList.length === 0" style="text-align:center;padding:40px 0;color:#909399">
          <i class="el-icon-tickets" style="font-size:40px;color:#dcdfe6"></i>
          <p style="margin-top:8px;font-size:13px">未查询到 systemd 服务</p>
        </div>
      </template>
    </el-card>

    <!-- 新增/编辑 service 文件弹窗 -->
    <el-dialog
      :title="editDialog.op === 'create' ? '新增 service 文件' : '编辑 service 文件'"
      :visible.sync="editDialog.visible"
      width="680px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" size="small">
        <el-form-item label="服务名">
          <el-input
            v-model="editDialog.name"
            :disabled="editDialog.op === 'update'"
            placeholder="如 mdl-forward.service"
          />
          <div v-if="editDialog.op === 'create'" style="font-size:11px;color:#909399;margin-top:4px">
            必须以 .service 结尾，建议以 mdl- 开头
          </div>
        </el-form-item>
        <el-form-item label="配置内容">
          <el-input
            v-model="editDialog.content"
            type="textarea"
            :rows="16"
            style="font-family:monospace"
            placeholder="[Unit]&#10;Description=..."
          />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button size="small" @click="editDialog.visible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="editDialog.loading" @click="submitEditDialog">
          {{ editDialog.op === 'create' ? '创建' : '保存' }}
        </el-button>
      </span>
    </el-dialog>

    <!-- 重命名弹窗 -->
    <el-dialog title="重命名 service" :visible.sync="renameDialog.visible" width="480px" :close-on-click-modal="false">
      <el-form label-width="90px" size="small">
        <el-form-item label="原服务名">
          <el-input :value="renameDialog.name" disabled />
        </el-form-item>
        <el-form-item label="新服务名">
          <el-input v-model="renameDialog.newName" placeholder="如 mdl-forward2.service" />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button size="small" @click="renameDialog.visible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="renameDialog.loading" @click="submitRename">确认重命名</el-button>
      </span>
    </el-dialog>

    <!-- 单服务重启弹窗（含 consul_pull 选项）-->
    <el-dialog title="重启服务" :visible.sync="restartDialog.visible" width="440px" :close-on-click-modal="false">
      <div style="margin-bottom:16px;font-size:13px">
        确认重启 <strong>{{ restartDialog.services.join(', ') }}</strong>？
      </div>
      <el-checkbox v-model="restartDialog.consulPull" style="font-size:13px">
        重启前先拉取最新配置（执行 consul_pull.py）
      </el-checkbox>
      <span slot="footer">
        <el-button size="small" @click="restartDialog.visible = false">取消</el-button>
        <el-button size="small" type="warning" :loading="restartDialog.loading" @click="submitRestart">确认重启</el-button>
      </span>
    </el-dialog>

    <!-- 批量重启弹窗 -->
    <el-dialog title="批量重启服务" :visible.sync="batchRestartDialog.visible" width="480px" :close-on-click-modal="false">
      <div style="margin-bottom:12px;font-size:13px">
        即将重启以下 {{ selectedServices.length }} 个服务：
      </div>
      <div style="background:#f5f7fa;padding:8px 12px;border-radius:4px;font-size:12px;font-family:monospace;max-height:120px;overflow:auto">
        <div v-for="s in selectedServices" :key="s.name">{{ s.name }}</div>
      </div>
      <div style="margin-top:16px">
        <el-checkbox v-model="batchRestartDialog.consulPull" style="font-size:13px">
          重启前先拉取最新配置（执行 consul_pull.py）
        </el-checkbox>
      </div>
      <span slot="footer">
        <el-button size="small" @click="batchRestartDialog.visible = false">取消</el-button>
        <el-button size="small" type="warning" :loading="batchRestartDialog.loading" @click="submitBatchRestart">
          确认批量重启
        </el-button>
      </span>
    </el-dialog>

    <!-- 新增/编辑服务实例弹窗 -->
    <service-form-modal
      v-if="isHostMode"
      v-model="showServiceForm"
      :host-id="routeId"
      :server="currentService"
      :existing-services="currentService ? [] : mdlServices"
      @success="fetchMdlServices"
    />

    <!-- 服务实例初始化弹窗 -->
    <init-server-modal
      v-if="isHostMode"
      v-model="showInitModal"
      :server="initTargetService"
      @done="fetchMdlServices"
    />
  </div>
</template>

<script>
import {
  getHost,
  getMdlServer,
  getMdlServers,
  deleteMdlServer,
  getSystemdServices,
  controlSystemdService,
  getSystemdServiceFile,
  manageSystemdService,
} from '@/api/mdlServer'
import ServiceFormModal from './components/ServiceFormModal'
import InitServerModal from './components/InitServerModal'

const DEFAULT_SERVICE_CONTENT = '[Unit]\nDescription=MDL Service\nAfter=network.target\n\n[Service]\nLimitNOFILE=1000000\nLimitCORE=infinity\nUser=root\nWorkingDirectory=/datayes/forward/bin\nType=forking\nExecStart=/datayes/forward/bin/feeder_handler -d\nKillMode=process\nTimeoutStopSec=120\nRestart=on-failure\nStandardOutput=null\nStandardError=null\n\n[Install]\nWantedBy=multi-user.target\n'

export default {
  name: 'ServerDetail',
  components: { ServiceFormModal, InitServerModal },
  data() {
    return {
      // host 模式
      host: null,
      mdlServices: [],
      servicesLoading: false,
      activeServerId: null,
      showServiceForm: false,
      currentService: null,
      showInitModal: false,
      initTargetService: null,

      // server 模式（兼容旧路由）
      server: null,

      // systemd
      serviceList: [],
      systemdRefreshedAt: '',
      refreshing: false,
      loading: false,
      svcSearch: '',
      svcStateFilter: '',
      selectedServices: [],

      editDialog: {
        visible: false,
        op: 'create',
        name: '',
        content: '',
        loading: false,
      },

      renameDialog: {
        visible: false,
        name: '',
        newName: '',
        loading: false,
      },

      restartDialog: {
        visible: false,
        services: [],
        consulPull: false,
        loading: false,
      },

      batchRestartDialog: {
        visible: false,
        consulPull: false,
        loading: false,
      },
    }
  },
  computed: {
    routeId() {
      return this.$route.params.id
    },
    isHostMode() {
      return this.$route.query.type === 'host'
    },
    // The MdlServer instance used for systemd actions
    activeServer() {
      if (this.isHostMode) {
        return this.mdlServices.find(s => s.id === this.activeServerId) || null
      }
      return this.server
    },
    activeServerIdForApi() {
      return this.activeServer ? this.activeServer.id : null
    },
    pageTitle() {
      if (this.isHostMode) return this.host ? this.host.fqdn : '加载中...'
      return this.server ? this.server.fqdn : '加载中...'
    },
    statusLabel() {
      const map = { uninitialized: '未初始化', initializing: '初始化中', ready: '运行中', failed: '初始化失败', retired: '已退役' }
      return map[this.server && this.server.init_status] || '未知'
    },
    statusType() {
      const map = { uninitialized: 'info', initializing: 'warning', ready: 'success', failed: 'danger', retired: '' }
      return map[this.server && this.server.init_status] || 'info'
    },
    filteredServices() {
      return this.serviceList.filter(s => {
        const matchName = !this.svcSearch || s.name.includes(this.svcSearch)
        const matchState = !this.svcStateFilter || s.active_state === this.svcStateFilter
        return matchName && matchState
      })
    },
  },
  created() {
    if (this.isHostMode) {
      this.fetchHost()
    } else {
      this.fetchServer()
    }
  },
  methods: {
    initStatusLabel(status) {
      const map = { uninitialized: '未初始化', initializing: '初始化中', ready: '运行中', failed: '初始化失败', retired: '已退役' }
      return map[status] || status || '-'
    },
    initStatusType(status) {
      const map = { uninitialized: 'info', initializing: 'warning', ready: 'success', failed: 'danger', retired: '' }
      return map[status] || 'info'
    },

    // ---- host 模式 ----
    async fetchHost() {
      try {
        const res = await getHost(this.routeId)
        this.host = res.data
        await this.fetchMdlServices()
      } catch {
        this.$message.error('加载机器信息失败')
      }
    },

    async fetchMdlServices() {
      this.servicesLoading = true
      try {
        const res = await getMdlServers({ host_id: this.routeId, page_size: 100 })
        const data = res.data
        this.mdlServices = Array.isArray(data) ? data
          : (data && Array.isArray(data.results)) ? data.results : []
        // 自动选中第一个（若当前选中的已不存在则重置）
        if (this.activeServerId && !this.mdlServices.find(s => s.id === this.activeServerId)) {
          this.activeServerId = null
          this.serviceList = []
        }
        if (!this.activeServerId && this.mdlServices.length > 0) {
          this.handleServiceSelect(this.mdlServices[0])
        }
      } catch {
        this.$message.error('加载服务实例列表失败')
      } finally {
        this.servicesLoading = false
      }
    },

    handleServiceSelect(row) {
      if (!row) return
      this.activeServerId = row.id
      this.serviceList = []
      this.fetchServices()
    },

    handleAddService() {
      this.currentService = null
      this.showServiceForm = true
    },

    handleEditService(row) {
      this.currentService = row
      this.showServiceForm = true
    },

    handleInitService(row) {
      this.initTargetService = row
      this.showInitModal = true
    },

    async handleDeleteService(row) {
      try {
        await this.$confirm(
          `确认删除服务实例 ${row.service_name}？删除后将无法恢复。`,
          '删除确认',
          { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        await deleteMdlServer(row.id)
        this.$message.success('删除成功')
        if (this.activeServerId === row.id) {
          this.activeServerId = null
          this.serviceList = []
        }
        await this.fetchMdlServices()
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '删除失败'
        this.$message.error(msg)
      }
    },

    // ---- server 模式（旧路由兼容） ----
    async fetchServer() {
      try {
        const res = await getMdlServer(this.routeId)
        this.server = res.data
        this.fetchServices()
      } catch {
        this.$message.error('加载服务器信息失败')
      }
    },

    // ---- systemd ----
    async fetchServices() {
      const id = this.activeServerIdForApi || (this.isHostMode ? null : this.routeId)
      if (!id) return
      this.loading = true
      try {
        const res = await getSystemdServices(id)
        const d = res.data || {}
        this.serviceList = d.services || []
        this.systemdRefreshedAt = d.refreshed_at || ''
      } catch (e) {
        this.$message.error('获取 systemd 服务列表失败：' + (e.message || ''))
      } finally {
        this.loading = false
      }
    },

    async handleRefreshNow() {
      const id = this.activeServerIdForApi || (this.isHostMode ? null : this.routeId)
      if (!id) return
      this.refreshing = true
      try {
        const res = await getSystemdServices(id, { refresh: 1 })
        const d = res.data || {}
        this.serviceList = d.services || []
        this.systemdRefreshedAt = d.refreshed_at || ''
        this.$message.success('已从远端实时刷新')
      } catch (e) {
        this.$message.error('实时刷新失败：' + (e.message || ''))
      } finally {
        this.refreshing = false
      }
    },

    handleSelectionChange(rows) {
      this.selectedServices = rows
    },

    async handleControl(svc, action) {
      const id = this.activeServerIdForApi || this.routeId
      try {
        await this.$confirm(
          '确认对「' + svc.name + '」执行 ' + action + '？',
          '确认操作',
          { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        const res = await controlSystemdService(id, { service: svc.name, action })
        if (res.data && res.data.ok) {
          this.$message.success(action + ' 成功')
          await this.fetchServices()
        } else {
          this.$message.error(action + ' 失败：' + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('操作失败：' + (e.message || ''))
      }
    },

    openRestartDialog(svc) {
      this.restartDialog.services = [svc.name]
      this.restartDialog.consulPull = false
      this.restartDialog.loading = false
      this.restartDialog.visible = true
    },

    async submitRestart() {
      const id = this.activeServerIdForApi || this.routeId
      this.restartDialog.loading = true
      try {
        const res = await controlSystemdService(id, {
          service: this.restartDialog.services[0],
          action: 'restart',
          consul_pull: this.restartDialog.consulPull,
        })
        if (res.data && res.data.ok) {
          this.$message.success('重启成功')
          this.restartDialog.visible = false
          await this.fetchServices()
        } else {
          this.$message.error('重启失败：' + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('操作失败：' + (e.message || ''))
      } finally {
        this.restartDialog.loading = false
      }
    },

    openBatchRestartDialog() {
      this.batchRestartDialog.consulPull = false
      this.batchRestartDialog.loading = false
      this.batchRestartDialog.visible = true
    },

    async submitBatchRestart() {
      const id = this.activeServerIdForApi || this.routeId
      this.batchRestartDialog.loading = true
      try {
        const res = await controlSystemdService(id, {
          services: this.selectedServices.map(s => s.name),
          action: 'restart',
          consul_pull: this.batchRestartDialog.consulPull,
        })
        if (res.data && res.data.ok) {
          this.$message.success('批量重启成功')
          this.batchRestartDialog.visible = false
          await this.fetchServices()
        } else {
          this.$message.error('批量重启失败：' + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('操作失败：' + (e.message || ''))
      } finally {
        this.batchRestartDialog.loading = false
      }
    },

    openCreateDialog() {
      this.editDialog.op = 'create'
      this.editDialog.name = ''
      this.editDialog.content = DEFAULT_SERVICE_CONTENT
      this.editDialog.loading = false
      this.editDialog.visible = true
    },

    async openEditDialog(svc) {
      const id = this.activeServerIdForApi || this.routeId
      this.editDialog.op = 'update'
      this.editDialog.name = svc.name
      this.editDialog.content = ''
      this.editDialog.loading = false
      this.editDialog.visible = true
      try {
        const res = await getSystemdServiceFile(id, svc.name)
        this.editDialog.content = (res.data && res.data.content) || ''
      } catch {
        this.$message.warning('读取 service 文件失败，可手动输入内容')
      }
    },

    async submitEditDialog() {
      const id = this.activeServerIdForApi || this.routeId
      const { op, name, content } = this.editDialog
      if (!name || !name.endsWith('.service')) {
        return this.$message.warning('服务名必须以 .service 结尾')
      }
      if (!content.trim()) {
        return this.$message.warning('配置内容不能为空')
      }
      this.editDialog.loading = true
      try {
        const res = await manageSystemdService(id, { op, name, content })
        if (res.data && res.data.ok) {
          this.$message.success(op === 'create' ? '创建成功' : '保存成功')
          this.editDialog.visible = false
          await this.fetchServices()
        } else {
          this.$message.error((op === 'create' ? '创建' : '保存') + '失败：' + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('操作失败：' + (e.message || ''))
      } finally {
        this.editDialog.loading = false
      }
    },

    async handleDelete(svc) {
      const id = this.activeServerIdForApi || this.routeId
      try {
        await this.$confirm(
          '确认删除「' + svc.name + '」的 service 文件？此操作不可恢复。',
          '删除确认',
          { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
        )
      } catch { return }
      try {
        const res = await manageSystemdService(id, { op: 'delete', name: svc.name })
        if (res.data && res.data.ok) {
          this.$message.success('删除成功')
          await this.fetchServices()
        } else {
          this.$message.error('删除失败：' + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('删除失败：' + (e.message || ''))
      }
    },

    openRenameDialog(svc) {
      this.renameDialog.name = svc.name
      this.renameDialog.newName = ''
      this.renameDialog.loading = false
      this.renameDialog.visible = true
    },

    async submitRename() {
      const id = this.activeServerIdForApi || this.routeId
      const { name, newName } = this.renameDialog
      if (!newName || !newName.endsWith('.service')) {
        return this.$message.warning('新服务名必须以 .service 结尾')
      }
      this.renameDialog.loading = true
      try {
        const res = await manageSystemdService(id, { op: 'rename', name, new_name: newName })
        if (res.data && res.data.ok) {
          this.$message.success('重命名成功')
          this.renameDialog.visible = false
          await this.fetchServices()
        } else {
          this.$message.error('重命名失败：' + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('重命名失败：' + (e.message || ''))
      } finally {
        this.renameDialog.loading = false
      }
    },
  },
}
</script>

<style scoped>
.server-detail {
  padding: 16px;
}
.mono {
  font-family: monospace;
  font-size: 12px;
}
</style>
