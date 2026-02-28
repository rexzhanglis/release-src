<template>
  <div class="server-management">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchQ"
        placeholder="搜索 FQDN / IP / 服务名"
        clearable
        size="small"
        style="width:260px"
        prefix-icon="el-icon-search"
        @input="handleSearch"
      />
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
    >
      <el-table-column prop="fqdn" label="FQDN" min-width="160" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP 地址" width="140" />
      <el-table-column prop="service_name" label="服务名" width="140" />
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
      @success="fetchServers"
    />

    <!-- 初始化弹窗 -->
    <init-server-modal
      v-model="showInit"
      :server="currentServer"
    />
  </div>
</template>

<script>
import { getMdlServers, deleteMdlServer } from '@/api/mdlServer'
import ServerFormModal from './components/ServerFormModal'
import InitServerModal from './components/InitServerModal'

export default {
  name: 'ServerManagement',
  components: { ServerFormModal, InitServerModal },
  data() {
    return {
      loading: false,
      servers: [],
      total: 0,
      page: 1,
      pageSize: 20,
      searchQ: '',
      searchTimer: null,
      showForm: false,
      showInit: false,
      currentServer: null,
    }
  },
  created() {
    this.fetchServers()
  },
  methods: {
    async fetchServers() {
      this.loading = true
      try {
        const res = await getMdlServers({
          q: this.searchQ || undefined,
          page: this.page,
          page_size: this.pageSize,
        })
        // DRF 默认分页返回 {count, results}；若未配置分页则直接返回数组
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

    handlePageChange(p) {
      this.page = p
      this.fetchServers()
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
