<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="操作审计日志"
    width="1000px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <!-- 筛选条件 -->
    <el-form :inline="true" size="small" style="margin-bottom:12px">
      <el-form-item label="操作类型">
        <el-select v-model="filters.action" clearable placeholder="全部" style="width:130px" @change="handleSearch">
          <el-option label="保存配置"   value="save" />
          <el-option label="批量修改"   value="batch_update" />
          <el-option label="文本替换"   value="text_replace" />
          <el-option label="提交 Git"   value="git_commit" />
          <el-option label="推送 Consul" value="push_consul" />
          <el-option label="Ansible 部署" value="deploy" />
          <el-option label="同步 GitLab" value="sync" />
        </el-select>
      </el-form-item>
      <el-form-item label="操作人">
        <el-input v-model="filters.operator" clearable placeholder="操作人" style="width:120px" @change="handleSearch" />
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="yyyy-MM-dd"
          style="width:220px"
          @change="handleSearch"
        />
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" clearable placeholder="实例名/文件名/摘要" style="width:160px" @change="handleSearch" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="el-icon-search" @click="handleSearch">查询</el-button>
        <el-button icon="el-icon-refresh" @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 日志表格 -->
    <el-table
      v-loading="loading"
      :data="items"
      size="small"
      border
      style="width:100%"
      empty-text=" "
    >
      <el-table-column prop="created_time" label="时间" width="160">
        <template slot-scope="{ row }">
          {{ formatTime(row.created_time) }}
        </template>
      </el-table-column>
      <el-table-column prop="action_display" label="操作" width="100">
        <template slot-scope="{ row }">
          <el-tag :type="actionTagType(row.action)" size="mini">{{ row.action_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" label="操作人" width="110" />
      <el-table-column prop="status_display" label="结果" width="80" align="center">
        <template slot-scope="{ row }">
          <el-tag
            :type="row.status === 'success' ? 'success' : row.status === 'partial' ? 'warning' : 'danger'"
            size="mini"
          >{{ row.status_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="filename" label="配置文件" width="160" show-overflow-tooltip />
      <el-table-column prop="instance_names" label="实例" min-width="160" show-overflow-tooltip />
      <el-table-column prop="summary" label="摘要" min-width="220" show-overflow-tooltip />
      <el-table-column label="详情" width="70" align="center">
        <template slot-scope="{ row }">
          <el-button
            v-if="row.detail"
            size="mini" type="text" icon="el-icon-document"
            @click="showDetail(row)"
          >查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态 -->
    <div v-if="!loading && items.length === 0" class="empty-placeholder">
      <i class="el-icon-document" style="font-size:40px;color:#dcdfe6"></i>
      <p style="color:#909399;margin-top:8px;font-size:13px">暂无操作记录</p>
    </div>

    <!-- 分页 -->
    <div style="margin-top:12px;text-align:right">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog
      :visible.sync="detailVisible"
      :title="detailTitle"
      width="680px"
      append-to-body
    >
      <pre class="detail-pre">{{ detailText }}</pre>
      <template v-if="deployLog || deployLogLoading">
        <el-divider content-position="left" style="margin:16px 0 10px">
          <i class="el-icon-tickets"></i> 部署日志
        </el-divider>
        <div v-loading="deployLogLoading">
          <pre class="detail-pre deploy-log-pre">{{ deployLog }}</pre>
        </div>
      </template>
      <div slot="footer">
        <el-button size="small" @click="detailVisible = false">关闭</el-button>
      </div>
    </el-dialog>

    <div slot="footer" style="display:flex;justify-content:space-between;align-items:center">
      <el-button size="small" icon="el-icon-refresh" :loading="loading" @click="fetchLogs()">刷新</el-button>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </div>
  </el-dialog>
</template>

<script>
import { getAuditLogs, getDeployTaskDetail } from '@/api/configMgmt'

const ACTION_TAG_MAP = {
  save:         '',
  batch_update: 'warning',
  text_replace: 'warning',
  git_commit:   'success',
  push_consul:  'success',
  deploy:       'danger',
  sync:         'info',
}

export default {
  name: 'AuditLogModal',
  props: {
    value: { type: Boolean, default: false }
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) }
    }
  },
  data() {
    return {
      loading: false,
      items: [],
      total: 0,
      page: 1,
      pageSize: 50,
      filters: {
        action: '',
        operator: '',
        dateRange: null,
        keyword: ''
      },
      detailVisible: false,
      detailText: '',
      detailTitle: '详情',
      deployLog: '',
      deployLogLoading: false,
    }
  },
  methods: {
    handleOpen() {
      this.page = 1
      this.fetchLogs()
    },
    handleSearch() {
      this.page = 1
      this.fetchLogs()
    },
    handleReset() {
      this.filters = { action: '', operator: '', dateRange: null, keyword: '' }
      this.page = 1
      this.fetchLogs()
    },
    handlePageChange(p) {
      this.page = p
      this.fetchLogs()
    },
    async fetchLogs() {
      this.loading = true
      try {
        const params = {
          page: this.page,
          page_size: this.pageSize,
        }
        if (this.filters.action)   params.action   = this.filters.action
        if (this.filters.operator) params.operator = this.filters.operator
        if (this.filters.keyword)  params.keyword  = this.filters.keyword
        if (this.filters.dateRange && this.filters.dateRange.length === 2) {
          params.date_from = this.filters.dateRange[0]
          params.date_to   = this.filters.dateRange[1]
        }
        const res = await getAuditLogs(params)
        this.items = res.data.items || []
        this.total = res.data.total || 0
      } catch (e) {
        this.$message.error('获取审计日志失败')
      } finally {
        this.loading = false
      }
    },
    formatTime(t) {
      if (!t) return '-'
      try {
        return new Date(t).toLocaleString('zh-CN', { hour12: false })
      } catch {
        return t.replace('T', ' ').slice(0, 19)
      }
    },
    actionTagType(action) {
      return ACTION_TAG_MAP[action] || ''
    },
    async showDetail(row) {
      try {
        const obj = JSON.parse(row.detail)
        this.detailText = JSON.stringify(obj, null, 2)
      } catch (e) {
        this.detailText = row.detail
      }
      this.detailTitle = row.action === 'deploy' ? '部署详情' : '操作详情'
      this.deployLog = ''
      this.detailVisible = true

      // deploy 操作：额外加载部署日志
      if (row.action === 'deploy' && row.deploy_task_id) {
        this.deployLogLoading = true
        try {
          const res = await getDeployTaskDetail(row.deploy_task_id)
          this.deployLog = res.data.log || '（无日志）'
        } catch {
          this.deployLog = '加载部署日志失败'
        } finally {
          this.deployLogLoading = false
        }
      }
    }
  }
}
</script>

<style scoped>
.detail-pre {
  background: #f5f7fa;
  color: #303133;
  border: 1px solid #e4e7ed;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 420px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.empty-placeholder {
  text-align: center;
  padding: 32px 0 16px;
}

.deploy-log-pre {
  background: #1e1e1e;
  color: #d4d4d4;
  border-color: #3c3c3c;
  max-height: 280px;
}
</style>
