<template>
  <div class="config-mgmt-layout">
    <!-- 顶部操作栏 -->
    <div class="top-bar">
      <h3 class="page-title">MDL 配置管理</h3>
      <div class="actions">
        <el-tooltip v-if="!canOperate" content="只读角色，无编辑权限" placement="bottom">
          <el-tag type="info" style="margin-right:8px;cursor:default">
            <i class="el-icon-view"></i> 只读模式
          </el-tag>
        </el-tooltip>
        <el-button type="primary" :loading="syncing" :disabled="!canOperate" @click="handleSync">
          <i class="el-icon-refresh"></i> 同步
        </el-button>
        <el-button type="warning" :disabled="!hasChecked || !canOperate" @click="showBatchEdit = true">
          <i class="el-icon-edit"></i> 批量修改
        </el-button>
        <el-button type="success" :disabled="!hasChecked || !canOperate" @click="handleGitCommit">
          <i class="el-icon-upload2"></i> 提交 Git
        </el-button>
        <el-button type="info" :disabled="!hasChecked || !canOperate" @click="handlePushConsul">
          <i class="el-icon-connection"></i> 推送 Consul
        </el-button>
        <el-button type="danger" :disabled="!hasCheckedInstances || !canDeploy" @click="showDeploy = true">
          <i class="el-icon-video-play"></i> 部署
        </el-button>
        <el-button @click="showAuditLog = true">
          <i class="el-icon-notebook-2"></i> 操作日志
        </el-button>
        <el-button @click="showConsistency = true">
          <i class="el-icon-warning-outline"></i> 一致性巡检
        </el-button>
      </div>
    </div>

    <div class="content">
      <!-- 左侧配置树 -->
      <div class="tree-panel">
        <div class="tree-header">
          <el-input
            v-model="searchText"
            placeholder="搜索实例..."
            clearable
            size="small"
            prefix-icon="el-icon-search"
            @input="handleSearch"
            @clear="handleSearch"
          />
          <el-button
            v-if="canOperate"
            size="mini"
            type="primary"
            icon="el-icon-plus"
            style="width:100%;margin-top:8px"
            @click="showAddInstance = true"
          >新增实例</el-button>
        </div>
        <div v-loading="treeLoading" class="tree-body">
          <el-tree
            ref="configTree"
            :data="treeData"
            :props="{ label: 'label', children: 'children' }"
            node-key="id"
            show-checkbox
            default-expand-all
            :expand-on-click-node="false"
            @check="handleCheck"
            @node-click="handleNodeClick"
          >
            <span slot-scope="{ node, data }" class="tree-node-content">
              <i v-if="data.type === 'service_type'" class="el-icon-folder-opened tree-icon"></i>
              <i v-else-if="data.type === 'instance'" class="el-icon-monitor tree-icon"></i>
              <i v-else class="el-icon-document tree-icon"></i>
              <span class="node-text">{{ node.label }}</span>
              <el-tag
                v-if="data.type === 'instance' && data.data && data.data.host_ip"
                size="mini"
                type="info"
                style="margin-left:4px"
              >
                {{ data.data.host_ip }}
              </el-tag>
            </span>
          </el-tree>
        </div>
      </div>

      <!-- 右侧编辑区 -->
      <div class="editor-panel">
        <div v-if="currentConfig" class="editor-header">
          <span class="editor-path">{{ currentConfigPath }}</span>
          <el-button size="small" :disabled="!currentConfig" @click="showHistory = true">
            <i class="el-icon-time"></i> 历史
          </el-button>
          <el-button type="primary" size="small" :disabled="!canOperate" @click="handleSave">
            <i class="el-icon-check"></i> 保存
          </el-button>
        </div>
        <div class="editor-body">
          <config-editor
            v-if="currentConfig"
            :content="editorContent"
            @change="handleEditorChange"
            @save="handleSave"
          />
          <div v-else class="editor-placeholder">
            <i class="el-icon-document" style="font-size:48px;color:#dcdfe6"></i>
            <p style="color:#909399;margin-top:12px">从左侧树中选择一个配置文件</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增实例弹窗 -->
    <add-instance-modal
      v-model="showAddInstance"
      @success="refreshTree"
    />

    <!-- 批量修改弹窗 -->
    <batch-edit-modal
      v-model="showBatchEdit"
      :checked-instance-ids="checkedInstanceIds"
      :checked-instances="checkedInstances"
      @success="refreshTree"
    />

    <!-- 部署弹窗 -->
    <deploy-modal
      v-model="showDeploy"
      :instance-ids="checkedInstanceIds"
      @success="refreshTree"
    />

    <!-- 审计日志弹窗 -->
    <audit-log-modal v-model="showAuditLog" />

    <!-- 历史版本抽屉 -->
    <history-drawer
      v-model="showHistory"
      :config-id="currentConfig && currentConfig.id"
      :config-path="currentConfigPath"
      :current-content="editorContent"
      @rollback-success="handleRollbackSuccess"
    />

    <!-- 一致性巡检弹窗 -->
    <consistency-modal v-model="showConsistency" />
  </div>
