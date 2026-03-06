<template>
  <div>
    <el-dialog
      :title="isEdit ? '编辑机器' : '新增机器'"
      :visible.sync="visible"
      width="480px"
      :close-on-click-modal="false"
      @close="resetForm"
    >
      <el-form ref="form" :model="form" :rules="rules" label-width="110px" size="small">
        <el-form-item label="FQDN" prop="fqdn">
          <el-input v-model="form.fqdn" placeholder="如 mdl-fwd-test01.wmcloud.com" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="IP 地址" prop="ip">
          <el-input v-model="form.ip" placeholder="如 10.24.71.77" />
        </el-form-item>
        <el-form-item label="SSH 用户" prop="user">
          <el-input v-model="form.user" placeholder="默认 root" />
        </el-form-item>
        <el-form-item label="远端 Python" prop="remote_python">
          <el-input v-model="form.remote_python" placeholder="/usr/bin/python3" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
      </div>
    </el-dialog>

    <!-- 新增机器后自动弹出服务器初始化弹窗 -->
    <host-init-modal
      v-model="showInitModal"
      :host="createdHost"
      @done="handleInitDone"
    />
  </div>
</template>

<script>
import { createHost, updateHost } from '@/api/mdlServer'
import HostInitModal from './HostInitModal'

export default {
  name: 'HostFormModal',
  components: { HostInitModal },
  model: { prop: 'value', event: 'input' },
  props: {
    value: { type: Boolean, default: false },
    host: { type: Object, default: null },
  },
  data() {
    return {
      saving: false,
      form: {
        fqdn: '',
        ip: '',
        user: 'root',
        remote_python: '/usr/bin/python3',
      },
      rules: {
        fqdn: [{ required: true, message: '请输入 FQDN', trigger: 'blur' }],
        ip: [{ required: true, message: '请输入 IP 地址', trigger: 'blur' }],
      },
      showInitModal: false,
      createdHost: null,
    }
  },
  computed: {
    visible: {
      get() { return this.value },
      set(v) { this.$emit('input', v) },
    },
    isEdit() { return !!(this.host && this.host.id) },
  },
  watch: {
    value(v) {
      if (v) {
        if (this.host) {
          this.form = {
            fqdn: this.host.fqdn || '',
            ip: this.host.ip || '',
            user: this.host.user || 'root',
            remote_python: this.host.remote_python || '/usr/bin/python3',
          }
        } else {
          this.resetForm()
        }
      }
    },
  },
  methods: {
    resetForm() {
      this.form = { fqdn: '', ip: '', user: 'root', remote_python: '/usr/bin/python3' }
      this.$nextTick(() => { this.$refs.form && this.$refs.form.clearValidate() })
    },
    async handleSubmit() {
      try {
        await this.$refs.form.validate()
      } catch { return }
      this.saving = true
      try {
        if (this.isEdit) {
          await updateHost(this.host.id, this.form)
          this.$message.success('更新成功')
          this.visible = false
          this.$emit('success')
        } else {
          const res = await createHost(this.form)
          this.visible = false
          this.$emit('success')
          // 新增机器后提示并弹出初始化弹窗
          this.$confirm('机器已创建，是否立即进行服务器系统环境初始化？', '新增成功', {
            confirmButtonText: '立即初始化',
            cancelButtonText: '稍后手动初始化',
            type: 'success',
          }).then(() => {
            this.createdHost = res.data && res.data.data ? res.data.data : res.data
            this.showInitModal = true
          }).catch(() => {})
        }
      } catch (e) {
        const msg = (e.response && e.response.data && e.response.data.message) || e.message || '操作失败'
        this.$message.error(msg)
      } finally {
        this.saving = false
      }
    },
    handleInitDone(status) {
      if (status === 'success') {
        this.$emit('success')
      }
    },
  },
}
</script>
