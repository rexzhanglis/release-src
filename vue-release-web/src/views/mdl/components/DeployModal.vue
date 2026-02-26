<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="部署配置（Consul + Ansible）"
    width="800px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @close="handleClose"
  >
    <!-- 预览阶段 -->
    <template v-if="!deployStatus">
      <div v-loading="loadingPreview">
        <el-alert type="warning" :closable="false" style="margin-bottom:14px">
          将对以下 <strong>{{ previewList.length }}</strong> 个实例执行：推送配置到 Consul，并通过 Ansible 重启服务
        </el-alert>

        <div v-if="previewList.length" class="preview-list">
          <div
            v-for="inst in previewList"
            :key="inst.instance_id"
            class="inst-card"
          >
            <!-- 实例标题行 -->
            <div class="inst-card-header">
              <i class="el-icon-monitor" style="color:#409eff;margin-right:6px"></i>
              <span class="inst-name">{{ inst.instance_name }}</span>
              <el-tag size="mini" type="info" style="margin-left:8px">{{ inst.service_type }}</el-tag>
              <el-tag size="mini" type="success" style="margin-left:4px">{{ inst.host_ip }}</el-tag>
            </div>

            <!-- 字段明细 -->
            <el-descriptions :column="2" size="mini" border class="inst-desc">
              <el-descriptions-item label="部署目录">
                <span class="mono">{{ inst.install_dir }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="服务名">
                <span class="mono">{{ inst.service_name }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Consul 路径" :span="2">
                <span class="mono">{{ inst.consul_space }}</span>
              </el-descriptions-item>
            </el-descriptions>

            <!-- 配置文件列表 -->
            <div class="config-files">
              <div class="config-files-title">
                <i class="el-icon-document"></i> 配置文件（{{ inst.configs.length }} 个）
              </div>
              <el-table :data="inst.configs" size="mini" border style="width:100%">
                <el-table-column prop="filename" label="文件名" width="200" />
                <el-table-column label="Consul Key" min-width="280">
                  <template slot-scope="{ row }">
                    <span class="mono small">{{ row.consul_key }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="size" label="大小(字符)" width="100" align="center" />
              </el-table>
            </div>
          </div>
        </div>
        <div v-else-if="!loadingPreview" style="color:#999;text-align:center;padding:20px">
          暂无实例信息
        </div>
      </div>
    </template>

    <!-- 部署进行中 / 结果 -->
    <template v-else>
      <div v-if="deployStatus === 'running'" class="deploying">
        <i class="el-icon-loading" style="font-size:28px;color:#409eff"></i>
        <span style="margin-left:10px;color:#409eff;font-size:15px">
          部署中，正在并发部署 {{ instanceIds.length }} 个实例...
        </span>
      </div>
      <div v-if="deployStatus === 'success'" class="deploy-result success">
        <i class="el-icon-circle-check" style="font-size:42px"></i>
        <p>全部实例部署成功</p>
      </div>
      <div v-if="deployStatus === 'failed'" class="deploy-result fail">
        <i class="el-icon-circle-close" style="font-size:42px"></i>
        <p>部分或全部实例部署失败，请查看日志</p>
      </div>

      <div v-if="deployLog" class="deploy-log">
        <el-divider content-position="left">部署日志</el-divider>
        <pre ref="logPre">{{ deployLog }}</pre>
      </div>
    </template>

    <div slot="footer">
      <el-button @click="dialogVisible = false">
        {{ deployStatus ? '关闭' : '取消' }}
      </el-button>
      <el-button
        v-if="!deployStatus"
        type="primary"
        :loading="deploying"
        :disabled="loadingPreview || previewList.length === 0"
        @click="handleDeploy"
      >
        确认部署
      </el-button>
    </div>
  </el-dialog>
</template>

<script>
import { getDeployPreview, createDeployTask, getDeployTaskDetail } from '@/api/configMgmt'

export default {
  name: 'DeployModal',
  props: {
    value: {
      type: Boolean,
      default: false
    },
    instanceIds: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) }
    }
  },
  data() {
    return {
      loadingPreview: false,
      previewList: [],
      deploying: false,
      deployStatus: '',
      deployLog: '',
      pollTimer: null
    }
  },
  methods: {
    async handleOpen() {
      // 重置状态
      this.deployStatus = ''
      this.deployLog = ''
      this.previewList = []

      if (!this.instanceIds.length) return
      this.loadingPreview = true
      try {
        const res = await getDeployPreview({ instance_ids: this.instanceIds })
        this.previewList = res.data || []
      } catch (e) {
        this.$message.error('获取部署信息失败')
      } finally {
        this.loadingPreview = false
      }
    },

    handleClose() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },

    async handleDeploy() {
      this.deploying = true
      this.deployStatus = 'running'
      this.deployLog = ''

      try {
        const res = await createDeployTask({ instance_ids: this.instanceIds })
        const taskId = res.data.task_id

        this.pollTimer = setInterval(async () => {
          try {
            const taskRes = await getDeployTaskDetail(taskId)
            const task = taskRes.data
            this.deployLog = task.log || ''
            // 日志滚到底部
            this.$nextTick(() => {
              if (this.$refs.logPre) {
                this.$refs.logPre.scrollTop = this.$refs.logPre.scrollHeight
              }
            })
            if (task.status === 'success' || task.status === 'failed') {
              clearInterval(this.pollTimer)
              this.pollTimer = null
              this.deployStatus = task.status
              this.deploying = false
              if (task.status === 'success') {
                this.$message.success('部署完成')
                this.$emit('success')
              } else {
                this.$message.error('部署失败，请查看日志')
              }
            }
          } catch (e) {
            clearInterval(this.pollTimer)
            this.pollTimer = null
            this.deployStatus = 'failed'
            this.deploying = false
          }
        }, 2000)
      } catch (e) {
        this.$message.error('创建部署任务失败')
        this.deployStatus = 'failed'
        this.deploying = false
      }
    }
  }
}
</script>

<style scoped>
.preview-list {
  max-height: 480px;
  overflow-y: auto;
}
.inst-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 14px;
  overflow: hidden;
}
.inst-card-header {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}
.inst-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}
.inst-desc {
  margin: 10px 14px 6px;
}
.config-files {
  padding: 0 14px 14px;
}
.config-files-title {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}
.mono {
  font-family: monospace;
  font-size: 12px;
  color: #303133;
  word-break: break-all;
}
.small {
  font-size: 11px;
}
/* 部署中 / 结果 */
.deploying {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.deploy-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0 8px;
}
.deploy-result.success { color: #67c23a; }
.deploy-result.fail { color: #f56c6c; }
.deploy-result p { margin-top: 10px; font-size: 15px; }
.deploy-log pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
