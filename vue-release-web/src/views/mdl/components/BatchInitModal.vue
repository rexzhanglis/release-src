<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="批量初始化服务器环境"
    width="800px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @close="handleClose"
  >
    <!-- 阶段1：参数确认 -->
    <template v-if="phase === 'config'">
      <el-alert type="info" :closable="false" style="margin-bottom:14px">
        将对以下 <strong>{{ servers.length }}</strong> 台服务器执行系统环境初始化。<br>
        <span style="color:#909399;font-size:12px">初始化为串行执行，每台服务器完成后再执行下一台。</span>
      </el-alert>

      <el-form label-width="120px" size="small" style="margin-bottom:12px">
        <el-form-item label="SSH 用户名">
          <el-input v-model="sshUser" placeholder="留空则使用各服务器配置的用户名" style="width:280px" />
        </el-form-item>
        <el-form-item label="SSH 密码">
          <el-input v-model="sshPass" type="password" show-password placeholder="留空则使用系统全局配置的 SSH 密码" style="width:280px" />
        </el-form-item>
      </el-form>

      <el-table :data="servers" border size="small" style="width:100%">
        <el-table-column prop="fqdn" label="FQDN" min-width="160" />
        <el-table-column prop="ip" label="IP 地址" width="140" />
        <el-table-column prop="service_name" label="服务名" width="140" />
        <el-table-column prop="install_dir" label="安装目录" min-width="160" show-overflow-tooltip />
      </el-table>
    </template>

    <!-- 阶段2：执行中 -->
    <template v-else>
      <el-table :data="taskRows" border size="small" style="width:100%;margin-bottom:12px">
        <el-table-column prop="fqdn" label="FQDN" min-width="140" />
        <el-table-column prop="ip" label="IP 地址" width="130" />
        <el-table-column label="状态" width="110" align="center">
          <template slot-scope="{ row }">
            <span v-if="row.status === 'pending'" style="color:#c0c4cc">等待中</span>
            <span v-else-if="row.status === 'running'" style="color:#409eff">
              <i class="el-icon-loading" /> 执行中
            </span>
            <span v-else-if="row.status === 'success'" style="color:#67c23a">
              <i class="el-icon-circle-check" /> 成功
            </span>
            <span v-else-if="row.status === 'failed'" style="color:#f56c6c">
              <i class="el-icon-circle-close" /> 失败
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template slot-scope="{ row }">
            <el-button
              v-if="row.status === 'success' || row.status === 'failed'"
              size="mini"
              type="text"
              @click="showLog(row)"
            >查看日志</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 汇总 -->
      <div v-if="phase === 'done'" style="margin-bottom:12px">
        <el-alert
          :type="summary.type"
          :title="summary.title"
          :closable="false"
          show-icon
        />
      </div>

      <!-- 当前日志 -->
      <el-divider content-position="left" style="margin:8px 0">
        <i class="el-icon-tickets" /> {{ logTitle }}
      </el-divider>
      <pre ref="logPre" class="init-log">{{ currentLog || '等待输出...' }}</pre>
    </template>

    <div slot="footer">
      <el-button @click="dialogVisible = false">{{ phase !== 'config' ? '关闭' : '取消' }}</el-button>
      <el-button
        v-if="phase === 'config'"
        type="primary"
        :loading="starting"
        @click="handleStart"
      >
        开始批量初始化
      </el-button>
    </div>

    <!-- 日志查看弹窗 -->
    <el-dialog
      :visible.sync="showLogDialog"
      :title="`日志 — ${logDialogServer}`"
      width="700px"
      append-to-body
    >
      <pre class="init-log">{{ logDialogContent }}</pre>
    </el-dialog>
  </el-dialog>
</template>

<script>
import { initMdlServer, getInitStatus } from '@/api/mdlServer'

