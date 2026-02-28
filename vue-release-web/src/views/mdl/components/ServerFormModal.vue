<template>
  <el-dialog
    :visible.sync="dialogVisible"
    :title="isEdit ? '编辑服务器' : '新增服务器'"
    width="700px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @close="resetForm"
  >
    <el-form
      ref="form"
      :model="form"
      :rules="rules"
      label-width="120px"
      size="small"
    >
      <!-- ===== 复制已有服务器 ===== -->
      <template v-if="!isEdit">
        <el-form-item label="复制已有服务器" label-width="120px" style="margin-bottom:10px">
          <el-select
            v-model="cloneServerId"
            placeholder="选择参考服务器，自动填充字段（可选）"
            clearable
            filterable
            style="width:100%"
            @change="handleClone"
          >
            <el-option
              v-for="s in serverOptions"
              :key="s.id"
              :label="`${s.fqdn} (${s.ip})`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-divider style="margin:4px 0 12px" />
      </template>

      <!-- ===== 基础信息 ===== -->
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="FQDN" prop="fqdn">
            <el-input v-model="form.fqdn" placeholder="如 mdl-fwd-prod01" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="IP 地址" prop="ip">
            <el-input v-model="form.ip" placeholder="如 10.121.21.240" @input="autoFillConfig" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="服务名" prop="service_name">
            <el-input v-model="form.service_name" placeholder="如 mdl-forward" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="角色名" prop="role_name">
            <el-input v-model="form.role_name" placeholder="如 forward" @input="autoFillConfig" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="SSH 用户" prop="user">
            <el-input v-model="form.user" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="远端 Python" prop="remote_python">
            <el-input v-model="form.remote_python" placeholder="/opt/anaconda/bin/python" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="安装目录" prop="install_dir">
            <el-input v-model="form.install_dir" placeholder="/datayes/forward/bin" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="备份目录" prop="backups_dir">
            <el-input v-model="form.backups_dir" placeholder="/datayes/forward/backup" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="Consul KV 前缀" prop="consul_space">
        <el-input v-model="form.consul_space" placeholder="如 /kv/configs/mdl/forward/forward_prod01" />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="Consul Token" prop="consul_token">
            <el-input v-model="form.consul_token" type="password" show-password placeholder="Consul 认证 Token" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="配置文件" prop="consul_files">
            <el-input v-model="form.consul_files" placeholder="feeder_handler.cfg" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="Git 配置链接" prop="config_git_url">
        <el-input v-model="form.config_git_url" placeholder="可选，生产环境 Git 配置文件链接" />
      </el-form-item>

      <el-form-item label="标签">
        <el-select
          v-model="form.label_ids"
          multiple
          filterable
          placeholder="选择标签（可多选）"
          style="width:100%"
        >
          <el-option
            v-for="lbl in allLabels"
            :key="lbl.id"
            :label="lbl.name"
            :value="lbl.id"
          />
        </el-select>
      </el-form-item>

      <!-- ===== 新增时：同步创建配置实例选项 ===== -->
      <template v-if="!isEdit">
        <el-divider style="margin:14px 0 10px" />
        <el-form-item label-width="0" style="margin-bottom:8px">
          <el-checkbox v-model="form.create_config_instance">
            <span style="font-weight:600">同时创建配置实例并提交 Git</span>
            <span style="color:#909399;font-size:12px;margin-left:6px">
              在配置管理中创建对应节点，并将空配置文件提交到 GitLab
            </span>
          </el-checkbox>
        </el-form-item>

        <template v-if="form.create_config_instance">
          <el-form-item label="服务类型" prop="service_type_name">
            <el-input
              v-model="form.service_type_name"
              placeholder="Git 仓库一级目录，如 aliforward、forward"
              style="width:260px"
            />
            <span style="margin-left:8px;color:#909399;font-size:12px">对应配置管理树的顶级节点</span>
          </el-form-item>

          <el-form-item label="实例名称" prop="instance_name">
            <el-input
              v-model="form.instance_name"
              placeholder="如 10_121_21_240_19015"
              style="width:260px"
            />
            <span style="margin-left:8px;color:#909399;font-size:12px">Git 仓库二级目录，通常为 IP_端口</span>
          </el-form-item>

          <el-form-item label="Commit 说明">
            <el-input
              v-model="form.commit_message"
              placeholder="留空自动生成"
              style="width:340px"
            />
          </el-form-item>
        </template>
      </template>
    </el-form>

    <!-- 提交结果展示（保存完成后显示，替换保存按钮） -->
    <div v-if="submitResult" style="margin-top:12px">
      <el-alert
        :type="submitResult.type"
        :title="submitResult.title"
        :closable="false"
        show-icon
      >
        <div slot="default">
          <div v-for="(d, i) in submitResult.details" :key="i" style="font-size:12px;margin-top:3px">{{ d }}</div>
        </div>
      </el-alert>
    </div>

    <div slot="footer">
      <el-button @click="dialogVisible = false">{{ submitResult ? '关闭' : '取消' }}</el-button>
      <el-button
        v-if="!submitResult"
        type="primary"
        :loading="saving"
        @click="handleSubmit"
      >保存</el-button>
    </div>
  </el-dialog>
