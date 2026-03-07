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

      <!-- 批量模式：显示实例列表 -->
      <template v-if="isBatch">
        <div style="margin-bottom:12px;font-size:13px;color:#303133;font-weight:600">
          待初始化服务实例（共 {{ serverList.length }} 个，将依次串行执行）：
        </div>
        <el-table :data="serverList" size="mini" border style="margin-bottom:16px">
          <el-table-column prop="service_name" label="服务名" />
          <el-table-column prop="install_dir" label="安装目录" show-overflow-tooltip>
            <template slot-scope="{ row }"><span class="mono">{{ row.install_dir }}</span></template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 单个模式：服务器信息展示 -->
      <el-descriptions v-else-if="singleServer" :column="2" size="small" border style="margin-bottom:16px">
        <el-descriptions-item label="FQDN">
          <span class="mono">{{ singleServer.fqdn }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="IP 地址">
          <span class="mono">{{ singleServer.ip }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="服务名">
          <span class="mono">{{ singleServer.service_name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="安装目录">
          <span class="mono">{{ singleServer.install_dir }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="备份目录">
          <span class="mono">{{ singleServer.backups_dir }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="远端 Python">
          <span class="mono">{{ singleServer.remote_python }}</span>
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
            <span style="color:#909399;font-size:12px;margin-left:6px">勾选后可上传出口机器所需配置文件</span>
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
          <div>{{ isBatch ? `批量初始化完成（共 ${batchItems.length} 个）` : '系统环境初始化完成' }}</div>
          <div style="font-size:12px;color:#67c23a;margin-top:4px">
            请前往 Jira 创建发布工单，通过发布流程进行首次版本部署
          </div>
        </div>
      </div>

      <!-- 批量模式：实例列表状态 -->
      <template v-if="isBatch && batchItems.length">
        <el-table :data="batchItems" size="mini" border style="margin:10px 0 8px">
          <el-table-column label="服务名" prop="server.service_name" />
          <el-table-column label="状态" width="100" align="center">
            <template slot-scope="{ row }">
              <span v-if="row.status === 'running'" style="color:#409eff">
                <i class="el-icon-loading" /> 初始化中
              </span>
              <span v-else-if="row.status === 'success'" style="color:#67c23a">
                <i class="el-icon-circle-check" /> 成功
              </span>
              <span v-else-if="row.status === 'failed'" style="color:#f56c6c">
                <i class="el-icon-circle-close" /> 失败
              </span>
              <span v-else style="color:#909399">等待中</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <!-- 单个模式成功后：配置实例创建引导 -->
      <template v-if="!isBatch && initStatus === 'success'">
        <el-divider style="margin:14px 0 10px" />
        <div style="font-size:13px;font-weight:600;margin-bottom:10px;color:#303133">
          <i class="el-icon-folder-add" style="color:#409eff;margin-right:4px" />
          创建配置管理实例
        </div>
        <div v-if="!configCreated">
          <el-alert type="info" :closable="false" style="margin-bottom:12px;font-size:12px">
            在配置管理中为该服务器创建对应实例，并将空配置文件提交到 GitLab，方便后续通过平台管理配置。
          </el-alert>
          <el-form ref="cfgForm" :model="cfgForm" label-width="100px" size="small">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="服务类型" prop="service_type_name"
                  :rules="[{ required: true, message: '请填写服务类型', trigger: 'blur' }]">
                  <el-input v-model="cfgForm.service_type_name" placeholder="如 aliforward、forward" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="实例名称" prop="instance_name"
                  :rules="[{ required: true, message: '请填写实例名称', trigger: 'blur' }]">
                  <el-input v-model="cfgForm.instance_name" placeholder="如 10_121_21_240_19015" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="Commit 说明">
              <el-input v-model="cfgForm.commit_message" placeholder="留空自动生成" style="width:300px" />
            </el-form-item>
          </el-form>
          <div style="display:flex;gap:8px;margin-top:4px">
            <el-button type="primary" size="small" :loading="cfgCreating" @click="handleCreateConfig">
              创建并提交 Git
            </el-button>
            <el-button size="small" @click="configSkipped = true" v-if="!configSkipped">跳过</el-button>
          </div>
          <div v-if="configSkipped" style="margin-top:8px;font-size:12px;color:#909399">
            已跳过，可稍后在「配置管理」页面手动创建。
          </div>
        </div>
        <el-alert v-else type="success" :closable="false" style="font-size:12px">
          <i class="el-icon-circle-check" />
          配置实例已创建：<b>{{ configCreated }}</b>
        </el-alert>
      </template>
      <div v-else-if="initStatus === 'failed'" class="status-row fail">
        <i class="el-icon-circle-close" style="font-size:32px"></i>
        <span style="margin-left:10px">{{ isBatch ? '批量初始化部分失败，请查看各实例日志' : '初始化失败，请查看下方日志' }}</span>
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
import { createConfigInstance } from '@/api/configMgmt'

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
]

export default {
  name: 'InitServerModal',
  props: {
    value: { type: Boolean, default: false },
    // 支持单个对象或数组（批量初始化）
    server: { type: [Object, Array], default: null },
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) },
    },
    serverList() {
      if (!this.server) return []
      return Array.isArray(this.server) ? this.server : [this.server]
    },
    isBatch() {
      return this.serverList.length > 1
    },
    singleServer() {
      return this.serverList[0] || null
    },
  },
  data() {
    return {
      initForm: { ssh_user: '', ssh_pass: '', is_egress: false },
      egressFiles: [],
      starting: false,
      initStatus: '',   // '' | 'running' | 'success' | 'failed'
      deployLog: '',
      taskId: null,
      pollTimer: null,
      initProgress: 0,
      currentStep: '',
      // 批量模式：每个实例状态
      batchItems: [],  // [{ server, status: ''|'running'|'success'|'failed', log }]
      batchCurrentIdx: -1,
      // 配置实例创建（单个模式）
      cfgForm: { service_type_name: '', instance_name: '', commit_message: '' },
      cfgCreating: false,
      configCreated: '',
      configSkipped: false,
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
      this.batchItems = this.serverList.map(s => ({ server: s, status: '', log: '' }))
      this.batchCurrentIdx = -1
      // 单个模式：预填配置实例表单
      const s = this.singleServer
      if (s) {
        this.cfgForm = {
          service_type_name: s.role_name || '',
          instance_name: s.ip ? s.ip.replace(/\./g, '_') : '',
          commit_message: '',
        }
      } else {
        this.cfgForm = { service_type_name: '', instance_name: '', commit_message: '' }
      }
      this.cfgCreating = false
      this.configCreated = ''
      this.configSkipped = false
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
      if (this.isBatch) {
        await this._runBatch()
      } else {
        await this._runSingle(this.singleServer)
      }
    },
    // 单个初始化核心逻辑，返回最终 status
    async _runSingle(srv) {
      this.starting = true
      this.initStatus = 'running'
      this.deployLog = ''
      this.initProgress = 0
      this.currentStep = '准备初始化...'

      return new Promise((resolve) => {
        const formData = new FormData()
        if (this.initForm.ssh_user) formData.append('ssh_user', this.initForm.ssh_user)
        if (this.initForm.ssh_pass) formData.append('ssh_pass', this.initForm.ssh_pass)
        formData.append('is_egress', this.initForm.is_egress ? '1' : '0')
        if (this.initForm.is_egress) {
          this.egressFiles.forEach(f => formData.append('egress_files', f.raw))
        }

        initMdlServer(srv.id, formData).then(res => {
          const respData = res.data
          if (!respData || !respData.task_id) {
            throw new Error((res && res.message) || '服务器返回数据异常')
          }
          this.taskId = respData.task_id

          this.pollTimer = setInterval(async () => {
            try {
              const r = await getInitStatus(srv.id, this.taskId)
              const d = r.data
              if (!d) return
              this.deployLog = d.log || ''
              this.updateProgress(this.deployLog)
              this.$nextTick(() => {
                if (this.$refs.logPre) this.$refs.logPre.scrollTop = this.$refs.logPre.scrollHeight
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
                this.$emit('done', d.status)
                resolve(d.status)
              }
            } catch (pollErr) {
              console.error('轮询状态失败:', pollErr)
            }
          }, 2000)
        }).catch(e => {
          const msg = (e.response && e.response.data && e.response.data.message) || e.message || '启动失败'
          this.$message.error(msg)
          this.initStatus = 'failed'
          this.starting = false
          resolve('failed')
        })
      })
    },
    // 批量初始化：依次串行执行每个实例
    async _runBatch() {
      this.starting = true
      this.initStatus = 'running'
      let allSuccess = true

      for (let i = 0; i < this.batchItems.length; i++) {
        this.batchCurrentIdx = i
        this.batchItems[i].status = 'running'
        this.deployLog = ''
        this.initProgress = 0
        this.currentStep = `初始化 ${this.batchItems[i].server.service_name}...`

        const srv = this.batchItems[i].server
        const formData = new FormData()
        if (this.initForm.ssh_user) formData.append('ssh_user', this.initForm.ssh_user)
        if (this.initForm.ssh_pass) formData.append('ssh_pass', this.initForm.ssh_pass)
        formData.append('is_egress', '0')

        const finalStatus = await new Promise((resolve) => {
          initMdlServer(srv.id, formData).then(res => {
            const respData = res.data
            if (!respData || !respData.task_id) throw new Error('返回数据异常')
            const taskId = respData.task_id

            const timer = setInterval(async () => {
              try {
                const r = await getInitStatus(srv.id, taskId)
                const d = r.data
                if (!d) return
                this.batchItems[i].log = d.log || ''
                this.deployLog = d.log || ''
                this.updateProgress(d.log || '')
                this.$nextTick(() => {
                  if (this.$refs.logPre) this.$refs.logPre.scrollTop = this.$refs.logPre.scrollHeight
                })
                if (d.status === 'success' || d.status === 'failed') {
                  clearInterval(timer)
                  this.batchItems[i].status = d.status
                  resolve(d.status)
                }
              } catch (e) { console.error(e) }
            }, 2000)
          }).catch(e => {
            this.batchItems[i].status = 'failed'
            resolve('failed')
          })
        })

        if (finalStatus !== 'success') allSuccess = false
      }

      this.batchCurrentIdx = -1
      this.starting = false
      this.initStatus = allSuccess ? 'success' : 'failed'
      if (allSuccess) {
        this.initProgress = 100
        this.$message.success(`批量初始化完成，共 ${this.batchItems.length} 个实例`)
      } else {
        this.$message.error('批量初始化部分失败，请查看各实例日志')
      }
      this.$emit('done', this.initStatus)
    },
    async handleCreateConfig() {
      try {
        await this.$refs.cfgForm.validate()
      } catch { return }
      this.cfgCreating = true
      try {
        const payload = {
          server_id: this.singleServer && this.singleServer.id,
          service_type_name: this.cfgForm.service_type_name.trim(),
          instance_name: this.cfgForm.instance_name.trim(),
          commit_message: this.cfgForm.commit_message.trim() || undefined,
          git_commit: true,
        }
        const res = await createConfigInstance(payload)
        const data = (res.data && res.data.data) || res.data || {}
        const label = data.config_instance
          ? `${data.config_instance.service_type}/${data.config_instance.name}`
          : `${payload.service_type_name}/${payload.instance_name}`
        this.configCreated = label
        this.$message.success('配置实例已创建')
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '创建失败'
        this.$message.error(msg)
      } finally {
        this.cfgCreating = false
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
