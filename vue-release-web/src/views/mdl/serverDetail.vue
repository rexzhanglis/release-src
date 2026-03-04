<template>
  <div class="server-detail">
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:16px;font-size:13px">
      <el-breadcrumb-item :to="{ name: 'mdlServers' }">服务器管理</el-breadcrumb-item>
      <el-breadcrumb-item>{{ server ? server.fqdn : '加载中...' }}</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 基本信息卡片 -->
    <el-card v-if="server" shadow="never" style="margin-bottom:16px">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">{{ server.fqdn }}</span>
        <el-tag :type="statusType" size="small" effect="plain">{{ statusLabel }}</el-tag>
      </div>
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="IP 地址">{{ server.ip }}</el-descriptions-item>
        <el-descriptions-item label="服务名">{{ server.service_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SSH 用户">{{ server.user || 'root' }}</el-descriptions-item>
        <el-descriptions-item label="安装目录">
          <span class="mono">{{ server.install_dir || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="备份目录">
          <span class="mono">{{ server.backups_dir || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="Python 路径">
          <span class="mono">{{ server.remote_python || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="标签">
          <el-tag
            v-for="lbl in (server.labels || [])"
            :key="lbl.id"
            size="mini"
            style="margin-right:4px"
          >{{ lbl.name }}</el-tag>
          <span v-if="!server.labels || server.labels.length === 0" style="color:#c0c4cc">-</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- systemd 服务 -->
    <el-card shadow="never">
      <div slot="header" style="display:flex;align-items:center;justify-content:space-between">
        <span style="font-weight:600">systemd 服务</span>
        <el-button
          size="small"
          icon="el-icon-refresh"
          :loading="loading"
          @click="fetchServices"
        >刷新</el-button>
      </div>

      <div v-if="!server" style="text-align:center;padding:40px 0;color:#909399">
        <i class="el-icon-loading" style="font-size:24px"></i>
        <p style="margin-top:8px">加载中...</p>
      </div>
      <template v-else>
        <!-- 搜索 -->
        <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center">
          <el-input
            v-model="svcSearch"
            placeholder="过滤服务名"
            clearable
            size="small"
            prefix-icon="el-icon-search"
            style="width:220px"
          />
          <el-select
            v-model="svcStateFilter"
            placeholder="运行状态"
            clearable
            size="small"
            style="width:120px"
          >
            <el-option label="active" value="active" />
            <el-option label="inactive" value="inactive" />
            <el-option label="failed" value="failed" />
          </el-select>
          <span style="font-size:12px;color:#909399;margin-left:auto">
            共 {{ filteredServices.length }} / {{ serviceList.length }} 个服务
          </span>
        </div>

        <el-table
          v-loading="loading"
          :data="filteredServices"
          border
          size="small"
          max-height="560"
        >
          <el-table-column prop="name" label="服务名" min-width="220" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span class="mono" style="font-size:12px">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="运行状态" width="100" align="center">
            <template slot-scope="{ row }">
              <el-tag
                :type="row.active_state === 'active' ? 'success' : row.active_state === 'failed' ? 'danger' : 'info'"
                size="mini"
              >{{ row.active_state }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="子状态" width="90" align="center">
            <template slot-scope="{ row }">
              <span style="font-size:11px;color:#909399">{{ row.sub_state }}</span>
            </template>
          </el-table-column>
          <el-table-column label="自启动" width="90" align="center">
            <template slot-scope="{ row }">
              <el-tag
                v-if="row.enabled !== null"
                :type="row.enabled === 'enabled' ? 'success' : 'info'"
                size="mini"
              >{{ row.enabled === 'enabled' ? '已启用' : row.enabled || '-' }}</el-tag>
              <span v-else style="color:#c0c4cc;font-size:11px">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span style="font-size:11px;color:#606266">{{ row.description }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" align="center" fixed="right">
            <template slot-scope="{ row }">
              <el-button
                v-if="row.active_state !== 'active'"
                size="mini" type="text" style="color:#67c23a"
                @click="handleControl(row, 'start')"
              >启动</el-button>
              <el-button
                v-else
                size="mini" type="text" style="color:#e6a23c"
                @click="handleControl(row, 'stop')"
              >停止</el-button>
              <el-button
                v-if="row.active_state === 'active'"
                size="mini" type="text"
                @click="handleControl(row, 'restart')"
              >重启</el-button>
              <el-divider direction="vertical" />
              <el-button
                v-if="row.enabled !== 'enabled'"
                size="mini" type="text" style="color:#409eff"
                @click="handleControl(row, 'enable')"
              >自启</el-button>
              <el-button
                v-else
                size="mini" type="text" style="color:#f56c6c"
                @click="handleControl(row, 'disable')"
              >禁用</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!loading && serviceList.length === 0" style="text-align:center;padding:40px 0;color:#909399">
          <i class="el-icon-tickets" style="font-size:40px;color:#dcdfe6"></i>
          <p style="margin-top:8px;font-size:13px">未查询到 systemd 服务</p>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script>
import { getMdlServer, getSystemdServices, controlSystemdService } from '@/api/mdlServer'

export default {
  name: 'ServerDetail',
  data() {
    return {
      server: null,
      serviceList: [],
      loading: false,
      svcSearch: '',
      svcStateFilter: '',
    }
  },
  computed: {
    serverId() {
      return this.$route.params.id
    },
    statusLabel() {
      const map = { uninitialized: '未初始化', initializing: '初始化中', ready: '运行中', failed: '初始化失败', retired: '已退役' }
      return map[this.server && this.server.init_status] || '未知'
    },
    statusType() {
      const map = { uninitialized: 'info', initializing: 'warning', ready: 'success', failed: 'danger', retired: '' }
      return map[this.server && this.server.init_status] || 'info'
    },
    filteredServices() {
      return this.serviceList.filter(s => {
        const matchName = !this.svcSearch || s.name.includes(this.svcSearch)
        const matchState = !this.svcStateFilter || s.active_state === this.svcStateFilter
        return matchName && matchState
      })
    },
  },
  created() {
    this.fetchServer()
  },
  methods: {
    async fetchServer() {
      try {
        const res = await getMdlServer(this.serverId)
        this.server = res.data
        this.fetchServices()
      } catch (e) {
        this.$message.error('加载服务器信息失败')
      }
    },

    async fetchServices() {
      if (!this.server) return
      this.loading = true
      try {
        const res = await getSystemdServices(this.serverId)
        this.serviceList = (res.data && res.data.services) || []
      } catch (e) {
        this.$message.error('获取 systemd 服务列表失败：' + (e.message || ''))
      } finally {
        this.loading = false
      }
    },

    async handleControl(svc, action) {
      try {
        await this.$confirm(
          `确认对「${svc.name}」执行 ${action}？`,
          '确认操作',
          { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        const res = await controlSystemdService(this.serverId, { service: svc.name, action })
        if (res.data && res.data.ok) {
          this.$message.success(`${action} 成功`)
          await this.fetchServices()
        } else {
          this.$message.error(`${action} 失败：` + ((res.data && res.data.output) || ''))
        }
      } catch (e) {
        this.$message.error('操作失败：' + (e.message || ''))
      }
    },
  },
}
</script>

<style scoped>
.server-detail {
  padding: 16px;
}
.mono {
  font-family: monospace;
  font-size: 12px;
}
</style>
