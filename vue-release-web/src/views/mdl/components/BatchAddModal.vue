<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="批量新增服务器"
    width="1100px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @close="handleClose"
  >
    <div style="margin-bottom:10px;display:flex;align-items:center;gap:8px">
      <el-button size="small" icon="el-icon-plus" @click="addRow">添加一行</el-button>
      <el-button size="small" icon="el-icon-delete" @click="clearRows">清空</el-button>
      <span style="color:#909399;font-size:12px;margin-left:8px">
        每行填写一台服务器信息，FQDN 和 IP 为必填项
      </span>
    </div>

    <el-table :data="rows" border size="small" style="width:100%">
      <el-table-column label="FQDN *" min-width="140">
        <template slot-scope="{ row, $index }">
          <el-input v-model="row.fqdn" size="mini" placeholder="mdl-fwd-prod01" :class="{ 'is-error': errors[$index] && errors[$index].fqdn }" />
          <div v-if="errors[$index] && errors[$index].fqdn" style="color:#f56c6c;font-size:11px">{{ errors[$index].fqdn }}</div>
        </template>
      </el-table-column>
      <el-table-column label="IP *" width="140">
        <template slot-scope="{ row, $index }">
          <el-input v-model="row.ip" size="mini" placeholder="10.121.21.240" :class="{ 'is-error': errors[$index] && errors[$index].ip }" />
          <div v-if="errors[$index] && errors[$index].ip" style="color:#f56c6c;font-size:11px">{{ errors[$index].ip }}</div>
        </template>
      </el-table-column>
      <el-table-column label="服务名" width="130">
        <template slot-scope="{ row }">
          <el-input v-model="row.service_name" size="mini" placeholder="mdl-forward" />
        </template>
      </el-table-column>
      <el-table-column label="角色名" width="110">
        <template slot-scope="{ row }">
          <el-input v-model="row.role_name" size="mini" placeholder="forward" />
        </template>
      </el-table-column>
      <el-table-column label="SSH用户" width="90">
        <template slot-scope="{ row }">
          <el-input v-model="row.user" size="mini" />
        </template>
      </el-table-column>
      <el-table-column label="安装目录" min-width="160">
        <template slot-scope="{ row }">
          <el-input v-model="row.install_dir" size="mini" placeholder="/datayes/forward/bin" />
        </template>
      </el-table-column>
      <el-table-column label="备份目录" min-width="150">
        <template slot-scope="{ row }">
          <el-input v-model="row.backups_dir" size="mini" placeholder="/datayes/forward/backup" />
        </template>
      </el-table-column>
      <el-table-column label="标签" width="140">
        <template slot-scope="{ row }">
          <el-select v-model="row.label_ids" multiple size="mini" placeholder="选择标签" style="width:100%">
            <el-option v-for="lbl in allLabels" :key="lbl.id" :label="lbl.name" :value="lbl.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template slot-scope="{ row }">
          <el-tag v-if="row._status === 'ok'" type="success" size="mini">成功</el-tag>
          <el-tag v-else-if="row._status === 'error'" type="danger" size="mini">失败</el-tag>
          <span v-else style="color:#c0c4cc;font-size:12px">-</span>
        </template>
      </el-table-column>
      <el-table-column label="" width="50" align="center">
        <template slot-scope="{ $index }">
          <el-button
            size="mini"
            type="text"
            icon="el-icon-delete"
            style="color:#f56c6c"
            @click="removeRow($index)"
          />
        </template>
      </el-table-column>
    </el-table>

    <!-- 结果汇总 -->
    <div v-if="resultSummary" style="margin-top:12px">
      <el-alert
        :type="resultSummary.type"
        :title="resultSummary.title"
        :closable="false"
        show-icon
      />
    </div>

    <div slot="footer">
      <el-button @click="dialogVisible = false">{{ resultSummary ? '关闭' : '取消' }}</el-button>
      <el-button
        v-if="!resultSummary"
        type="primary"
        :loading="saving"
        @click="handleSubmit"
      >
        批量保存（{{ rows.length }} 台）
      </el-button>
    </div>
  </el-dialog>
</template>

<script>
import { createMdlServer } from '@/api/mdlServer'

const newRow = () => ({
  fqdn: '',
  ip: '',
  service_name: 'mdl-forward',
  role_name: 'forward',
  user: 'root',
  remote_python: '/opt/anaconda/bin/python',
  install_dir: '/datayes/forward/bin',
  backups_dir: '/datayes/forward/backup',
  consul_space: '',
  consul_token: '',
  consul_files: 'feeder_handler.cfg',
  config_git_url: '',
  label_ids: [],
  create_config_instance: false,
  service_type_name: '',
  instance_name: '',
  commit_message: '',
  _status: '',
  _error: '',
})

export default {
  name: 'BatchAddModal',
  props: {
    value: { type: Boolean, default: false },
    allLabels: { type: Array, default: () => [] },
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) },
    },
  },
  data() {
    return {
      rows: [newRow()],
      errors: [],
      saving: false,
      resultSummary: null,
    }
  },
  methods: {
    handleOpen() {
      this.rows = [newRow()]
      this.errors = []
      this.resultSummary = null
    },
    handleClose() {
      this.resultSummary = null
    },
    addRow() {
      this.rows.push(newRow())
    },
    removeRow(index) {
      this.rows.splice(index, 1)
      if (this.rows.length === 0) this.rows.push(newRow())
    },
    clearRows() {
      this.rows = [newRow()]
      this.errors = []
      this.resultSummary = null
    },
    validate() {
      this.errors = this.rows.map(row => {
        const e = {}
        if (!(row.fqdn || '').trim()) e.fqdn = '必填'
        if (!(row.ip || '').trim()) e.ip = '必填'
        return e
      })
      return this.errors.every(e => Object.keys(e).length === 0)
    },
    async handleSubmit() {
      if (!this.validate()) {
        this.$message.warning('请检查必填项')
        return
      }
      this.saving = true
      this.resultSummary = null

      let successCount = 0
      let failCount = 0

      for (let i = 0; i < this.rows.length; i++) {
        const row = this.rows[i]
        try {
          await createMdlServer({ ...row })
          this.$set(this.rows[i], '_status', 'ok')
          this.$set(this.rows[i], '_error', '')
          successCount++
        } catch (e) {
          const msg = (e.response && e.response.data && e.response.data.message) || e.message || '创建失败'
          this.$set(this.rows[i], '_status', 'error')
          this.$set(this.rows[i], '_error', msg)
          failCount++
        }
      }

      this.saving = false
      this.resultSummary = {
        type: failCount === 0 ? 'success' : (successCount === 0 ? 'error' : 'warning'),
        title: `完成：${successCount} 台成功，${failCount} 台失败`,
      }
      if (successCount > 0) {
        this.$emit('success')
      }
    },
  },
}
</script>
