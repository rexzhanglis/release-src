<template>
  <el-drawer
    :visible.sync="drawerVisible"
    title="配置历史版本"
    direction="rtl"
    size="480px"
    :before-close="handleClose"
  >
    <div class="history-drawer-body">
      <!-- 当前文件信息 -->
      <div v-if="configPath" class="current-path">
        <i class="el-icon-document" style="color:#409eff"></i>
        <span>{{ configPath }}</span>
      </div>

      <div v-loading="loading" class="history-list">
        <div
          v-for="item in items"
          :key="item.id"
          class="history-item"
          :class="{ 'history-item--selected': selectedId === item.id }"
          @click="handleSelect(item)"
        >
          <div class="history-item-header">
            <el-tag :type="actionTagType(item.action)" size="mini">{{ actionLabel(item.action) }}</el-tag>
            <span class="history-time">{{ formatTime(item.created_time) }}</span>
          </div>
          <div class="history-item-meta">
            <i class="el-icon-user" style="color:#909399;font-size:12px"></i>
            <span class="history-operator">{{ item.operator }}</span>
            <span v-if="item.remark" class="history-remark">{{ item.remark }}</span>
          </div>
          <div class="history-item-actions" @click.stop>
            <el-button size="mini" type="text" @click="handlePreviewDiff(item)">
              <i class="el-icon-view"></i> 对比当前
            </el-button>
            <el-button size="mini" type="text" style="color:#f56c6c" @click="handleRollback(item)">
              <i class="el-icon-refresh-left"></i> 回滚
            </el-button>
          </div>
        </div>

        <div v-if="!loading && items.length === 0" class="empty-tip">
          <i class="el-icon-document" style="font-size:32px;color:#dcdfe6"></i>
          <p>暂无历史版本</p>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="history-pagination">
        <el-pagination
          small
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- Diff 对比弹窗 -->
    <el-dialog
      :visible.sync="diffVisible"
      title="版本对比（历史 vs 当前）"
      width="900px"
      append-to-body
      :close-on-click-modal="false"
    >
      <div ref="diffContainer" class="diff-editor-container"></div>
      <div slot="footer">
        <el-button @click="diffVisible = false">关闭</el-button>
        <el-button type="warning" @click="handleRollback(diffTargetItem)">
          <i class="el-icon-refresh-left"></i> 回滚到此版本
        </el-button>
      </div>
    </el-dialog>
  </el-drawer>
</template>

<script>
import * as monaco from 'monaco-editor'
import { getConfigHistory, getConfigHistoryDetail, rollbackConfig } from '@/api/configMgmt'

const ACTION_LABEL = {
  save: '保存',
  batch_update: '批量修改',
  text_replace: '文本替换',
  rollback: '回滚',
}
const ACTION_TAG = {
  save: '',
  batch_update: 'warning',
  text_replace: 'warning',
  rollback: 'danger',
}

export default {
  name: 'HistoryDrawer',
  props: {
    value: { type: Boolean, default: false },
    configId: { type: Number, default: null },
    configPath: { type: String, default: '' },
    currentContent: { type: String, default: '{}' },
  },
  computed: {
    drawerVisible: {
      get() { return this.value },
      set(v) { this.$emit('input', v) }
    }
  },
  data() {
    return {
      loading: false,
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
      selectedId: null,
      diffVisible: false,
      diffTargetItem: null,
      diffEditor: null,
    }
  },
  watch: {
    value(v) {
      if (v && this.configId) {
        this.page = 1
        this.fetchHistory()
      }
    },
    diffVisible(v) {
      if (!v && this.diffEditor) {
        this.diffEditor.dispose()
        this.diffEditor = null
      }
    }
  },
  methods: {
    handleClose() {
      this.drawerVisible = false
    },
    async fetchHistory() {
      this.loading = true
      try {
        const res = await getConfigHistory({
          config_id: this.configId,
          page: this.page,
          page_size: this.pageSize,
        })
        this.items = res.data.items || []
        this.total = res.data.total || 0
      } catch (e) {
        const msg = (e.response && e.response.data &&
          (e.response.data.message || e.response.data.detail)) || e.message || '未知错误'
        this.$message.error('加载历史记录失败: ' + msg)
      } finally {
        this.loading = false
      }
    },
    handlePageChange(p) {
      this.page = p
      this.fetchHistory()
    },
    handleSelect(item) {
      this.selectedId = item.id
    },
    async handlePreviewDiff(item) {
      this.diffTargetItem = item
      let historyContent = '{}'
      try {
        const res = await getConfigHistoryDetail(item.id)
        historyContent = JSON.stringify(res.data.content, null, 2)
      } catch (e) {
        this.$message.error('加载历史内容失败')
        return
      }
      this.diffVisible = true
      this.$nextTick(() => {
        if (this.$refs.diffContainer) {
          if (this.diffEditor) this.diffEditor.dispose()
          this.diffEditor = monaco.editor.createDiffEditor(this.$refs.diffContainer, {
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            renderSideBySide: true,
            automaticLayout: true,
          })
          this.diffEditor.setModel({
            original: monaco.editor.createModel(historyContent, 'json'),
            modified: monaco.editor.createModel(this.currentContent, 'json'),
          })
        }
      })
    },
    async handleRollback(item) {
      if (!item) return
      try {
        await this.$confirm(
          `确认回滚到 ${this.formatTime(item.created_time)} 的版本？当前内容将被覆盖（系统会先备份当前版本）。`,
          '确认回滚',
          { type: 'warning', confirmButtonText: '确认回滚', cancelButtonText: '取消' }
        )
      } catch { return }

      try {
        const res = await rollbackConfig(item.id)
        this.$message.success(res.data.message || '回滚成功')
        this.diffVisible = false
        this.$emit('rollback-success')
        this.fetchHistory()
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message
        this.$message.error('回滚失败: ' + msg)
      }
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t }
    },
    actionLabel(action) { return ACTION_LABEL[action] || action },
    actionTagType(action) { return ACTION_TAG[action] || '' },
  },
  beforeDestroy() {
    if (this.diffEditor) this.diffEditor.dispose()
  }
}
</script>

<style scoped>
.history-drawer-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 16px 16px;
  box-sizing: border-box;
}

.current-path {
  font-size: 12px;
  color: #606266;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 6px 10px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  word-break: break-all;
}

.history-list {
  flex: 1;
  overflow-y: auto;
}

.history-item {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.history-item:hover {
  border-color: #409eff;
  box-shadow: 0 1px 6px rgba(64,158,255,0.15);
}
.history-item--selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.history-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
}
.history-time {
  font-size: 12px;
  color: #909399;
}

.history-item-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}
.history-remark {
  color: #909399;
  font-size: 11px;
  background: #f5f7fa;
  border-radius: 3px;
  padding: 1px 5px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-item-actions {
  display: flex;
  gap: 4px;
}

.empty-tip {
  text-align: center;
  padding: 40px 0;
  color: #909399;
  font-size: 13px;
}

.history-pagination {
  padding-top: 10px;
  text-align: center;
}

.diff-editor-container {
  width: 100%;
  height: 500px;
}
</style>
