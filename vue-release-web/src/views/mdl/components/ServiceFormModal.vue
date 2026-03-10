<template>
  <el-dialog
    :title="isEdit ? '编辑服务实例' : '新增服务实例'"
    @open="onOpen"
    :visible.sync="visible"
    width="560px"
    :close-on-click-modal="false"
    @close="resetForm"
  >
    <el-form ref="form" :model="form" :rules="rules" label-width="110px" size="small">
      <el-form-item v-if="!isEdit && existingServices.length" label="从已有复制">
        <el-select
          v-model="copySourceId"
          placeholder="选择一个已有实例作为模板"
          clearable
          size="small"
          style="width:100%"
          @change="handleCopySource"
        >
          <el-option
            v-for="s in existingServices"
            :key="s.id"
            :label="s.service_name"
            :value="s.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="服务名" prop="service_name">
        <el-input v-model="form.service_name" placeholder="如 mdl-forward1" :disabled="isEdit" />
      </el-form-item>
      <el-form-item label="角色名称" prop="role_name">
        <el-input v-model="form.role_name" placeholder="如 forward" />
      </el-form-item>
      <el-form-item label="安装目录" prop="install_dir">
        <el-input v-model="form.install_dir" placeholder="/datayes/forward/bin" class="mono-input" />
      </el-form-item>
      <el-form-item label="备份目录" prop="backups_dir">
        <el-input v-model="form.backups_dir" placeholder="/datayes/forward/backup" class="mono-input" />
      </el-form-item>
      <el-form-item label="Consul 地址" prop="consul_space">
        <el-input v-model="form.consul_space" placeholder="如 http://10.x.x.x:8500/v1/kv/..." class="mono-input" />
      </el-form-item>
      <el-form-item label="Consul Token" prop="consul_token">
        <el-input v-model="form.consul_token" placeholder="Consul ACL Token" show-password />
      </el-form-item>
      <el-form-item label="配置文件" prop="consul_files">
        <el-input v-model="form.consul_files" placeholder="feeder_handler.cfg,feeder_receiver.cfg" />
        <div style="font-size:11px;color:#909399;margin-top:4px">多个文件用逗号分隔</div>
      </el-form-item>
      <el-form-item label="可执行文件名" prop="executable">
        <el-input v-model="form.executable" placeholder="feeder_handler" />
        <div style="font-size:11px;color:#909399;margin-top:4px">systemd ExecStart 中的可执行文件名</div>
      </el-form-item>
      <el-form-item label="配置 Git URL" prop="config_git_url">
        <el-input v-model="form.config_git_url" placeholder="生产环境填 Git 配置路径，staging 可留空" />
      </el-form-item>
    </el-form>
    <div slot="footer">
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
    </div>
  </el-dialog>
</template>

<script>
import { createMdlServer, updateMdlServer } from '@/api/mdlServer'
import { getConfigDefaults } from '@/api/configMgmt'

export default {
  name: 'ServiceFormModal',
  model: { prop: 'value', event: 'input' },
  props: {
    value: { type: Boolean, default: false },
    hostId: { type: [Number, String], required: true },
    server: { type: Object, default: null },
    existingServices: { type: Array, default: () => [] },
  },
  data() {
    return {
      saving: false,
      copySourceId: null,
      form: {
        service_name: '',
        role_name: '',
        install_dir: '',
        backups_dir: '',
        consul_space: '',
        consul_token: '',
        consul_files: 'feeder_handler.cfg',
        executable: 'feeder_handler',
        config_git_url: '',
      },
      rules: {
        service_name: [{ required: true, message: '请输入服务名', trigger: 'blur' }],
        install_dir: [{ required: true, message: '请输入安装目录', trigger: 'blur' }],
        consul_space: [{ required: true, message: '请输入 Consul 地址', trigger: 'blur' }],
        consul_token: [{ required: true, message: '请输入 Consul Token', trigger: 'blur' }],
      },
    }
  },
  computed: {
    visible: {
      get() { return this.value },
      set(v) { this.$emit('input', v) },
    },
    isEdit() { return !!(this.server && this.server.id) },
  },
  watch: {
    value(v) {
      if (v) {
        if (this.server) {
          this.form = {
            service_name: this.server.service_name || '',
            role_name: this.server.role_name || '',
            install_dir: this.server.install_dir || '',
            backups_dir: this.server.backups_dir || '',
            consul_space: this.server.consul_space || '',
            consul_token: this.server.consul_token || '',
            consul_files: this.server.consul_files || 'feeder_handler.cfg',
            executable: this.server.executable || 'feeder_handler',
            config_git_url: this.server.config_git_url || '',
          }
        } else {
          this.resetForm()
        }
      }
    },
  },
  methods: {
    onOpen() {
      this.copySourceId = null
      if (!this.isEdit) {
        getConfigDefaults().then(res => {
          const d = res.data || {}
          if (d.consul_token && !this.form.consul_token) this.form.consul_token = d.consul_token
          if (d.config_git_url && !this.form.config_git_url) this.form.config_git_url = d.config_git_url
        }).catch(() => {})
      }
    },
    resetForm() {
      this.copySourceId = null
      this.gitImportId = null
      this.form = {
        service_name: '',
        role_name: '',
        install_dir: '',
        backups_dir: '',
        consul_space: '',
        consul_token: '',
        consul_files: 'feeder_handler.cfg',
        executable: 'feeder_handler',
        config_git_url: '',
      }
      this.$nextTick(() => { this.$refs.form && this.$refs.form.clearValidate() })
    },
    handleCopySource(id) {
      if (!id) return
      const src = this.existingServices.find(s => s.id === id)
      if (!src) return
      this.form = {
        service_name: '',
        role_name: src.role_name || '',
        install_dir: src.install_dir || '',
        backups_dir: src.backups_dir || '',
        consul_space: src.consul_space || '',
        consul_token: src.consul_token || '',
        consul_files: src.consul_files || 'feeder_handler.cfg',
        executable: src.executable || 'feeder_handler',
        config_git_url: src.config_git_url || '',
      }
      this.$nextTick(() => { this.$refs.form && this.$refs.form.clearValidate() })
    },
    async handleSubmit() {
      try {
        await this.$refs.form.validate()
      } catch { return }
      this.saving = true
      try {
        if (this.isEdit) {
          await updateMdlServer(this.server.id, this.form)
          this.$message.success('更新成功')
        } else {
          const res = await createMdlServer({ ...this.form, host_id: this.hostId })
          this.$message.success('新增成功')
          this.$emit('created', res.data)
        }
        this.visible = false
        this.$emit('success')
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

<style scoped>
.mono-input >>> input {
  font-family: monospace;
  font-size: 12px;
}
</style>
