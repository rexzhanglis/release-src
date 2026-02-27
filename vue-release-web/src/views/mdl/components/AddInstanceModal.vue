<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="新增配置实例"
    width="560px"
    :close-on-click-modal="false"
    @open="handleOpen"
    @closed="handleClosed"
  >
    <el-form
      ref="form"
      :model="form"
      :rules="rules"
      label-width="110px"
      size="small"
    >
      <el-form-item label="服务类型" prop="service_type_id">
        <el-select
          v-model="form.service_type_id"
          filterable
          allow-create
          placeholder="选择或输入新服务类型"
          style="width:100%"
          @change="handleServiceTypeChange"
        >
          <el-option
            v-for="st in serviceTypes"
            :key="st.id"
            :label="st.name"
            :value="st.id"
          />
        </el-select>
        <div style="font-size:11px;color:#909399;margin-top:3px">
          输入不存在的名称将自动创建新服务类型
        </div>
      </el-form-item>

      <el-form-item label="实例名称" prop="name">
        <el-input v-model="form.name" placeholder="如 10.121.21.243_19015" />
      </el-form-item>

      <el-form-item label="主机 IP" prop="host_ip">
        <el-input v-model="form.host_ip" placeholder="如 10.121.21.243" />
      </el-form-item>

      <el-form-item label="端口">
        <el-input-number v-model="form.port" :min="1" :max="65535" style="width:160px" placeholder="如 19015" />
      </el-form-item>

      <el-form-item label="配置文件" prop="consul_files">
        <el-input
          v-model="form.consul_files"
          placeholder="多个文件用逗号分隔，如 feeder_handler.cfg"
        />
        <div style="font-size:11px;color:#909399;margin-top:3px">
          同时会在数据库中为每个文件名创建空白 ConfigFile 记录
        </div>
      </el-form-item>

      <el-form-item label="安装目录">
        <el-input v-model="form.install_dir" placeholder="如 /datayes/app/bin" />
      </el-form-item>

      <el-form-item label="服务名">
        <el-input v-model="form.service_name" placeholder="如 mdl-forward" />
      </el-form-item>

      <el-form-item label="远端 Python">
        <el-input v-model="form.remote_python" placeholder="/usr/bin/python" />
      </el-form-item>
    </el-form>

    <div slot="footer">
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确认新增</el-button>
    </div>
  </el-dialog>
</template>

<script>
import { getServiceTypes, createConfigInstance, createConfigFile } from '@/api/configMgmt'
import request from '@/utils/request'

export default {
  name: 'AddInstanceModal',
  props: {
    value: { type: Boolean, default: false }
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(v) { this.$emit('input', v) }
    }
  },
  data() {
    return {
      serviceTypes: [],
      submitting: false,
      form: {
        service_type_id: null,
        name: '',
        host_ip: '',
        port: null,
        consul_files: 'feeder_handler.cfg',
        install_dir: '',
        service_name: '',
        remote_python: '/usr/bin/python',
      },
      rules: {
        service_type_id: [{ required: true, message: '请选择或输入服务类型', trigger: 'change' }],
        name: [{ required: true, message: '请输入实例名称', trigger: 'blur' }],
        host_ip: [{ required: true, message: '请输入主机 IP', trigger: 'blur' }],
        consul_files: [{ required: true, message: '请输入至少一个配置文件名', trigger: 'blur' }],
      }
    }
  },
  methods: {
    async handleOpen() {
      try {
        const res = await getServiceTypes()
        this.serviceTypes = res.data || []
      } catch (e) {
        this.$message.error('加载服务类型失败')
      }
    },
    handleClosed() {
      this.$refs.form && this.$refs.form.resetFields()
      this.form.port = null
      this.form.install_dir = ''
      this.form.service_name = ''
      this.form.remote_python = '/usr/bin/python'
    },
    handleServiceTypeChange(val) {
      // allow-create 时 val 可能是字符串（新输入的名称）
      // 不需要额外处理，提交时判断
    },
    async handleSubmit() {
      try {
        await this.$refs.form.validate()
      } catch { return }

      this.submitting = true
      try {
        let serviceTypeId = this.form.service_type_id

        // 如果是字符串（新输入的服务类型名），先创建
        if (typeof serviceTypeId === 'string') {
          const stRes = await request({
            url: '/config-mgmt/service-types/',
            method: 'post',
            data: { name: serviceTypeId }
          })
          serviceTypeId = stRes.data.id
        }

        // 创建实例
        const instRes = await createConfigInstance({
          service_type: serviceTypeId,
          name: this.form.name,
          host_ip: this.form.host_ip,
          port: this.form.port || null,
          consul_files: this.form.consul_files,
          install_dir: this.form.install_dir,
          service_name: this.form.service_name,
          remote_python: this.form.remote_python || '/usr/bin/python',
        })
        const instanceId = instRes.data.id

        // 为每个配置文件名创建空白 ConfigFile
        const filenames = this.form.consul_files.split(',').map(f => f.trim()).filter(Boolean)
        for (const filename of filenames) {
          await createConfigFile({
            instance: instanceId,
            filename,
            content: {},
          })
        }

        this.$message.success(`实例 ${this.form.name} 已新增，共创建 ${filenames.length} 个配置文件`)
        this.$emit('success')
        this.dialogVisible = false
      } catch (e) {
        const msg = (e.response && e.response.data &&
          (e.response.data.message || JSON.stringify(e.response.data))) || e.message
        this.$message.error('新增失败: ' + msg)
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>
