<template>
  <div class="server-management">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="搜索 FQDN / IP"
        clearable
        size="small"
        style="width:220px"
        prefix-icon="el-icon-search"
        @input="handleSearch"
      />
      <el-select
        v-model="filterLabelId"
        placeholder="按标签过滤"
        clearable
        size="small"
        style="width:150px;margin-left:8px"
        @change="handleLabelFilter"
      >
        <el-option
          v-for="label in allLabels"
          :key="label.id"
          :label="label.name"
          :value="label.id"
        />
      </el-select>
      <el-button
        type="primary"
        size="small"
        icon="el-icon-plus"
        style="margin-left:12px"
        @click="handleAdd"
      >
        新增机器
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
        icon="el-icon-refresh"
        :loading="loading"
        @click="fetchHosts"
      >
        刷新
      </el-button>
      <el-button
        v-if="checkedHosts.length > 0"
        size="small"
        type="warning"
        icon="el-icon-refresh"
        style="margin-left:8px"
        @click="showBatchRestart = true"
      >
        批量重启（{{ checkedHosts.length }} 台）
      </el-button>

      <!-- 列选择器 -->
      <el-popover
        placement="bottom-end"
        width="200"
        trigger="click"
        style="margin-left:auto"
      >
        <div>
          <div style="font-size:12px;color:#909399;margin-bottom:8px;font-weight:600">显示列（拖拽可排序）</div>
          <div
            v-for="col in columnDefs"
            :key="col.key"
            class="col-item"
            draggable="true"
            @dragstart="dragStart(col)"
            @dragover.prevent="dragOver(col)"
            @drop="dragDrop(col)"
            @dragend="dragEnd"
          >
            <i class="el-icon-rank col-drag-handle" />
            <el-checkbox v-model="col.visible" :disabled="col.fixed">{{ col.label }}</el-checkbox>
          </div>
        </div>
        <el-button slot="reference" size="small" icon="el-icon-set-up">列设置</el-button>
      </el-popover>
    </div>

    <!-- 物理机表格 -->
    <el-table
      v-loading="loading"
      :data="hosts"
      border
      size="small"
      style="width:100%;margin-top:12px"
      @sort-change="handleSortChange"
      @selection-change="checkedHosts = $event"
      @row-click="handleRowClick"
    >
      <el-table-column type="selection" width="40" />
      <template v-for="col in visibleColumns">
        <el-table-column
          v-if="col.key === 'fqdn'"
          :key="col.key"
          prop="fqdn"
          label="FQDN"
          min-width="180"
          show-overflow-tooltip
          sortable="custom"
        >
          <template slot-scope="{ row }">
            <router-link
              :to="{ name: 'mdlServerDetail', params: { id: row.id }, query: { type: 'host' } }"
              style="color:#409eff;text-decoration:none"
              @click.native.stop
            >
              {{ row.fqdn }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column
          v-else-if="col.key === 'ip'"
          :key="col.key"
          prop="ip"
          label="IP 地址"
          width="140"
          sortable="custom"
        />
        <el-table-column
          v-else-if="col.key === 'user'"
          :key="col.key"
          prop="user"
          label="SSH 用户"
          width="100"
        />
        <el-table-column
          v-else-if="col.key === 'remote_python'"
          :key="col.key"
          prop="remote_python"
          label="远端 Python"
          min-width="160"
          show-overflow-tooltip
        />
        <el-table-column
          v-else-if="col.key === 'service_count'"
          :key="col.key"
          label="服务实例数"
          width="100"
          align="center"
        >
          <template slot-scope="{ row }">
            <el-badge :value="row.service_count || 0" type="primary" />
          </template>
        </el-table-column>
        <el-table-column
          v-else-if="col.key === 'created_time'"
          :key="col.key"
          label="创建时间"
          width="155"
        >
          <template slot-scope="{ row }">{{ row.created_time | formatTime }}</template>
        </el-table-column>
      </template>
      <el-table-column label="操作" width="280" align="center" fixed="right">
        <template slot-scope="{ row }">
          <el-button size="mini" type="text" icon="el-icon-view" @click.stop="handleViewDetail(row)">详情</el-button>
          <el-button size="mini" type="text" icon="el-icon-edit" @click.stop="handleEdit(row)">编辑</el-button>
          <el-button
            v-if="row.init_status !== 'ready'"
            size="mini" type="text" icon="el-icon-setting" style="color:#e6a23c"
            @click.stop="handleInitHost(row)"
          >初始化</el-button>
          <el-button
            size="mini" type="text" icon="el-icon-s-grid" style="color:#409eff"
            @click.stop="$router.push({ name: 'mdlServerDetail', params: { id: row.id }, query: { type: 'host' } })"
          >管理服务</el-button>
          <el-button size="mini" type="text" icon="el-icon-delete" style="color:#f56c6c" @click.stop="handleDelete(row)">删除</el-button>
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
    <div v-if="!loading && hosts.length === 0" class="empty-placeholder">
      <i class="el-icon-monitor" style="font-size:40px;color:#dcdfe6"></i>
      <p style="color:#909399;margin-top:8px;font-size:13px">暂无机器记录，点击「新增机器」开始</p>
    </div>

    <!-- 新增/编辑机器弹窗 -->
    <host-form-modal
      v-model="showForm"
      :host="currentHost"
      @success="fetchHosts"
    />

    <!-- 初始化机器弹窗 -->
    <host-init-modal
      v-model="showInitModal"
      :host="initTargetHost"
      @done="fetchHosts"
    />

    <!-- 详情弹窗 -->
    <el-dialog
      title="机器详情"
      :visible.sync="showDetail"
      width="520px"
      :close-on-click-modal="false"
    >
      <template v-if="detailHost">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="FQDN">{{ detailHost.fqdn }}</el-descriptions-item>
          <el-descriptions-item label="IP 地址">{{ detailHost.ip }}</el-descriptions-item>
          <el-descriptions-item label="SSH 用户">{{ detailHost.user }}</el-descriptions-item>
          <el-descriptions-item label="远端 Python">{{ detailHost.remote_python }}</el-descriptions-item>
          <el-descriptions-item label="服务实例数">{{ detailHost.service_count || 0 }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detailHost.created_time | formatTime }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ detailHost.updated_time | formatTime }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailHost.services && detailHost.services.length" style="margin-top:16px">
          <div style="font-size:13px;font-weight:600;color:#303133;margin-bottom:8px">服务实例列表</div>
          <el-table :data="detailHost.services" size="mini" border>
            <el-table-column prop="service_name" label="服务名" min-width="120" show-overflow-tooltip />
            <el-table-column prop="install_dir" label="安装目录" min-width="140" show-overflow-tooltip />
            <el-table-column prop="init_status" label="初始化状态" width="90" align="center">
              <template slot-scope="{ row }">
                <el-tag
                  :type="row.init_status === 'success' ? 'success' : row.init_status === 'failed' ? 'danger' : 'info'"
                  size="mini" effect="plain"
                >{{ row.init_status || '-' }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
      <div slot="footer">
        <el-button size="small" @click="showDetail = false">关闭</el-button>
        <el-button size="small" type="primary" @click="handleEditFromDetail">编辑</el-button>
        <el-button
          size="small"
          type="success"
          icon="el-icon-s-grid"
          @click="goManageServices"
        >管理服务</el-button>
      </div>
    </el-dialog>

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
              size="mini" type="text" style="color:#f56c6c" icon="el-icon-delete"
              @click="handleDeleteLabel(row)"
            />
          </template>
        </el-table-column>
      </el-table>
      <div slot="footer">
        <el-button @click="showLabelMgr = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- 跨机器批量重启弹窗 -->
    <el-dialog
      title="跨机器批量重启"
      :visible.sync="showBatchRestart"
      width="700px"
      :close-on-click-modal="false"
      @close="resetBatchRestart"
    >
      <!-- 第一阶段：输入前缀，查询服务 -->
      <template v-if="batchRestartStep === 'query'">
        <div style="margin-bottom:12px;font-size:13px;color:#606266">
          已选中 <strong>{{ checkedHosts.length }}</strong> 台机器，输入前缀后查询各机器上的服务，再选择需要重启的服务。
        </div>
        <el-form label-width="100px" size="small">
          <el-form-item label="服务名前缀">
            <el-input v-model="batchRestartPattern" placeholder="如 mdl-" style="width:240px" />
            <div style="font-size:11px;color:#909399;margin-top:4px">匹配每台机器上以此前缀开头的所有 systemd 服务</div>
          </el-form-item>
        </el-form>
        <div style="background:#f5f7fa;border-radius:4px;padding:8px 12px;font-size:12px;color:#909399">
          <div v-for="h in checkedHosts" :key="h.id">{{ h.fqdn }} ({{ h.ip }})</div>
        </div>
      </template>

      <!-- 第二阶段：展示服务列表，用户勾选 -->
      <template v-else-if="batchRestartStep === 'select'">
        <div style="margin-bottom:10px;font-size:13px;color:#606266">
          请勾选每台机器上需要重启的服务，然后点击「确认重启」。
        </div>
        <div
          v-for="item in batchServiceList"
          :key="item.host_id"
          style="margin-bottom:14px;border:1px solid #ebeef5;border-radius:4px;overflow:hidden"
        >
          <div style="background:#f5f7fa;padding:6px 12px;font-size:12px;font-weight:600;color:#303133;display:flex;align-items:center;justify-content:space-between">
            <span>{{ item.fqdn }} <span style="color:#909399;font-weight:400">({{ item.ip }})</span></span>
            <span v-if="!item.ok" style="color:#f56c6c;font-size:11px">{{ item.error }}</span>
            <el-checkbox
              v-else
              :indeterminate="batchSelectedServices[item.host_id] && batchSelectedServices[item.host_id].length > 0 && batchSelectedServices[item.host_id].length < item.services.length"
              :value="batchSelectedServices[item.host_id] && batchSelectedServices[item.host_id].length === item.services.length"
              @change="val => toggleAllServices(item, val)"
              style="margin-left:auto"
            >全选</el-checkbox>
          </div>
          <div v-if="item.ok && item.services.length" style="padding:8px 12px">
            <el-checkbox-group :value="batchSelectedServices[item.host_id] || []" @input="val => setHostServices(item.host_id, val)">
              <el-checkbox
                v-for="svc in item.services"
                :key="svc"
                :label="svc"
                style="display:block;margin:2px 0;font-family:monospace;font-size:12px"
              >{{ svc }}</el-checkbox>
            </el-checkbox-group>
          </div>
          <div v-else-if="item.ok" style="padding:8px 12px;font-size:12px;color:#909399">无匹配服务</div>
        </div>
        <div style="margin-top:4px;padding:8px 4px;border-top:1px solid #ebeef5">
          <el-checkbox v-model="batchRestartConsulPull" size="small">重启前先执行 consul_pull.py 拉取最新配置</el-checkbox>
        </div>
      </template>

      <!-- 第三阶段：执行结果 -->
      <template v-else-if="batchRestartStep === 'result'">
        <div style="margin-bottom:8px;font-size:13px">
          完成：{{ batchRestartResult.ok_count }}/{{ batchRestartResult.total }} 台成功
        </div>
        <el-table :data="batchRestartResult.results" size="mini" border max-height="380">
          <el-table-column prop="fqdn" label="机器" min-width="140" show-overflow-tooltip />
          <el-table-column prop="ip" label="IP" width="130" />
          <el-table-column label="重启服务" min-width="180" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span style="font-family:monospace;font-size:11px">{{ (row.matched || []).join(', ') || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="结果" width="70" align="center">
            <template slot-scope="{ row }">
              <el-tag :type="row.ok ? 'success' : 'danger'" size="mini" effect="plain">{{ row.ok ? '成功' : '失败' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="详情" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span style="font-size:11px;color:#909399">{{ row.output || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <span slot="footer">
        <!-- query 阶段 -->
        <template v-if="batchRestartStep === 'query'">
          <el-button size="small" @click="showBatchRestart = false">取消</el-button>
          <el-button
            size="small" type="primary"
            :loading="batchListLoading"
            :disabled="!batchRestartPattern"
            @click="handleQueryServices"
          >查询服务</el-button>
        </template>
        <!-- select 阶段 -->
        <template v-else-if="batchRestartStep === 'select'">
          <el-button size="small" @click="batchRestartStep = 'query'">返回</el-button>
          <el-button
            size="small" type="warning"
            :loading="batchRestartLoading"
            :disabled="!hasSelectedServices"
            @click="handleBatchRestart"
          >确认重启</el-button>
        </template>
        <!-- result 阶段 -->
        <template v-else>
          <el-button size="small" @click="showBatchRestart = false">关闭</el-button>
        </template>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { getHosts, deleteHost, getLabels, createLabel, deleteLabel, batchListServices, batchRestartHosts } from '@/api/mdlServer'
import HostFormModal from './components/HostFormModal'
import HostInitModal from './components/HostInitModal'

const DEFAULT_COLUMNS = [
  { key: 'fqdn', label: 'FQDN', visible: true, fixed: true },
  { key: 'ip', label: 'IP 地址', visible: true, fixed: false },
  { key: 'user', label: 'SSH 用户', visible: true, fixed: false },
  { key: 'remote_python', label: '远端 Python', visible: false, fixed: false },
  { key: 'service_count', label: '服务实例数', visible: true, fixed: false },
  { key: 'created_time', label: '创建时间', visible: true, fixed: false },
]

const STORAGE_KEY = 'serverMgmt_columns'

function loadColumns() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (Array.isArray(saved) && saved.length === DEFAULT_COLUMNS.length) {
      return saved.map((s, i) => ({ ...DEFAULT_COLUMNS.find(d => d.key === s.key) || DEFAULT_COLUMNS[i], visible: s.visible }))
    }
  } catch {}
  return DEFAULT_COLUMNS.map(c => ({ ...c }))
}

export default {
  name: 'ServerManagement',
  components: { HostFormModal, HostInitModal },
  filters: {
    formatTime(val) {
      if (!val) return ''
      return val.replace('T', ' ').slice(0, 19)
    },
  },
  data() {
    return {
      loading: false,
      hosts: [],
      total: 0,
      page: 1,
      pageSize: 20,
      searchQ: '',
      filterLabelId: '',
      searchTimer: null,
      showForm: false,
      currentHost: null,
      showLabelMgr: false,
      allLabels: [],
      newLabelName: '',
      checkedHosts: [],
      showBatchRestart: false,
      batchRestartPattern: 'mdl-',
      batchRestartConsulPull: false,
      batchRestartLoading: false,
      batchRestartResult: null,
      // 三阶段：query（输入前缀）→ select（选择服务）→ result（执行结果）
      batchRestartStep: 'query',
      batchServiceList: [],     // [{host_id, fqdn, ip, services:[...], ok, error}]
      batchSelectedServices: {}, // {host_id: [checked_service, ...]}
      batchListLoading: false,
      // 详情弹窗
      showDetail: false,
      detailHost: null,
      // 初始化弹窗
      showInitModal: false,
      initTargetHost: null,
      // 列管理
      columnDefs: loadColumns(),
      dragSrcKey: null,
    }
  },
  computed: {
    visibleColumns() {
      return this.columnDefs.filter(c => c.visible)
    },
    hasSelectedServices() {
      return Object.values(this.batchSelectedServices).some(svcs => svcs && svcs.length > 0)
    },
  },
  watch: {
    columnDefs: {
      deep: true,
      handler(val) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(val.map(c => ({ key: c.key, visible: c.visible }))))
      },
    },
  },
  created() {
    this.fetchHosts()
    this.fetchLabels()
  },
  methods: {
    async fetchHosts() {
      this.loading = true
      try {
        const res = await getHosts({
          q: this.searchQ || undefined,
          label_id: this.filterLabelId || undefined,
          page: this.page,
          page_size: this.pageSize,
        })
        const data = res.data
        if (Array.isArray(data)) {
          this.hosts = data
          this.total = data.length
        } else if (data && Array.isArray(data.results)) {
          this.hosts = data.results
          this.total = data.count || data.results.length
        } else {
          this.hosts = []
          this.total = 0
        }
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '加载失败'
        this.$message.error('加载机器列表失败: ' + msg)
      } finally {
        this.loading = false
      }
    },

    handleSearch() {
      clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => {
        this.page = 1
        this.fetchHosts()
      }, 400)
    },

    handleLabelFilter() {
      this.page = 1
      this.fetchHosts()
    },

    handlePageChange(p) {
      this.page = p
      this.fetchHosts()
    },

    handleSortChange({ prop, order }) {
      this.sortProp = prop || ''
      this.sortOrder = order || ''
    },

    handleAdd() {
      this.currentHost = null
      this.showForm = true
    },

    handleEdit(row) {
      this.currentHost = row
      this.showForm = true
    },

    handleViewDetail(row) {
      this.detailHost = row
      this.showDetail = true
    },

    handleRowClick(row) {
      this.handleViewDetail(row)
    },

    handleEditFromDetail() {
      this.showDetail = false
      this.currentHost = this.detailHost
      this.showForm = true
    },

    goManageServices() {
      if (!this.detailHost) return
      this.showDetail = false
      this.$router.push({ name: 'mdlServerDetail', params: { id: this.detailHost.id }, query: { type: 'host' } })
    },

    handleInitHost(row) {
      this.initTargetHost = row
      this.showInitModal = true
    },

    async handleDelete(row) {
      try {
        await this.$confirm(
          `确认删除机器 ${row.fqdn} (${row.ip})？删除前请确保该机器下无服务实例。`,
          '删除确认',
          { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        await deleteHost(row.id)
        this.$message.success('删除成功')
        this.fetchHosts()
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '删除失败'
        this.$message.error(msg)
      }
    },

    async fetchLabels() {
      try {
        const res = await getLabels()
        const data = res.data
        this.allLabels = Array.isArray(data) ? data
          : (data && Array.isArray(data.results)) ? data.results : []
      } catch {}
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

    resetBatchRestart() {
      this.batchRestartStep = 'query'
      this.batchServiceList = []
      this.batchSelectedServices = {}
      this.batchRestartResult = null
    },

    async handleQueryServices() {
      if (!this.batchRestartPattern) return
      this.batchListLoading = true
      try {
        const res = await batchListServices({
          host_ids: this.checkedHosts.map(h => h.id),
          service_pattern: this.batchRestartPattern,
        })
        this.batchServiceList = res.data.results || []
        // 默认全选所有服务
        const selected = {}
        this.batchServiceList.forEach(item => {
          selected[item.host_id] = [...(item.services || [])]
        })
        this.batchSelectedServices = selected
        this.batchRestartStep = 'select'
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '查询失败'
        this.$message.error(msg)
      } finally {
        this.batchListLoading = false
      }
    },

    toggleAllServices(item, val) {
      this.$set(this.batchSelectedServices, item.host_id, val ? [...item.services] : [])
    },

    setHostServices(hostId, val) {
      this.$set(this.batchSelectedServices, hostId, val)
    },

    async handleBatchRestart() {
      this.batchRestartLoading = true
      try {
        // 构建 per_host_services，只传用户勾选的服务
        const perHostServices = {}
        Object.entries(this.batchSelectedServices).forEach(([hostId, svcs]) => {
          if (svcs && svcs.length) perHostServices[hostId] = svcs
        })
        const res = await batchRestartHosts({
          host_ids: this.checkedHosts.map(h => h.id),
          per_host_services: perHostServices,
          consul_pull: this.batchRestartConsulPull,
        })
        this.batchRestartResult = res.data
        this.batchRestartStep = 'result'
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '操作失败'
        this.$message.error(msg)
      } finally {
        this.batchRestartLoading = false
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

    // 列拖拽排序
    dragStart(col) {
      this.dragSrcKey = col.key
    },
    dragOver(col) {
      if (col.key === this.dragSrcKey) return
      const cols = this.columnDefs
      const srcIdx = cols.findIndex(c => c.key === this.dragSrcKey)
      const dstIdx = cols.findIndex(c => c.key === col.key)
      if (srcIdx === -1 || dstIdx === -1) return
      const moved = cols.splice(srcIdx, 1)[0]
      cols.splice(dstIdx, 0, moved)
    },
    dragEnd() {
      this.dragSrcKey = null
    },
    dragDrop() {},
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
  gap: 8px;
}
.empty-placeholder {
  text-align: center;
  padding: 40px 0;
}
.col-item {
  display: flex;
  align-items: center;
  padding: 4px 0;
  cursor: grab;
  border-radius: 4px;
  transition: background 0.15s;
}
.col-item:hover {
  background: #f5f7fa;
}
.col-drag-handle {
  color: #c0c4cc;
  margin-right: 6px;
  font-size: 14px;
  cursor: grab;
}
</style>
