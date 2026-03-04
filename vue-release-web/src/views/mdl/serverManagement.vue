<template>
  <div class="server-management">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="搜索 FQDN / IP / 服务名"
        clearable
        size="small"
        style="width:220px"
        prefix-icon="el-icon-search"
        @input="handleSearch"
      />
      <el-select
        v-model="filterLabelId"
        placeholder="按标签筛选"
        clearable
        size="small"
        style="width:160px;margin-left:8px"
        @change="handleLabelFilter"
      >
        <el-option
          v-for="lbl in allLabels"
          :key="lbl.id"
          :label="lbl.name"
          :value="lbl.id"
        />
      </el-select>
      <el-button
        type="primary"
        size="small"
        icon="el-icon-plus"
        style="margin-left:12px"
        @click="handleAdd"
      >
        新增服务器
      </el-button>
      <el-button
        size="small"
        icon="el-icon-document-add"
        style="margin-left:8px"
        @click="showBatchAdd = true"
      >
        批量新增
      </el-button>
      <el-button
        size="small"
        icon="el-icon-s-tools"
        style="margin-left:8px;color:#e6a23c;border-color:#e6a23c"
        :disabled="selectedRows.length === 0"
        @click="handleBatchInit"
      >
        批量初始化{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
      </el-button>
      <el-button
        size="small"
        icon="el-icon-price-tag"
        style="margin-left:8px"
        @click="showLabelMgr = true"
      >
        标签管理
      </el-button>
      <el-button
        size="small"
        icon="el-icon-document"
        style="margin-left:8px"
        @click="openOpLog"
      >
        操作日志
      </el-button>
      <el-popover
        placement="bottom-end"
        trigger="click"
        width="180"
        style="margin-left:8px"
      >
        <div>
          <div style="font-size:12px;color:#909399;margin-bottom:8px">选择显示的列</div>
          <el-checkbox-group v-model="visibleCols" style="display:flex;flex-direction:column;gap:4px">
            <el-checkbox v-for="c in colOptions" :key="c.key" :label="c.key" style="margin-left:0">{{ c.label }}</el-checkbox>
          </el-checkbox-group>
        </div>
        <el-button slot="reference" size="small" icon="el-icon-setting">列</el-button>
      </el-popover>
      <el-button
        size="small"
        icon="el-icon-refresh"
        :loading="loading"
        @click="fetchServers"
      >
        刷新
      </el-button>
    </div>

    <!-- 表格 -->
    <el-table
      v-loading="loading"
      :data="sortedServers"
      border
      size="small"
      style="width:100%;margin-top:12px"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
    >
      <el-table-column type="selection" width="40" />
      <el-table-column prop="fqdn" label="FQDN" min-width="160" show-overflow-tooltip sortable="custom" />
      <el-table-column v-if="visibleCols.includes('ip')" prop="ip" label="IP 地址" width="140" sortable="custom" />
      <el-table-column v-if="visibleCols.includes('service_name')" prop="service_name" label="服务名" width="140" sortable="custom" />
      <el-table-column v-if="visibleCols.includes('labels')" label="标签" width="160">
        <template slot-scope="{ row }">
          <el-tag
            v-for="lbl in (row.labels || [])"
            :key="lbl.id"
            size="mini"
            style="margin-right:4px;margin-bottom:2px"
          >{{ lbl.name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="visibleCols.includes('init_status')" label="状态" width="110" align="center">
        <template slot-scope="{ row }">
          <el-tag
            :type="initStatusType(row.init_status)"
            size="small"
            effect="plain"
          >{{ initStatusLabel(row.init_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="visibleCols.includes('install_dir')" prop="install_dir" label="安装目录" min-width="160" show-overflow-tooltip sortable="custom">
        <template slot-scope="{ row }">
          <span class="mono">{{ row.install_dir }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="visibleCols.includes('backups_dir')" prop="backups_dir" label="备份目录" min-width="140" show-overflow-tooltip sortable="custom">
        <template slot-scope="{ row }">
          <span class="mono">{{ row.backups_dir }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="visibleCols.includes('remote_python')" prop="remote_python" label="Python 路径" width="180" show-overflow-tooltip sortable="custom">
        <template slot-scope="{ row }">
          <span class="mono">{{ row.remote_python }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template slot-scope="{ row }">
          <el-button size="mini" type="text" icon="el-icon-edit" @click="handleEdit(row)">编辑</el-button>

          <!-- 未初始化 / 初始化失败 → 初始化 -->
          <el-tooltip v-if="row.init_status === 'initializing'" content="初始化进行中，请等待完成" placement="top">
            <span><el-button size="mini" type="text" icon="el-icon-loading" disabled>初始化中</el-button></span>
          </el-tooltip>
          <el-button
            v-else-if="row.init_status === 'uninitialized' || row.init_status === 'failed'"
            size="mini" type="text" icon="el-icon-s-tools"
            style="color:#e6a23c"
            @click="handleInit(row)"
          >{{ row.init_status === 'failed' ? '重新初始化' : '初始化' }}</el-button>

          <!-- 运行中 → 变更配置 + 更多（重新初始化） -->
          <template v-else-if="row.init_status === 'ready'">
            <el-button size="mini" type="text" icon="el-icon-setting" style="color:#409eff" @click="handleConfigChange(row)">变更配置</el-button>
            <el-dropdown size="mini" trigger="click" @command="cmd => handleRowCommand(cmd, row)" style="margin-left:4px">
              <el-button size="mini" type="text" icon="el-icon-more" style="color:#909399" />
              <el-dropdown-menu slot="dropdown">
                <el-dropdown-item command="services" icon="el-icon-tickets">systemd 服务</el-dropdown-item>
                <el-dropdown-item command="reinit" icon="el-icon-s-tools">重新初始化</el-dropdown-item>
              </el-dropdown-menu>
            </el-dropdown>
          </template>

          <el-button size="mini" type="text" icon="el-icon-delete" style="color:#f56c6c" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-if="total > pageSize"
      background
      layout="prev, pager, next, total"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      style="margin-top:12px;text-align:right"
      @current-change="handlePageChange"
    />

    <!-- 空状态 -->
    <div v-if="!loading && servers.length === 0" class="empty-placeholder">
      <i class="el-icon-monitor" style="font-size:40px;color:#dcdfe6"></i>
      <p style="color:#909399;margin-top:8px;font-size:13px">暂无服务器记录</p>
    </div>

    <!-- 新增/编辑弹窗 -->
    <server-form-modal
      v-model="showForm"
      :server="currentServer"
      :all-labels="allLabels"
      @success="fetchServers"
      @init-after-create="handleInitAfterCreate"
    />

    <!-- 初始化弹窗 -->
    <init-server-modal
      v-model="showInit"
      :server="currentServer"
      @done="fetchServers"
    />

    <!-- 批量新增弹窗 -->
    <batch-add-modal
      v-model="showBatchAdd"
      :all-labels="allLabels"
      @success="fetchServers"
    />

    <!-- 批量初始化弹窗 -->
    <batch-init-modal
      v-model="showBatchInit"
      :servers="selectedRows"
    />

    <!-- 标签管理弹窗 -->
    <el-dialog
      title="标签管理"
      :visible.sync="showLabelMgr"
      width="420px"
      :close-on-click-modal="false"
      @open="fetchLabels"
    >
      <div style="display:flex;margin-bottom:12px">
        <el-input
          v-model="newLabelName"
          placeholder="输入新标签名"
          size="small"
          style="flex:1;margin-right:8px"
          @keyup.enter.native="handleCreateLabel"
        />
        <el-button type="primary" size="small" @click="handleCreateLabel">添加</el-button>
      </div>
      <el-table :data="allLabels" size="small" border>
        <el-table-column prop="name" label="标签名" />
        <el-table-column label="操作" width="80" align="center">
          <template slot-scope="{ row }">
            <el-button
              size="mini"
              type="text"
              style="color:#f56c6c"
              icon="el-icon-delete"
              @click="handleDeleteLabel(row)"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
    <!-- 操作日志弹窗 -->
    <el-dialog
      title="服务器操作日志"
      :visible.sync="showOpLog"
      width="900px"
      :close-on-click-modal="false"
      @open="fetchOpLogs"
    >
      <!-- 筛选栏 -->
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
        <el-select v-model="opLogAction" placeholder="操作类型" clearable size="small" style="width:140px" @change="fetchOpLogs">
          <el-option label="服务器初始化" value="server_init" />
          <el-option label="新增服务器" value="server_create" />
          <el-option label="删除服务器" value="server_delete" />
        </el-select>
        <el-select v-model="opLogStatus" placeholder="结果" clearable size="small" style="width:110px" @change="fetchOpLogs">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-input v-model="opLogKeyword" placeholder="搜索 FQDN / IP" clearable size="small" style="width:200px" @input="opLogSearch" />
        <el-button size="small" icon="el-icon-refresh" :loading="opLogLoading" @click="fetchOpLogs">刷新</el-button>
      </div>

      <el-table v-loading="opLogLoading" :data="opLogs" border size="small" style="width:100%">
        <el-table-column label="时间" width="155">
          <template slot-scope="{ row }">{{ row.created_time | formatTime }}</template>
        </el-table-column>
        <el-table-column label="操作类型" width="120">
          <template slot-scope="{ row }">{{ row.action_display }}</template>
        </el-table-column>
        <el-table-column prop="operator" label="操作人" width="110" />
        <el-table-column label="结果" width="80" align="center">
          <template slot-scope="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="mini">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="instance_names" label="服务器" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="80" align="center">
          <template slot-scope="{ row }">
            <el-button
              v-if="row.deploy_task_id"
              size="mini"
              type="text"
              @click="showInitLog(row)"
            >查看日志</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="opLogTotal > opLogPageSize"
        background
        layout="prev, pager, next, total"
        :total="opLogTotal"
        :page-size="opLogPageSize"
        :current-page="opLogPage"
        style="margin-top:10px;text-align:right"
        @current-change="p => { opLogPage = p; fetchOpLogs() }"
      />

      <div slot="footer">
        <el-button @click="showOpLog = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- 初始化日志详情弹窗 -->
    <el-dialog
      :visible.sync="showInitLogDialog"
      :title="`初始化日志 — ${initLogTitle}`"
      width="760px"
      append-to-body
    >
      <pre class="init-log">{{ initLogContent || '加载中...' }}</pre>
      <div slot="footer">
        <el-button @click="showInitLogDialog = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- systemd 服务管理弹窗 -->
    <el-dialog
      :visible.sync="showSystemd"
      :title="`systemd 服务 — ${systemdServer ? systemdServer.fqdn : ''}`"
      width="860px"
      :close-on-click-modal="false"
    >
      <el-table v-loading="systemdLoading" :data="systemdList" border size="small" max-height="460">
        <el-table-column prop="name" label="服务名" min-width="200" show-overflow-tooltip />
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
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip>
          <template slot-scope="{ row }">
            <span style="font-size:11px;color:#606266">{{ row.description }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" align="center">
          <template slot-scope="{ row }">
            <el-button
              v-if="row.active_state !== 'active'"
              size="mini" type="text" style="color:#67c23a"
              @click="handleSystemdControl(row, 'start')"
            >启动</el-button>
            <el-button
              v-else
              size="mini" type="text" style="color:#e6a23c"
              @click="handleSystemdControl(row, 'stop')"
            >停止</el-button>
            <el-button
              v-if="row.active_state === 'active'"
              size="mini" type="text"
              @click="handleSystemdControl(row, 'restart')"
            >重启</el-button>
            <el-divider direction="vertical" />
            <el-button
              v-if="row.enabled !== 'enabled'"
              size="mini" type="text" style="color:#409eff"
              @click="handleSystemdControl(row, 'enable')"
            >自启</el-button>
            <el-button
              v-else
              size="mini" type="text" style="color:#f56c6c"
              @click="handleSystemdControl(row, 'disable')"
            >禁用</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top:8px;font-size:12px;color:#909399">
        共 {{ systemdList.length }} 个服务
      </div>
      <div slot="footer">
        <el-button size="small" :loading="systemdLoading" icon="el-icon-refresh" @click="openSystemdDialog(systemdServer)">刷新</el-button>
        <el-button @click="showSystemd = false">关闭</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getMdlServers, deleteMdlServer, getLabels, createLabel, deleteLabel } from '@/api/mdlServer'
import { getAuditLogs } from '@/api/configMgmt'
import ServerFormModal from './components/ServerFormModal'
import InitServerModal from './components/InitServerModal'
import BatchAddModal from './components/BatchAddModal'
import BatchInitModal from './components/BatchInitModal'

export default {
  name: 'ServerManagement',
  components: { ServerFormModal, InitServerModal, BatchAddModal, BatchInitModal },
  computed: {
    sortedServers() {
      if (!this.sortProp || !this.sortOrder) return this.servers
      const prop = this.sortProp
      const asc = this.sortOrder === 'ascending'
      return [...this.servers].sort((a, b) => {
        const av = (a[prop] || '').toString()
        const bv = (b[prop] || '').toString()
        return asc ? av.localeCompare(bv) : bv.localeCompare(av)
      })
    },
  },
  data() {
    return {
      loading: false,
      servers: [],
      total: 0,
      page: 1,
      pageSize: 20,
      searchQ: '',
      filterLabelId: null,
      searchTimer: null,
      showForm: false,
      showInit: false,
      showLabelMgr: false,
      showBatchAdd: false,
      showBatchInit: false,
      selectedRows: [],
      currentServer: null,
      sortProp: '',
      sortOrder: '',
      allLabels: [],
      newLabelName: '',
      // 自定义列
      colOptions: [
        { key: 'ip',            label: 'IP 地址' },
        { key: 'service_name',  label: '服务名' },
        { key: 'labels',        label: '标签' },
        { key: 'init_status',   label: '状态' },
        { key: 'install_dir',   label: '安装目录' },
        { key: 'backups_dir',   label: '备份目录' },
        { key: 'remote_python', label: 'Python 路径' },
      ],
      visibleCols: ['ip', 'service_name', 'labels', 'init_status', 'install_dir', 'backups_dir', 'remote_python'],
      // 操作日志
      showOpLog: false,
      opLogLoading: false,
      opLogs: [],
      opLogTotal: 0,
      opLogPage: 1,
      opLogPageSize: 20,
      opLogAction: '',
      opLogStatus: '',
      opLogKeyword: '',
      opLogSearchTimer: null,
      // 初始化日志详情
      showInitLogDialog: false,
      initLogTitle: '',
      initLogContent: '',
      // systemd 服务弹窗
      showSystemd: false,
      systemdServer: null,
      systemdLoading: false,
      systemdList: [],
    }
  },
  filters: {
    formatTime(val) {
      if (!val) return ''
      return val.replace('T', ' ').slice(0, 19)
    },
  },
  created() {
    this.fetchLabels()
    this.fetchServers()
  },
  methods: {
    async fetchLabels() {
      try {
        const res = await getLabels()
        const data = res.data
        this.allLabels = Array.isArray(data) ? data
          : (data && Array.isArray(data.results)) ? data.results : []
      } catch {}
    },

    async fetchServers() {
      this.loading = true
      try {
        const res = await getMdlServers({
          q: this.searchQ || undefined,
          label_id: this.filterLabelId || undefined,
          page: this.page,
          page_size: this.pageSize,
        })
        const data = res.data
        if (Array.isArray(data)) {
          this.servers = data
          this.total = data.length
        } else if (data && Array.isArray(data.results)) {
          this.servers = data.results
          this.total = data.count || data.results.length
        } else {
          this.servers = []
          this.total = 0
        }
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '加载失败'
        this.$message.error('加载服务器列表失败: ' + msg)
      } finally {
        this.loading = false
      }
    },

    handleSearch() {
      clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => {
        this.page = 1
        this.fetchServers()
      }, 400)
    },

    handleLabelFilter() {
      this.page = 1
      this.fetchServers()
    },

    handlePageChange(p) {
      this.page = p
      this.fetchServers()
    },

    handleSortChange({ prop, order }) {
      this.sortProp = prop || ''
      this.sortOrder = order || ''
    },
    handleSelectionChange(rows) {
      this.selectedRows = rows
    },
    handleBatchInit() {
      if (this.selectedRows.length === 0) return
      this.showBatchInit = true
    },
    handleAdd() {
      this.currentServer = null
      this.showForm = true
    },

    handleEdit(row) {
      this.currentServer = row
      this.showForm = true
    },

    handleInit(row) {
      this.currentServer = row
      this.showInit = true
    },

    async handleDelete(row) {
      try {
        await this.$confirm(
          `确认删除服务器 ${row.fqdn} (${row.ip})？`,
          '删除确认',
          { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
        )
      } catch { return }

      try {
        await deleteMdlServer(row.id)
        this.$message.success('删除成功')
        this.fetchServers()
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '删除失败'
        this.$message.error(msg)
      }
    },

    async handleCreateLabel() {
      const name = this.newLabelName.trim()
      if (!name) return
      try {
        await createLabel({ name })
        this.newLabelName = ''
        this.$message.success('标签创建成功')
        await this.fetchLabels()
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '创建失败'
        this.$message.error(msg)
      }
    },

    async handleDeleteLabel(row) {
      try {
        await this.$confirm(`确认删除标签「${row.name}」？`, '删除确认', {
          type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消'
        })
      } catch { return }
      try {
        await deleteLabel(row.id)
        this.$message.success('删除成功')
        await this.fetchLabels()
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '删除失败'
        this.$message.error(msg)
      }
    },

    handleInitAfterCreate(server) {
      if (!server) return
      this.currentServer = server
      this.showInit = true
    },

    handleConfigChange(row) {
      this.$router.push({ name: 'mdlConfigManagement', query: { ip: row.ip } })
    },

    handleRowCommand(cmd, row) {
      if (cmd === 'reinit') {
        this.$confirm(`确认对「${row.fqdn}」重新执行初始化？运行中的服务不会被停止，但目录和 systemd 配置会被覆盖。`, '重新初始化确认', {
          type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消'
        }).then(() => {
          this.handleInit(row)
        }).catch(() => {})
      } else if (cmd === 'services') {
        this.openSystemdDialog(row)
      }
    },

    async openSystemdDialog(row) {
      this.systemdServer = row
      this.showSystemd = true
      this.systemdLoading = true
      this.systemdList = []
      try {
        const { getSystemdServices } = await import('@/api/mdlServer')
        const res = await getSystemdServices(row.id)
        this.systemdList = (res.data && res.data.services) || []
      } catch (e) {
        this.$message.error('获取 systemd 服务列表失败：' + (e.message || ''))
      } finally {
        this.systemdLoading = false
      }
    },

    async handleSystemdControl(svc, action) {
      try {
        await this.$confirm(
          `确认对「${svc.name}」执行 ${action}？`,
          '确认操作',
          { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        const { controlSystemdService } = await import('@/api/mdlServer')
        const res = await controlSystemdService(this.systemdServer.id, { service: svc.name, action })
        if (res.data && res.data.ok) {
          this.$message.success(`${action} 成功`)
          // 刷新列表
          await this.openSystemdDialog(this.systemdServer)
        } else {
          this.$message.error(`${action} 失败：` + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('操作失败：' + (e.message || ''))
      }
    },

    openOpLog() {
      this.opLogPage = 1
      this.opLogAction = ''
      this.opLogStatus = ''
      this.opLogKeyword = ''
      this.showOpLog = true
    },

    async fetchOpLogs() {
      this.opLogLoading = true
      try {
        const res = await getAuditLogs({
          action: this.opLogAction || 'server_init,server_create,server_delete',
          status: this.opLogStatus || undefined,
          keyword: this.opLogKeyword || undefined,
          page: this.opLogPage,
          page_size: this.opLogPageSize,
        })
        const d = res.data && res.data.data ? res.data.data : res.data
        this.opLogs = d.items || []
        this.opLogTotal = d.total || 0
      } catch (e) {
        this.$message.error('加载操作日志失败')
      } finally {
        this.opLogLoading = false
      }
    },

    opLogSearch() {
      clearTimeout(this.opLogSearchTimer)
      this.opLogSearchTimer = setTimeout(() => {
        this.opLogPage = 1
        this.fetchOpLogs()
      }, 400)
    },

    async showInitLog(row) {
      this.initLogTitle = row.instance_names || ''
      this.initLogContent = '加载中...'
      this.showInitLogDialog = true
      try {
        const { getDeployTaskDetail } = await import('@/api/configMgmt')
        const res = await getDeployTaskDetail(row.deploy_task_id)
        const d = res.data && res.data.data ? res.data.data : res.data
        this.initLogContent = d.log || '（无日志）'
      } catch {
        this.initLogContent = '（日志加载失败）'
      }
    },

    initStatusLabel(s) {
      return { uninitialized: '未初始化', initializing: '初始化中', ready: '运行中', failed: '初始化失败', retired: '已退役' }[s] || s || '未知'
    },
    initStatusType(s) {
      return { uninitialized: 'info', initializing: 'warning', ready: 'success', failed: 'danger', retired: '' }[s] || 'info'
    },
  },
}
</script>

<style scoped>
.server-management {
  padding: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
.mono {
  font-family: monospace;
  font-size: 12px;
}
.empty-placeholder {
  text-align: center;
  padding: 40px 0;
}
.init-log {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
}
</style>