export default {
  name: 'BatchInitModal',
  props: {
    value: { type: Boolean, default: false },
    servers: { type: Array, default: () => [] },
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) },
    },
  },
  data() {
    return {
      phase: 'config',   // 'config' | 'running' | 'done'
      sshUser: '',
      sshPass: '',
      starting: false,
      taskRows: [],      // { fqdn, ip, service_name, install_dir, status, log, taskId }
      currentLog: '',
      logTitle: '执行日志',
      summary: { type: 'success', title: '' },
      showLogDialog: false,
      logDialogServer: '',
      logDialogContent: '',
    }
  },
  methods: {
    handleOpen() {
      this.phase = 'config'
      this.sshUser = ''
      this.sshPass = ''
      this.taskRows = []
      this.currentLog = ''
      this.logTitle = '执行日志'
      this.starting = false
    },
    handleClose() {
      // nothing to clean up - polling is sequential, no dangling timers
    },
    showLog(row) {
      this.logDialogServer = row.fqdn
      this.logDialogContent = row.log || '（无日志）'
      this.showLogDialog = true
    },
    async handleStart() {
      this.starting = true
      this.phase = 'running'
      this.taskRows = this.servers.map(s => ({
        id: s.id,
        fqdn: s.fqdn,
        ip: s.ip,
        service_name: s.service_name,
        install_dir: s.install_dir,
        status: 'pending',
        log: '',
        taskId: null,
      }))

      let successCount = 0
      let failCount = 0

      for (let i = 0; i < this.taskRows.length; i++) {
        const row = this.taskRows[i]
        this.$set(this.taskRows, i, { ...row, status: 'running' })
        this.logTitle = `执行日志 — ${row.fqdn}`
        this.currentLog = ''

        try {
          const formData = new FormData()
          if (this.sshUser) formData.append('ssh_user', this.sshUser)
          if (this.sshPass) formData.append('ssh_pass', this.sshPass)
          formData.append('is_egress', '0')

          const res = await initMdlServer(row.id, formData)
          const respData = res.data && res.data.data
          if (!respData || !respData.task_id) {
            const msg = (res.data && res.data.message) || '服务器返回数据异常'
            throw new Error(msg)
          }

          const taskId = respData.task_id
          this.$set(this.taskRows, i, { ...this.taskRows[i], taskId })

          // Poll until done
          const finalLog = await this.pollUntilDone(row.id, taskId, i)
          successCount++
          this.$set(this.taskRows, i, { ...this.taskRows[i], status: 'success', log: finalLog })
        } catch (e) {
          const msg = (e.response && e.response.data && e.response.data.message) || e.message || '初始化失败'
          const existingLog = this.taskRows[i].log || ''
          this.$set(this.taskRows, i, { ...this.taskRows[i], status: 'failed', log: existingLog + `\n[错误] ${msg}` })
          failCount++
        }
      }

      this.phase = 'done'
      this.starting = false
      this.summary = {
        type: failCount === 0 ? 'success' : (successCount === 0 ? 'error' : 'warning'),
        title: `批量初始化完成：${successCount} 台成功，${failCount} 台失败`,
      }
    },

    pollUntilDone(serverId, taskId, rowIndex) {
      return new Promise((resolve, reject) => {
        const timer = setInterval(async () => {
          try {
            const r = await getInitStatus(serverId, taskId)
            const d = r.data && r.data.data
            if (!d) return
            const log = d.log || ''
            this.$set(this.taskRows, rowIndex, { ...this.taskRows[rowIndex], log })
            this.currentLog = log
            this.$nextTick(() => {
              if (this.$refs.logPre) {
                this.$refs.logPre.scrollTop = this.$refs.logPre.scrollHeight
              }
            })
            if (d.status === 'success') {
              clearInterval(timer)
              resolve(log)
            } else if (d.status === 'failed') {
              clearInterval(timer)
              reject(new Error('Ansible 执行失败'))
            }
          } catch (e) {
            console.error('轮询失败:', e)
          }
        }, 2000)
      })
    },
  },
}
</script>

<style scoped>
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
</style>
