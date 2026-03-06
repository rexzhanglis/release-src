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
    </div>

    <!-- 物理机表格 -->
    <el-table
      v-loading="loading"
      :data="hosts"
      border
      size="small"
      style="width:100%;margin-top:12px"
      @sort-change="handleSortChange"
    >
      <el-table-column prop="fqdn" label="FQDN" min-width="180" show-overflow-tooltip sortable="custom">
        <template slot-scope="{ row }">
          <router-link
            :to="{ name: 'mdlServerDetail', params: { id: row.id }, query: { type: 'host' } }"
            style="color:#409eff;text-decoration:none"
          >
            {{ row.fqdn }}
          </router-link>
        </template>
      </el-table-column>
      <el-table-column prop="ip" label="IP 地址" width="140" sortable="custom" />
      <el-table-column prop="user" label="SSH 用户" width="100" />
      <el-table-column label="服务实例数" width="100" align="center">
        <template slot-scope="{ row }">
          <el-badge :value="row.service_count || 0" type="primary" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="155">
        <template slot-scope="{ row }">{{ row.created_time | formatTime }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template slot-scope="{ row }">
          <el-button size="mini" type="text" icon="el-icon-edit" @click.stop="handleEdit(row)">编辑</el-button>
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
  </div>
</template>

<script>
import { getHosts, deleteHost, getLabels, createLabel, deleteLabel } from '@/api/mdlServer'
import HostFormModal from './components/HostFormModal'

export default {
  name: 'ServerManagement',
  components: { HostFormModal },
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
    }
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
  gap: 8px;
}
.empty-placeholder {
  text-align: center;
  padding: 40px 0;
}
</style>
