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
      :data="servers"
      border
      size="small"
      style="width:100%;margin-top:12px"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="40" />
      <el-table-column prop="fqdn" label="FQDN" min-width="160" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP 地址" width="140" />
      <el-table-column prop="service_name" label="服务名" width="140" />
      <el-table-column label="标签" width="160">
        <template slot-scope="{ row }">
          <el-tag
            v-for="lbl in (row.labels || [])"
            :key="lbl.id"
            size="mini"
            style="margin-right:4px;margin-bottom:2px"
          >{{ lbl.name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="install_dir" label="安装目录" min-width="160" show-overflow-tooltip>
        <template slot-scope="{ row }">
          <span class="mono">{{ row.install_dir }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="backups_dir" label="备份目录" min-width="140" show-overflow-tooltip>
        <template slot-scope="{ row }">
          <span class="mono">{{ row.backups_dir }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="remote_python" label="Python 路径" width="180" show-overflow-tooltip>
        <template slot-scope="{ row }">
          <span class="mono">{{ row.remote_python }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template slot-scope="{ row }">
          <el-button
            size="mini"
            type="text"
            icon="el-icon-edit"
            @click="handleEdit(row)"
          >编辑</el-button>
          <el-button
            size="mini"
            type="text"
            icon="el-icon-s-tools"
            style="color:#e6a23c"
            @click="handleInit(row)"
          >初始化</el-button>
          <el-button
            size="mini"
            type="text"
            icon="el-icon-delete"
            style="color:#f56c6c"
            @click="handleDelete(row)"
          >删除</el-button>
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
    />

    <!-- 初始化弹窗 -->
    <init-server-modal
      v-model="showInit"
      :server="currentServer"
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
  </div>
</template>

<script>
import { getMdlServers, deleteMdlServer, getLabels, createLabel, deleteLabel } from '@/api/mdlServer'
import ServerFormModal from './components/ServerFormModal'
import InitServerModal from './components/InitServerModal'
import BatchAddModal from './components/BatchAddModal'
import BatchInitModal from './components/BatchInitModal'

export default {
  name: 'ServerManagement',
  components: { ServerFormModal, InitServerModal, BatchAddModal, BatchInitModal },
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
      allLabels: [],
      newLabelName: '',
    }
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
</style>
