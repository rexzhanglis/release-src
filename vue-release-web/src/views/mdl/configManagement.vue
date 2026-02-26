<template>
  <div class="config-mgmt-layout">
    <!-- 顶部操作栏 -->
    <div class="top-bar">
      <h3 class="page-title">MDL 配置管理</h3>
      <div class="actions">
        <el-button type="primary" :loading="syncing" @click="handleSync">
          <i class="el-icon-refresh"></i> 同步
        </el-button>
        <el-button type="warning" :disabled="!hasChecked" @click="showBatchEdit = true">
          <i class="el-icon-edit"></i> 批量修改
        </el-button>
        <el-button type="success" :disabled="!hasChecked" @click="handleGitCommit">
          <i class="el-icon-upload2"></i> 提交 Git
        </el-button>
        <el-button type="info" :disabled="!hasChecked" @click="handlePushConsul">
          <i class="el-icon-connection"></i> 推送 Consul
        </el-button>
        <el-button type="danger" :disabled="!hasCheckedInstances" @click="showDeploy = true">
          <i class="el-icon-video-play"></i> 部署
        </el-button>
        <el-button @click="showAuditLog = true">
          <i class="el-icon-notebook-2"></i> 操作日志
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
          <el-button type="primary" size="small" @click="handleSave">
            <i class="el-icon-check"></i> 保存
          </el-button>
        </div>
        <div class="editor-body">
          <config-editor
            v-if="currentConfig"
            :content="editorContent"
            @change="handleEditorChange"
          />
          <div v-else class="editor-placeholder">
            <i class="el-icon-document" style="font-size:48px;color:#dcdfe6"></i>
            <p style="color:#909399;margin-top:12px">从左侧树中选择一个配置文件</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量修改弹窗 -->
    <batch-edit-modal
      v-model="showBatchEdit"
      :checked-instance-ids="checkedInstanceIds"
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
  </div>
</template>

<script>
import { getConfigTree, getConfigDetail, updateConfig, syncFromGitlab, gitCommit, pushConsul } from '@/api/configMgmt'
import ConfigEditor from './components/ConfigEditor'
import BatchEditModal from './components/BatchEditModal'
import DeployModal from './components/DeployModal'
import AuditLogModal from './components/AuditLogModal'

export default {
  name: 'MdlConfigManagement',
  components: {
    ConfigEditor,
    BatchEditModal,
    DeployModal,
    AuditLogModal
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

      // 选中状态
      checkedConfigIds: [],
      checkedInstanceIds: [],

      // 弹窗控制
      showBatchEdit: false,
      showDeploy: false,
      showAuditLog: false
    }
  },
  computed: {
    hasChecked() {
      return this.checkedConfigIds.length > 0
    },
    hasCheckedInstances() {
      return this.checkedInstanceIds.length > 0
    }
  },
  created() {
    this.fetchTree()
  },
  methods: {
    async fetchTree(search) {
      this.treeLoading = true
      try {
        const params = {}
        if (search) params.search = search
        const res = await getConfigTree(params)
        this.treeData = res.data
      } catch (e) {
        this.$message.error('加载配置树失败')
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
      this.checkedConfigIds = checked
        .filter(n => n.type === 'config')
        .map(n => n.data.config_id)

      const instanceIdSet = new Set()
      checked.forEach(n => {
        if (n.type === 'instance') instanceIdSet.add(n.data.id)
        if (n.type === 'config') {
          // config 节点存有实例 ID：通过 instance 字段
        }
      })
      // 同时收集 config 节点的父 instance
      checked.filter(n => n.type === 'instance').forEach(n => instanceIdSet.add(n.data.id))
      // config 节点也贡献 instance（需要从 config 的 instance 关系获取）
      // 简单方案：选中 instance 类型节点即可
      this.checkedInstanceIds = [...instanceIdSet]
    },

    async handleNodeClick(data) {
      if (data.type !== 'config') return

      try {
        const res = await getConfigDetail(data.data.config_id)
        const config = res.data
        this.currentConfig = config
        this.currentConfigPath = `${config.service_type_name}/${config.instance_name}/${config.filename}`
        this.editorContent = JSON.stringify(config.content, null, 2)
      } catch (e) {
        this.$message.error('加载配置失败')
      }
    },

    handleEditorChange(value) {
      this.editorContent = value
    },

    async handleSave() {
      try {
        const content = JSON.parse(this.editorContent)
        await updateConfig(this.currentConfig.id, { content })
        this.$message.success('保存成功')
      } catch (e) {
        if (e instanceof SyntaxError) {
          this.$message.error('JSON 格式错误，请检查后重试')
        } else {
          this.$message.error('保存失败')
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
        const errMsg = (e.response && e.response.data && e.response.data.error) || e.message
        this.$message.error('同步失败: ' + errMsg)
      } finally {
        this.syncing = false
      }
    },

    handleGitCommit() {
      if (!this.checkedConfigIds.length) {
        this.$message.warning('请先勾选要提交的配置文件')
        return
      }
      this.$prompt('请输入提交信息', '提交到 GitLab', {
        inputValue: 'Update configs',
        confirmButtonText: '提交',
        cancelButtonText: '取消'
      }).then(async ({ value }) => {
        try {
          const res = await gitCommit({
            config_ids: this.checkedConfigIds,
            message: value
          })
          this.$message.success(res.data.message || '提交成功')
        } catch (e) {
          this.$message.error('提交失败')
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
          this.$message.success(res.data.message || '推送成功')
        } catch (e) {
          this.$message.error('推送失败')
        }
      }).catch(() => {})
    },

    refreshTree() {
      this.fetchTree(this.searchText)
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