</template>

<script>
import { createMdlServer, updateMdlServer, getMdlServers } from '@/api/mdlServer'

const DEFAULT_FORM = () => ({
  fqdn: '',
  ip: '',
  role_name: 'forward',
  user: 'root',
  remote_python: '/opt/anaconda/bin/python',
  service_name: 'mdl-forward',
  install_dir: '/datayes/forward/bin',
  backups_dir: '/datayes/forward/backup',
  consul_space: '',
  consul_token: '',
  consul_files: 'feeder_handler.cfg',
  config_git_url: '',
  label_ids: [],
  // 新增时额外字段
  create_config_instance: true,
  service_type_name: '',
  instance_name: '',
  commit_message: '',
})

export default {
  name: 'ServerFormModal',
  props: {
    value: { type: Boolean, default: false },
    server: { type: Object, default: null },
    allLabels: { type: Array, default: () => [] },
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) },
    },
    isEdit() { return !!(this.server && this.server.id) },
  },
  data() {
    return {
      saving: false,
      submitResult: null,
      form: DEFAULT_FORM(),
      cloneServerId: null,
      serverOptions: [],
      rules: {
        fqdn:         [{ required: true, message: '请填写 FQDN', trigger: 'blur' }],
        ip:           [{ required: true, message: '请填写 IP 地址', trigger: 'blur' }],
        user:         [{ required: true, message: '请填写 SSH 用户', trigger: 'blur' }],
        service_name: [{ required: true, message: '请填写服务名', trigger: 'blur' }],
        install_dir:  [{ required: true, message: '请填写安装目录', trigger: 'blur' }],
        backups_dir:  [{ required: true, message: '请填写备份目录', trigger: 'blur' }],
        service_type_name: [{
          validator: (rule, val, cb) => {
            if (this.form.create_config_instance && !(val || '').trim()) {
              cb(new Error('请填写服务类型'))
            } else { cb() }
          }, trigger: 'blur'
        }],
        instance_name: [{
          validator: (rule, val, cb) => {
            if (this.form.create_config_instance && !(val || '').trim()) {
              cb(new Error('请填写实例名称'))
            } else { cb() }
          }, trigger: 'blur'
        }],
      },
    }
  },
  methods: {
    async fetchServerOptions() {
      try {
        const res = await getMdlServers({ page_size: 500 })
        const data = res.data
        const list = Array.isArray(data) ? data
          : (data && Array.isArray(data.results)) ? data.results : []
        this.serverOptions = list
      } catch {}
    },
    handleClone(id) {
      if (!id) return
      const src = this.serverOptions.find(s => s.id === id)
      if (!src) return
      // 只覆盖非 FQDN/IP 的字段，FQDN 和 IP 留给用户填写
      this.form.role_name      = src.role_name      || this.form.role_name
      this.form.user           = src.user           || this.form.user
      this.form.remote_python  = src.remote_python  || this.form.remote_python
      this.form.service_name   = src.service_name   || this.form.service_name
      this.form.install_dir    = src.install_dir    || this.form.install_dir
      this.form.backups_dir    = src.backups_dir    || this.form.backups_dir
      this.form.consul_space   = src.consul_space   || this.form.consul_space
      this.form.consul_token   = src.consul_token   || this.form.consul_token
      this.form.consul_files   = src.consul_files   || this.form.consul_files
      this.form.config_git_url = src.config_git_url || this.form.config_git_url
      this.form.label_ids      = (src.labels || []).map(l => l.id)
      this.$message.info('已填充参考服务器配置，请修改 FQDN 和 IP 地址')
    },
    handleOpen() {
      this.submitResult = null
      this.cloneServerId = null
      if (this.isEdit) {
        const s = this.server
        this.form = {
          fqdn: s.fqdn || '',
          ip: s.ip || '',
          role_name: s.role_name || 'forward',
          user: s.user || 'root',
          remote_python: s.remote_python || '/opt/anaconda/bin/python',
          service_name: s.service_name || 'mdl-forward',
          install_dir: s.install_dir || '/datayes/forward/bin',
          backups_dir: s.backups_dir || '/datayes/forward/backup',
          consul_space: s.consul_space || '',
          consul_token: s.consul_token || '',
          consul_files: s.consul_files || 'feeder_handler.cfg',
          config_git_url: s.config_git_url || '',
          label_ids: (s.labels || []).map(l => l.id),
          create_config_instance: false,
          service_type_name: '',
          instance_name: '',
          commit_message: '',
        }
      } else {
        this.form = DEFAULT_FORM()
        this.fetchServerOptions()
      }
    },
    resetForm() {
      this.submitResult = null
      this.$nextTick(() => {
        if (this.$refs.form) this.$refs.form.clearValidate()
      })
    },
    // IP / 角色名变化时自动填充实例名和服务类型（辅助提示，用户可覆盖）
    autoFillConfig() {
      if (this.form.ip && !this.form.instance_name) {
        this.form.instance_name = this.form.ip.replace(/\./g, '_')
      }
      if (this.form.role_name && !this.form.service_type_name) {
        this.form.service_type_name = this.form.role_name
      }
    },
    async handleSubmit() {
      try {
        await this.$refs.form.validate()
      } catch {
        return
      }
      this.saving = true
      try {
        if (this.isEdit) {
          await updateMdlServer(this.server.id, this.form)
          this.$message.success('保存成功')
          this.$emit('success')
          this.dialogVisible = false
        } else {
          const res = await createMdlServer({
            ...this.form,
            git_commit: this.form.create_config_instance,
          })
          const data = (res.data && res.data.data) || {}

          // 构建结果详情
          const details = []
          if (data.config_instance) {
            if (data.config_instance.error) {
              details.push(`⚠ 配置实例创建失败: ${data.config_instance.error}`)
            } else {
              details.push(`✓ 配置实例: ${data.config_instance.service_type}/${data.config_instance.name}`)
              details.push(`✓ 配置文件: ${(data.config_instance.files || []).join(', ')}`)
            }
          }
          if (data.git) {
            const gitOk = data.git.results && data.git.results.every(r => r.status === 'ok')
            details.push(`${gitOk ? '✓' : '⚠'} Git: ${data.git.message}`)
          }

          const hasError = !!(data.config_instance && data.config_instance.error) ||
            !!(data.git && data.git.results && data.git.results.some(r => r.status !== 'ok'))

          this.submitResult = {
            type: hasError ? 'warning' : 'success',
            title: hasError ? '服务器已新增，但部分步骤失败' : '新增成功',
            details,
          }
          this.$emit('success')
        }
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '操作失败'
        this.$message.error(msg)
      } finally {
        this.saving = false
      }
    },
  },
}
</script>
