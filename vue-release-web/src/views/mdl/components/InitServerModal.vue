<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="初始化服务器环境"
    width="680px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @close="handleClose"
  >
    <!-- 阶段1：确认参数 -->
    <template v-if="!initStatus">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        将对目标服务器执行<strong>系统环境初始化</strong>：创建目录结构 → 配置 systemd 服务文件 → 配置 coredump<br>
        <span style="color:#909399;font-size:12px">初始化完成后，请通过 Jira 发布流程进行首次版本部署。</span>
      </el-alert>

      <!-- 服务器信息展示 -->
      <el-descriptions v-if="server" :column="2" size="small" border style="margin-bottom:16px">
        <el-descriptions-item label="FQDN">
          <span class="mono">{{ server.fqdn }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="IP 地址">
          <span class="mono">{{ server.ip }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="服务名">
          <span class="mono">{{ server.service_name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="安装目录">
          <span class="mono">{{ server.install_dir }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="备份目录">
          <span class="mono">{{ server.backups_dir }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="远端 Python">
          <span class="mono">{{ server.remote_python }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-form ref="initForm" :model="initForm" label-width="120px" size="small">
        <el-form-item label="SSH 用户名">
          <el-input
            v-model="initForm.ssh_user"
            placeholder="留空则使用服务器配置的用户名"
            style="width:280px"
          />
        </el-form-item>
        <el-form-item label="SSH 密码">
          <el-input
            v-model="initForm.ssh_pass"
            type="password"
            show-password
            placeholder="留空则使用系统全局配置的 SSH 密码"
            style="width:280px"
          />
        </el-form-item>
      </el-form>
    </template>

    <!-- 阶段2：执行+日志 -->
    <template v-else>
      <div v-if="initStatus === 'running'" class="status-row">
        <i class="el-icon-loading" style="font-size:24px;color:#409eff"></i>
        <span style="margin-left:10px;color:#409eff">初始化中，请耐心等待...</span>
      </div>
      <div v-else-if="initStatus === 'success'" class="status-row success">
        <i class="el-icon-circle-check" style="font-size:32px"></i>
        <div style="margin-left:12px">
          <div>系统环境初始化完成</div>
          <div style="font-size:12px;color:#67c23a;margin-top:4px">
            请前往 Jira 创建发布工单，通过发布流程进行首次版本部署
          </div>
        </div>
      </div>
      <div v-else-if="initStatus === 'failed'" class="status-row fail">
        <i class="el-icon-circle-close" style="font-size:32px"></i>
        <span style="margin-left:10px">初始化失败，请查看日志</span>
      </div>

      <el-divider content-position="left" style="margin:12px 0 8px">
        <i class="el-icon-tickets"></i> 执行日志
      </el-divider>
      <pre ref="logPre" class="init-log">{{ deployLog || '等待输出...' }}</pre>
    </template>

    <div slot="footer">
      <el-button @click="dialogVisible = false">
        {{ initStatus ? '关闭' : '取消' }}
      </el-button>
      <el-button
        v-if="!initStatus"
        type="primary"
        :loading="starting"
        @click="handleStart"
      >
        开始初始化环境
      </el-button>
    </div>
  </el-dialog>
</template>

<script>
import { initMdlServer, getInitStatus } from '@/api/mdlServer'

export default {
  name: 'InitServerModal',
  props: {
    value: { type: Boolean, default: false },
    server: { type: Object, default: null },
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) },
    },
  },
  data() {
    return {
      initForm: { ssh_user: '', ssh_pass: '' },
      starting: false,
      initStatus: '',   // '' | 'running' | 'success' | 'failed'
      deployLog: '',
      taskId: null,
      pollTimer: null,
    }
  },
  methods: {
    handleOpen() {
      this.initStatus = ''
      this.deployLog = ''
      this.taskId = null
      this.initForm = { ssh_user: '', ssh_pass: '' }
    },
    handleClose() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
    async handleStart() {
      this.starting = true
      this.initStatus = 'running'
      this.deployLog = ''

      try {
        const res = await initMdlServer(this.server.id, {
          ssh_user: this.initForm.ssh_user || undefined,
          ssh_pass: this.initForm.ssh_pass || undefined,
        })
        const respData = res.data && res.data.data
        if (!respData || !respData.task_id) {
          const msg = (res.data && res.data.message) || '服务器返回数据异常，请查看后端日志'
          throw new Error(msg)
        }
        this.taskId = respData.task_id

        this.pollTimer = setInterval(async () => {
          try {
            const r = await getInitStatus(this.server.id, this.taskId)
            const d = r.data.data
            this.deployLog = d.log || ''
            this.$nextTick(() => {
              if (this.$refs.logPre) {
                this.$refs.logPre.scrollTop = this.$refs.logPre.scrollHeight
              }
            })
            if (d.status === 'success' || d.status === 'failed') {
              clearInterval(this.pollTimer)
              this.pollTimer = null
              this.initStatus = d.status
              this.starting = false
              if (d.status === 'success') {
                this.$message.success('系统环境初始化成功，请通过 Jira 发布流程部署版本')
              } else {
                this.$message.error('初始化失败，请查看日志')
              }
            }
          } catch {
            clearInterval(this.pollTimer)
            this.pollTimer = null
            this.initStatus = 'failed'
            this.starting = false
          }
        }, 2000)
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '启动失败'
        this.$message.error(msg)
        this.initStatus = 'failed'
        this.starting = false
      }
    },
  },
}
</script>

<style scoped>
.status-row {
  display: flex;
  align-items: center;
  padding: 12px 0;
  font-size: 15px;
}
.status-row.success { color: #67c23a; }
.status-row.fail    { color: #f56c6c; }

.init-log {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 360px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
}

.mono {
  font-family: monospace;
  font-size: 12px;
}
</style>
