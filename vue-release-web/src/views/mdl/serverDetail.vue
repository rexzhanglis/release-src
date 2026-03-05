<template>
  <div class="server-detail">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:16px;font-size:13px">
      <el-breadcrumb-item :to="{ name: 'mdlServers' }">服务器管理</el-breadcrumb-item>
      <el-breadcrumb-item>{{ server ? server.fqdn : '加载中...' }}</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 基本信息卡片 -->
    <el-card v-if="server" shadow="never" style="margin-bottom:16px">
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
        <el-descriptions-item label="标签">
          <el-tag
            v-for="lbl in (server.labels || [])"
            :key="lbl.id"
            size="mini"
            style="margin-right:4px"
          >{{ lbl.name }}</el-tag>
          <span v-if="!server.labels || server.labels.length === 0" style="color:#c0c4cc">-</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- systemd 服务 -->
    <el-card shadow="never">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">systemd 服务</span>
        <div style="display:flex;gap:8px">
          <el-button size="small" type="primary" icon="el-icon-plus" @click="openCreateDialog">新增服务</el-button>
          <el-button
            size="small"
            type="warning"
            icon="el-icon-refresh"
            :disabled="selectedServices.length === 0"
            @click="openBatchRestartDialog"
          >批量重启 {{ selectedServices.length > 0 ? '(' + selectedServices.length + ')' : '' }}</el-button>
          <el-button size="small" icon="el-icon-refresh" :loading="loading" @click="fetchServices">刷新</el-button>
        </div>
      </div>

      <div v-if="!server" style="text-align:center;padding:40px 0;color:#909399">
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
  </div>
</template>

<script>
import {
  getMdlServer,
  getSystemdServices,
  controlSystemdService,
  getSystemdServiceFile,
  manageSystemdService,
} from '@/api/mdlServer'

const DEFAULT_SERVICE_CONTENT = '[Unit]\nDescription=MDL Service\nAfter=network.target\n\n[Service]\nLimitNOFILE=1000000\nLimitCORE=infinity\nUser=root\nWorkingDirectory=/datayes/forward/bin\nType=forking\nExecStart=/datayes/forward/bin/feeder_handler -d\nKillMode=process\nTimeoutStopSec=120\nRestart=on-failure\nStandardOutput=null\nStandardError=null\n\n[Install]\nWantedBy=multi-user.target\n'

export default {
  name: 'ServerDetail',
  data() {
    return {
      server: null,
      serviceList: [],
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
    serverId() {
      return this.$route.params.id
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
    this.fetchServer()
  },
  methods: {
    async fetchServer() {
      try {
        const res = await getMdlServer(this.serverId)
        this.server = res.data
        this.fetchServices()
      } catch (e) {
        this.$message.error('加载服务器信息失败')
      }
    },

    async fetchServices() {
      if (!this.server) return
      this.loading = true
      try {
        const res = await getSystemdServices(this.serverId)
        this.serviceList = (res.data && res.data.services) || []
      } catch (e) {
        this.$message.error('获取 systemd 服务列表失败：' + (e.message || ''))
      } finally {
        this.loading = false
      }
    },

    handleSelectionChange(rows) {
      this.selectedServices = rows
    },

    // 单个 start/stop/enable/disable
    async handleControl(svc, action) {
      try {
        await this.$confirm(
          '确认对「' + svc.name + '」执行 ' + action + '？',
          '确认操作',
          { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        const res = await controlSystemdService(this.serverId, { service: svc.name, action })
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

    // 单服务重启（含 consul_pull 选项）
    openRestartDialog(svc) {
      this.restartDialog.services = [svc.name]
      this.restartDialog.consulPull = false
      this.restartDialog.loading = false
      this.restartDialog.visible = true
    },

    async submitRestart() {
      this.restartDialog.loading = true
      try {
        const res = await controlSystemdService(this.serverId, {
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

    // 批量重启
    openBatchRestartDialog() {
      this.batchRestartDialog.consulPull = false
      this.batchRestartDialog.loading = false
      this.batchRestartDialog.visible = true
    },

    async submitBatchRestart() {
      this.batchRestartDialog.loading = true
      try {
        const res = await controlSystemdService(this.serverId, {
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

    // 新增 service
    openCreateDialog() {
      this.editDialog.op = 'create'
      this.editDialog.name = ''
      this.editDialog.content = DEFAULT_SERVICE_CONTENT
      this.editDialog.loading = false
      this.editDialog.visible = true
    },

    // 编辑 service（先读取远端文件内容）
    async openEditDialog(svc) {
      this.editDialog.op = 'update'
      this.editDialog.name = svc.name
      this.editDialog.content = ''
      this.editDialog.loading = false
      this.editDialog.visible = true
      try {
        const res = await getSystemdServiceFile(this.serverId, svc.name)
        this.editDialog.content = (res.data && res.data.content) || ''
      } catch (e) {
        this.$message.warning('读取 service 文件失败，可手动输入内容')
      }
    },

    async submitEditDialog() {
      const { op, name, content } = this.editDialog
      if (!name || !name.endsWith('.service')) {
        return this.$message.warning('服务名必须以 .service 结尾')
      }
      if (!content.trim()) {
        return this.$message.warning('配置内容不能为空')
      }
      this.editDialog.loading = true
      try {
        const res = await manageSystemdService(this.serverId, { op, name, content })
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

    // 删除 service
    async handleDelete(svc) {
      try {
        await this.$confirm(
          '确认删除「' + svc.name + '」的 service 文件？此操作不可恢复。',
          '删除确认',
          { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' }
        )
      } catch { return }
      try {
        const res = await manageSystemdService(this.serverId, { op: 'delete', name: svc.name })
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

    // 重命名 service
    openRenameDialog(svc) {
      this.renameDialog.name = svc.name
      this.renameDialog.newName = ''
      this.renameDialog.loading = false
      this.renameDialog.visible = true
    },

    async submitRename() {
      const { name, newName } = this.renameDialog
      if (!newName || !newName.endsWith('.service')) {
        return this.$message.warning('新服务名必须以 .service 结尾')
      }
      this.renameDialog.loading = true
      try {
        const res = await manageSystemdService(this.serverId, { op: 'rename', name, new_name: newName })
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
