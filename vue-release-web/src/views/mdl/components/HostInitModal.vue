<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="初始化服务器系统环境"
    width="640px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @close="handleClose"
  >
    <!-- 阶段1：填写参数 -->
    <template v-if="!initStatus">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        将对目标服务器执行<strong>系统级初始化</strong>：安装工具包 → 创建运维用户 → 配置 limits → 配置 DNS<br>
        <span style="color:#909399;font-size:12px">每台机器只需执行一次，完成后再添加服务实例并进行实例初始化。</span>
      </el-alert>

      <el-descriptions v-if="host" :column="2" size="small" border style="margin-bottom:16px">
        <el-descriptions-item label="FQDN">
          <span class="mono">{{ host.fqdn }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="IP 地址">
          <span class="mono">{{ host.ip }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="SSH 用户">
          <span class="mono">{{ host.user || 'root' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="远端 Python">
          <span class="mono">{{ host.remote_python || '/usr/bin/python3' }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-form label-width="110px" size="small">
        <el-form-item label="SSH 用户名">
          <el-input
            v-model="form.ssh_user"
            :placeholder="'留空则使用 ' + (host && host.user || 'root')"
            style="width:280px"
          />
        </el-form-item>
        <el-form-item label="SSH 密码">
          <el-input
            v-model="form.ssh_pass"
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
          <div>服务器系统环境初始化完成</div>
          <div style="font-size:12px;color:#67c23a;margin-top:4px">
            可在服务器详情页新增服务实例并进行实例初始化
          </div>
        </div>
      </div>
      <div v-else-if="initStatus === 'failed'" class="status-row fail">
        <i class="el-icon-circle-close" style="font-size:32px"></i>
        <span style="margin-left:10px">初始化失败，请查看下方日志</span>
      </div>

      <!-- 进度条 -->
      <div v-if="initStatus === 'running' || initStatus === 'success'" class="progress-container">
        <el-progress
          :percentage="initProgress"
          :status="initStatus === 'success' ? 'success' : ''"
          :stroke-width="10"
        />
        <div v-if="currentStep" class="current-step">
          <i class="el-icon-loading" v-if="initStatus === 'running'"></i>
          {{ currentStep }}
        </div>
      </div>

      <el-divider content-position="left" style="margin:12px 0 8px">
        <i class="el-icon-tickets"></i> 执行日志
      </el-divider>
      <pre ref="logPre" class="init-log" :class="{ 'init-log-error': initStatus === 'failed' }">{{ deployLog || (initStatus === 'failed' ? '日志为空，请检查后端服务日志' : '等待输出...') }}</pre>
    </template>

    <div slot="footer">
      <el-button @click="dialogVisible = false">{{ initStatus ? '关闭' : '取消' }}</el-button>
      <el-button
        v-if="!initStatus"
        type="primary"
        :loading="starting"
        @click="handleStart"
      >开始初始化</el-button>
    </div>
  </el-dialog>
</template>

<script>
import { initHost, getHostInitStatus } from '@/api/mdlServer'

const HOST_INIT_STEPS = [
  '安装常用工具包',
  '创建运维用户',
  '配置运维用户 sudoers',
  '配置 limits.conf',
  '配置 DNS',
  '重启 systemd-resolved',
]

export default {
  name: 'HostInitModal',
  model: { prop: 'value', event: 'input' },
  props: {
    value: { type: Boolean, default: false },
    host: { type: Object, default: null },
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(v) { this.$emit('input', v) },
    },
  },
  data() {
    return {
      form: { ssh_user: '', ssh_pass: '' },
      starting: false,
      initStatus: '',
      deployLog: '',
      taskId: null,
      pollTimer: null,
      initProgress: 0,
      currentStep: '',
    }
  },
  methods: {
    handleOpen() {
      this.form = { ssh_user: '', ssh_pass: '' }
      this.starting = false
      this.initStatus = ''
      this.deployLog = ''
      this.taskId = null
      this.initProgress = 0
      this.currentStep = ''
    },
    handleClose() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
    updateProgress(log) {
      if (!log) return
      const taskMatches = log.match(/TASK \[([^\]]+)\]/g) || []
      let maxIdx = -1
      let matchedStep = ''
      taskMatches.forEach(taskStr => {
        const taskName = taskStr.replace(/TASK \[/, '').replace(/\]$/, '').trim()
        HOST_INIT_STEPS.forEach((step, idx) => {
          if (taskName.includes(step) && idx > maxIdx) {
            maxIdx = idx
            matchedStep = step
          }
        })
      })
      if (maxIdx >= 0) {
        this.currentStep = matchedStep
        this.initProgress = Math.min(Math.round((maxIdx + 1) / HOST_INIT_STEPS.length * 90), 90)
      } else if (log.includes('PLAY [')) {
        this.initProgress = 5
        this.currentStep = '连接目标服务器...'
      }
    },
    async handleStart() {
      this.starting = true
      this.initStatus = 'running'
      this.deployLog = ''
      this.initProgress = 0
      this.currentStep = '准备初始化...'
      try {
        const payload = {}
        if (this.form.ssh_user) payload.ssh_user = this.form.ssh_user
        if (this.form.ssh_pass) payload.ssh_pass = this.form.ssh_pass

        const res = await initHost(this.host.id, payload)
        const respData = res.data
        if (!respData || !respData.task_id) {
          throw new Error((res && res.message) || '服务器返回数据异常')
        }
        this.taskId = respData.task_id

        this.pollTimer = setInterval(async () => {
          try {
            const r = await getHostInitStatus(this.host.id, this.taskId)
            const d = r.data
            if (!d) return
            this.deployLog = d.log || ''
            this.updateProgress(this.deployLog)
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
                this.initProgress = 100
                this.currentStep = '初始化完成'
                this.$message.success('服务器系统环境初始化成功')
              } else {
                this.$message.error('初始化失败，请查看日志')
              }
              this.$emit('done', d.status)
            }
          } catch (e) {
            console.error('轮询状态失败:', e)
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
.progress-container { margin: 8px 0 4px; }
.current-step {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}
.init-log {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 280px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
}
.init-log-error { border-left: 3px solid #f56c6c; }
.mono { font-family: monospace; font-size: 12px; }
</style>
