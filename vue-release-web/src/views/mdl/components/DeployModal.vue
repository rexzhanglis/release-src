<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="部署配置（Consul + Ansible）"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-alert type="warning" :closable="false" style="margin-bottom: 16px">
      将把配置推送到 Consul 并通过 Ansible 部署到 {{ instanceIds.length }} 个实例
    </el-alert>

    <div v-if="deployLog" class="deploy-log">
      <el-divider content-position="left">部署日志</el-divider>
      <pre>{{ deployLog }}</pre>
    </div>

    <div v-if="deployStatus" class="deploy-status">
      <div v-if="deployStatus === 'success'" style="text-align:center;padding:20px;color:#67c23a">
        <i class="el-icon-circle-check" style="font-size:48px"></i>
        <p style="margin-top:10px;font-size:16px">部署成功</p>
      </div>
      <div v-else-if="deployStatus === 'failed'" style="text-align:center;padding:20px;color:#f56c6c">
        <i class="el-icon-circle-close" style="font-size:48px"></i>
        <p style="margin-top:10px;font-size:16px">部署失败</p>
      </div>
      <div v-else-if="deployStatus === 'running'" class="deploying">
        <i class="el-icon-loading" style="font-size:24px;color:#409eff"></i>
        <span style="margin-left:8px;color:#409eff">部署中...</span>
      </div>
    </div>

    <div slot="footer">
      <el-button @click="dialogVisible = false">
        {{ deployStatus ? '关闭' : '取消' }}
      </el-button>
      <el-button
        v-if="!deployStatus"
        type="primary"
        :loading="deploying"
        @click="handleDeploy"
      >
        确认部署
      </el-button>
    </div>
  </el-dialog>
</template>

<script>
import { createDeployTask, getDeployTaskDetail } from '@/api/configMgmt'

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
      deploying: false,
      deployStatus: '',
      deployLog: '',
      pollTimer: null
    }
  },
  methods: {
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
.deploy-log pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 250px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.deploy-status { margin-top: 16px; }
.deploying {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
</style>
