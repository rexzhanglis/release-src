<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="初始化服务器环境"
    width="700px"
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

      <el-form ref="initForm" :model="initForm" label-width="130px" size="small">
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

        <el-divider style="margin:12px 0 10px" />

        <!-- 出口机器选项 -->
        <el-form-item label-width="0" style="margin-bottom:8px">
          <el-checkbox v-model="initForm.is_egress">
            <span style="font-weight:600">是出口机器</span>
            <span style="color:#909399;font-size:12px;margin-left:6px">勾选后可上传出口机器所需配置文件及 Anaconda 包</span>
          </el-checkbox>
        </el-form-item>

        <template v-if="initForm.is_egress">
          <el-form-item label="出口配置文件">
            <el-upload
              ref="egressUpload"
              action="#"
              :auto-upload="false"
              :multiple="true"
              :limit="3"
              accept=".py,.cfg,.local"
              :on-change="handleEgressFileChange"
              :on-remove="handleEgressFileRemove"
              :file-list="egressFiles"
            >
              <el-button size="small" icon="el-icon-upload2">选择文件</el-button>
              <div slot="tip" style="color:#909399;font-size:12px;margin-top:4px">
                需上传以下 3 个文件：<br>
                <span style="font-family:monospace">get_cloud_conf.py</span>、
                <span style="font-family:monospace">users_tcp.cfg</span>、
                <span style="font-family:monospace">users_tcp.cfg.local</span><br>
                上传后将复制到 <span style="font-family:monospace">{{ server && server.install_dir }}</span>
              </div>
            </el-upload>
          </el-form-item>

          <el-form-item label="Anaconda 包">
            <el-upload
              ref="anacondaUpload"
              action="#"
              :auto-upload="false"
              :limit="1"
              accept=".tar,.tar.gz,.tgz"
              :on-change="handleAnacondaFileChange"
              :on-remove="handleAnacondaFileRemove"
              :file-list="anacondaFiles"
            >
              <el-button size="small" icon="el-icon-upload2">选择文件</el-button>
              <div slot="tip" style="color:#909399;font-size:12px;margin-top:4px">
                上传 anaconda.tar，将解压到 /opt 目录
              </div>
            </el-upload>
          </el-form-item>
        </template>
      </el-form>
    </template>

    <!-- 阶段2：执行+进度+日志 -->
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
        <span style="margin-left:10px">初始化失败，请查看下方日志</span>
      </div>

      <!-- 进度条 -->
      <div v-if="initStatus === 'running' || initStatus === 'success'" class="progress-container">
        <el-progress
          :percentage="initProgress"
          :status="initStatus === 'success' ? 'success' : ''"
          :stroke-width="10"
          :show-text="true"
        />
        <div v-if="currentStep" class="current-step">
          <i class="el-icon-loading" v-if="initStatus === 'running'"></i>
          {{ currentStep }}
        </div>
      </div>

      <el-divider content-position="left" style="margin:12px 0 8px">
        <i class="el-icon-tickets"></i> 执行日志
      </el-divider>
      <pre ref="logPre" class="init-log" :class="{ 'init-log-error': initStatus === 'failed' && deployLog }">{{ deployLog || (initStatus === 'failed' ? '日志为空，请检查后端服务日志' : '等待输出...') }}</pre>
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

// Ansible 初始化步骤，与 init.yml 的 task 名称对应
const INIT_STEPS = [
  '安装系统工具包',
  '创建运维用户',
  '配置sudoers',
  '设置limits.conf',
  '创建目录结构',
  '配置coredump',
  '配置DNS',
  '部署systemd服务',
  '配置出口机器',
  '安装Anaconda',
]

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
      initForm: { ssh_user: '', ssh_pass: '', is_egress: false },
      egressFiles: [],
      anacondaFiles: [],
      starting: false,
      initStatus: '',   // '' | 'running' | 'success' | 'failed'
      deployLog: '',
      taskId: null,
      pollTimer: null,
      initProgress: 0,
      currentStep: '',
    }
  },
  methods: {
    handleOpen() {
      this.initStatus = ''
      this.deployLog = ''
      this.taskId = null
      this.initProgress = 0
      this.currentStep = ''
      this.initForm = { ssh_user: '', ssh_pass: '', is_egress: false }
      this.egressFiles = []
      this.anacondaFiles = []
    },
    handleClose() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
    handleEgressFileChange(file, fileList) {
      this.egressFiles = fileList
    },
    handleEgressFileRemove(file, fileList) {
      this.egressFiles = fileList
    },
    handleAnacondaFileChange(file, fileList) {
      this.anacondaFiles = fileList
    },
    handleAnacondaFileRemove(file, fileList) {
      this.anacondaFiles = fileList
    },
    // 从日志中解析当前执行到哪个步骤，更新进度条
    updateProgress(log) {
      if (!log) return
      // 匹配 Ansible 输出的 TASK [xxx] 行
      const taskMatches = log.match(/TASK \[([^\]]+)\]/g) || []
      let maxIdx = -1
      let matchedStep = ''
      taskMatches.forEach(taskStr => {
        const taskName = taskStr.replace(/TASK \[/, '').replace(/\]$/, '').trim()
        INIT_STEPS.forEach((step, idx) => {
          if (taskName.includes(step) && idx > maxIdx) {
            maxIdx = idx
            matchedStep = step
          }
        })
      })
      if (maxIdx >= 0) {
        this.currentStep = matchedStep
        // 进度：当前步骤 / 总步骤 * 90（留 10% 给最终保存）
        this.initProgress = Math.min(Math.round((maxIdx + 1) / INIT_STEPS.length * 90), 90)
      } else if (log.includes('PLAY [')) {
        // 已开始但还没匹配到具体步骤
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
        const formData = new FormData()
        if (this.initForm.ssh_user) formData.append('ssh_user', this.initForm.ssh_user)
        if (this.initForm.ssh_pass) formData.append('ssh_pass', this.initForm.ssh_pass)
        formData.append('is_egress', this.initForm.is_egress ? '1' : '0')

        if (this.initForm.is_egress) {
          this.egressFiles.forEach(f => formData.append('egress_files', f.raw))
          if (this.anacondaFiles.length > 0) {
            formData.append('anaconda_file', this.anacondaFiles[0].raw)
          }
        }

        const res = await initMdlServer(this.server.id, formData)
        // request.js 拦截器已将 response.data 直接返回，res 即 {code,message,data}
        const respData = res.data
        if (!respData || !respData.task_id) {
          const msg = (res && res.message) || '服务器返回数据异常，请查看后端日志'
          throw new Error(msg)
        }
        this.taskId = respData.task_id

        this.pollTimer = setInterval(async () => {
          try {
            const r = await getInitStatus(this.server.id, this.taskId)
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
                this.$message.success('系统环境初始化成功，请通过 Jira 发布流程部署版本')
              } else {
                this.$message.error('初始化失败，请查看日志')
              }
            }
          } catch (pollErr) {
            console.error('轮询状态失败:', pollErr)
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

.progress-container {
  margin: 8px 0 4px;
}
.current-step {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}
.current-step .el-icon-loading {
  margin-right: 4px;
  color: #409eff;
}

.init-log {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', 'Monaco', monospace;
}

.init-log-error {
  border-left: 3px solid #f56c6c;
}

.mono {
  font-family: monospace;
  font-size: 12px;
}
</style>