</template>

<script>
import { getConfigTree, getConfigDetail, updateConfig, syncFromGitlab, gitCommit, pushConsul } from '@/api/configMgmt'
import ConfigEditor from './components/ConfigEditor'
import AddInstanceModal from './components/AddInstanceModal'
import BatchEditModal from './components/BatchEditModal'
import DeployModal from './components/DeployModal'
import AuditLogModal from './components/AuditLogModal'
import HistoryDrawer from './components/HistoryDrawer'
import ConsistencyModal from './components/ConsistencyModal'

export default {
  name: 'MdlConfigManagement',
  components: {
    ConfigEditor,
    AddInstanceModal,
    BatchEditModal,
    DeployModal,
    AuditLogModal,
    HistoryDrawer,
    ConsistencyModal,
  },
  data() {
    return {
      treeLoading: false,
      treeData: [],
      searchText: '',
      searchTimer: null,

      syncing: false,

      // 当前编辑的配置
      currentConfig: null,
      currentConfigPath: '',
      editorContent: '',
      isDirty: false,

      // 选中状态
      checkedConfigIds: [],
      checkedConfigLabels: [],
      checkedInstanceIds: [],
      checkedInstances: [],

      // 弹窗控制
      showAddInstance: false,
      showBatchEdit: false,
      showDeploy: false,
      showAuditLog: false,
      showHistory: false,
      showConsistency: false,
    }
  },
  computed: {
    hasChecked() {
      return this.checkedConfigIds.length > 0
    },
    hasCheckedInstances() {
      return this.checkedInstanceIds.length > 0
    },
    canOperate() {
      const role = this.$store.state.user.configRole
      return role === 'config_admin' || role === 'config_operator'
    },
    canDeploy() {
      return this.$store.state.user.configRole === 'config_admin'
    }
  },
  created() {
    this.fetchTree()
  },
  methods: {
    // 统一提取后端错误信息
    getErrMsg(e, fallback) {
      return (e.response && e.response.data &&
        (e.response.data.message || e.response.data.error)) ||
        e.message || fallback
    },

    async fetchTree(search) {
      this.treeLoading = true
      try {
        const params = {}
        if (search) params.search = search
        const res = await getConfigTree(params)
        this.treeData = res.data
      } catch (e) {
        this.$message.error('加载配置树失败: ' + this.getErrMsg(e, '未知错误'))
      } finally {
        this.treeLoading = false
      }
    },

    handleSearch() {
      clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => {
        this.fetchTree(this.searchText)
      }, 300)
    },

    handleCheck() {
      const checked = this.$refs.configTree.getCheckedNodes(false, false)
      const configNodes = checked.filter(n => n.type === 'config')
      this.checkedConfigIds = configNodes.map(n => n.data.config_id)
      this.checkedConfigLabels = configNodes.map(n => n.label)

      const instanceMap = {}
      checked.filter(n => n.type === 'instance').forEach(n => {
        instanceMap[n.data.id] = {
          id: n.data.id,
          name: n.label,
          host_ip: n.data.host_ip || '',
          service_name: n.data.service_name || ''
        }
      })
      this.checkedInstanceIds = Object.keys(instanceMap).map(Number)
      this.checkedInstances = Object.values(instanceMap)
    },

    async handleNodeClick(data) {
      if (data.type !== 'config') return

      // 有未保存修改时询问用户
      if (this.isDirty) {
        try {
          await this.$confirm('当前有未保存的修改，切换后将丢失，确认继续？', '提示', {
            type: 'warning',
            confirmButtonText: '继续切换',
            cancelButtonText: '取消'
          })
        } catch {
          return
        }
      }

      try {
        const res = await getConfigDetail(data.data.config_id)
        const config = res.data
        this.currentConfig = config
        this.currentConfigPath = `${config.service_type_name}/${config.instance_name}/${config.filename}`
        this.editorContent = JSON.stringify(config.content, null, 2)
        this.isDirty = false
      } catch (e) {
        this.$message.error('加载配置失败: ' + this.getErrMsg(e, '未知错误'))
      }
    },

    handleEditorChange(value) {
      this.editorContent = value
      this.isDirty = true
    },

    async handleSave() {
      try {
        const content = JSON.parse(this.editorContent)
        // 同时传 raw_content，让后端保留编辑器原始格式（缩进、换行）
        await updateConfig(this.currentConfig.id, { content, raw_content: this.editorContent })
        this.$message.success('保存成功')
        this.isDirty = false
      } catch (e) {
        if (e instanceof SyntaxError) {
          this.$message.error('JSON 格式错误，请检查后重试')
        } else {
          this.$message.error('保存失败: ' + this.getErrMsg(e, '未知错误'))
        }
      }
    },

    async handleSync() {
      this.syncing = true
      try {
        const res = await syncFromGitlab()
        this.$message.success(res.data.message || '同步完成')
        await this.fetchTree()
      } catch (e) {
        this.$message.error('同步失败: ' + this.getErrMsg(e, '未知错误'))
      } finally {
        this.syncing = false
      }
    },

    handleGitCommit() {
      if (!this.checkedConfigIds.length) {
        this.$message.warning('请先勾选要提交的配置文件')
        return
      }
      const fileList = [...new Set(this.checkedConfigLabels)].join(', ')
      this.$prompt('请输入提交信息', '提交到 GitLab', {
        inputValue: `Update configs: ${fileList}`,
        confirmButtonText: '提交',
        cancelButtonText: '取消'
      }).then(async ({ value }) => {
        try {
          const res = await gitCommit({
            config_ids: this.checkedConfigIds,
            message: value
          })
          const allOk = res.data.results && res.data.results.every(r => r.status === 'ok')
          this.$notify({
            title: '提交结果',
            message: res.data.message || '提交完成',
            type: allOk ? 'success' : 'warning',
            duration: 5000
          })
        } catch (e) {
          this.$message.error('提交失败: ' + this.getErrMsg(e, '未知错误'))
        }
      }).catch(() => {})
    },

    handlePushConsul() {
      if (!this.checkedConfigIds.length) {
        this.$message.warning('请先勾选要推送的配置文件')
        return
      }
      this.$confirm(
        `确认推送 ${this.checkedConfigIds.length} 个配置到 Consul？`,
        '推送 Consul',
        { type: 'warning' }
      ).then(async () => {
        try {
          const res = await pushConsul({ config_ids: this.checkedConfigIds })
          const allOk = res.data.results && res.data.results.every(r => r.status === 'ok')
          this.$notify({
            title: '推送结果',
            message: res.data.message || '推送完成',
            type: allOk ? 'success' : 'warning',
            duration: 5000
          })
        } catch (e) {
          this.$message.error('推送失败: ' + this.getErrMsg(e, '未知错误'))
        }
      }).catch(() => {})
    },

    refreshTree() {
      this.fetchTree(this.searchText)
    },

    // 回滚成功后重新加载当前文件内容
    async handleRollbackSuccess() {
      if (!this.currentConfig) return
      try {
        const res = await getConfigDetail(this.currentConfig.id)
        const config = res.data
        this.currentConfig = config
        this.editorContent = JSON.stringify(config.content, null, 2)
        this.isDirty = false
        this.$message.success('编辑器已更新为回滚后的内容')
      } catch (e) {
        this.$message.error('重新加载配置失败: ' + this.getErrMsg(e, '未知错误'))
      }
    }
  }
}
</script>

<style scoped>
.config-mgmt-layout {
  height: calc(100vh - 84px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f0f2f5;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.page-title {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.actions {
  display: flex;
  gap: 8px;
}

.content {
  flex: 1;
  display: flex;
  overflow: hidden;
  margin: 10px;
  gap: 10px;
}

.tree-panel {
  width: 360px;
  border-radius: 4px;
  background: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.tree-header {
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
}

.tree-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.tree-node-content {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.tree-icon {
  color: #909399;
  font-size: 14px;
}

.node-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.editor-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

.editor-path {
  font-size: 13px;
  color: #606266;
  font-family: monospace;
}

.editor-body {
  flex: 1;
  overflow: hidden;
}

.editor-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>
