<template>
  <div class="msg-chain">
    <!-- 查询栏 -->
    <el-card shadow="never" class="search-card">
      <div class="search-bar">
        <span class="search-label">消息号</span>
        <el-select
          v-model="serviceId"
          placeholder="Service ID（可选）"
          clearable
          filterable
          size="small"
          style="width:280px"
        >
          <el-option
            v-for="s in serviceList"
            :key="s.service_id"
            :label="s.label"
            :value="s.service_id"
          />
        </el-select>
        <span style="margin:0 6px;color:#909399">.</span>
        <el-input
          v-model="msgId"
          placeholder="Message ID，如 53"
          size="small"
          style="width:160px"
          clearable
          @keyup.enter.native="handleQuery"
        />
        <el-button
          type="primary"
          size="small"
          icon="el-icon-search"
          :loading="loading"
          style="margin-left:12px"
          @click="handleQuery"
        >查询</el-button>
        <span v-if="queryLabel" class="query-label">
          查询：<b>{{ queryLabel }}</b>
        </span>
      </div>
      <div class="search-tip">
        格式示例：Service ID 选 <b>6</b>，Message ID 填 <b>53</b> → 查询 <b>6.53</b>（深L2 第53号消息）；
        不选 Service ID 则匹配所有 Service 下的该 Message ID。
      </div>
    </el-card>

    <!-- 结果区 -->
    <div v-if="result" class="result-area">
      <!-- 统计摘要 -->
      <el-row :gutter="12" style="margin-bottom:16px">
        <el-col :span="8">
          <el-card shadow="never" class="stat-card stat-config">
            <div class="stat-num">{{ result.config.length }}</div>
            <div class="stat-desc">配置文件中的转发机</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="stat-card stat-live">
            <div class="stat-num">{{ result.live.length }}</div>
            <div class="stat-desc">实时活跃订阅连接</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="stat-card stat-warn">
            <div class="stat-num">{{ result.unreachable.length }}</div>
            <div class="stat-desc">无法连接的服务器</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <!-- 左：配置文件来源 -->
        <el-col :span="12">
          <el-card shadow="never">
            <div slot="header" class="card-header">
              <i class="el-icon-document" style="color:#409eff" />
              <span>配置文件（静态）</span>
              <el-tag size="mini" type="info" style="margin-left:8px">feeder_handler.cfg</el-tag>
            </div>
            <div v-if="result.config.length === 0" class="empty-tip">
              未找到包含该消息的配置
            </div>
            <el-table v-else :data="result.config" border size="small">
              <el-table-column label="转发机实例" min-width="160" show-overflow-tooltip>
                <template slot-scope="{ row }">
                  <span class="mono">{{ row.fqdn }}</span>
                </template>
              </el-table-column>
              <el-table-column label="消息" width="80" align="center">
                <template slot-scope="{ row }">
                  <el-tag size="mini" type="primary">{{ row.msg_label }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="服务名" min-width="140" show-overflow-tooltip>
                <template slot-scope="{ row }">
                  <span style="font-size:11px;color:#606266">{{ row.service_name }}</span>
                </template>
              </el-table-column>
              <el-table-column label="上游地址" min-width="160" show-overflow-tooltip>
                <template slot-scope="{ row }">
                  <span class="mono" style="font-size:11px">{{ row.upstream_address }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>

        <!-- 右：实时订阅 -->
        <el-col :span="12">
          <el-card shadow="never">
            <div slot="header" class="card-header">
              <i class="el-icon-connection" style="color:#67c23a" />
              <span>实时订阅（heartbeat）</span>
              <el-tag size="mini" type="success" style="margin-left:8px">当前连接</el-tag>
            </div>
            <div v-if="result.live.length === 0" class="empty-tip">
              当前无下游订阅该消息
            </div>
            <el-table v-else :data="result.live" border size="small">
              <el-table-column label="转发机" width="130" show-overflow-tooltip>
                <template slot-scope="{ row }">
                  <span class="mono" style="font-size:11px">{{ row.forwarder_ip }}</span>
                </template>
              </el-table-column>
              <el-table-column label="客户端地址" min-width="180" show-overflow-tooltip>
                <template slot-scope="{ row }">
                  <span class="mono" style="font-size:11px">{{ row.client_address }}</span>
                </template>
              </el-table-column>
              <el-table-column label="订阅消息" width="90" align="center">
                <template slot-scope="{ row }">
                  <el-tag
                    v-for="sub in row.matched_subscriptions"
                    :key="sub.label"
                    size="mini"
                    type="success"
                    style="margin:1px"
                  >{{ sub.label }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="连接时间" width="110">
                <template slot-scope="{ row }">
                  <span style="font-size:11px;color:#909399">{{ row.start_date }}<br>{{ row.start_time }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- 无法连接的服务器 -->
      <el-card v-if="result.unreachable.length > 0" shadow="never" style="margin-top:16px">
        <div slot="header" class="card-header">
          <i class="el-icon-warning" style="color:#e6a23c" />
          <span>无法连接（heartbeat 超时）</span>
        </div>
        <el-table :data="result.unreachable" border size="small">
          <el-table-column prop="ip" label="IP" width="140" />
          <el-table-column prop="fqdn" label="FQDN" min-width="180" show-overflow-tooltip />
          <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip>
            <template slot-scope="{ row }">
              <span style="color:#f56c6c;font-size:11px">{{ row.error }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-placeholder">
      <i class="el-icon-share" style="font-size:48px;color:#dcdfe6" />
      <p style="color:#909399;margin-top:12px">输入消息号后点击查询，查看转发链路</p>
    </div>
  </div>
</template>

<script>
import { queryMsgChain, getServices } from '@/api/forwarderChain'

export default {
  name: 'MsgChain',
  data() {
    return {
      serviceList: [],
      serviceId: null,
      msgId: '',
      loading: false,
      result: null,
      queryLabel: '',
    }
  },
  created() {
    this.fetchServices()
    // 支持从路由参数直接带入查询，如从其他页面跳转
    const { msg } = this.$route.query
    if (msg) {
      const parts = msg.split('.')
      if (parts.length === 2) {
        this.serviceId = parseInt(parts[0]) || null
        this.msgId = parts[1]
      } else {
        this.msgId = msg
      }
      this.handleQuery()
    }
  },
  methods: {
    async fetchServices() {
      try {
        const res = await getServices()
        this.serviceList = res.data || []
      } catch {}
    },

    async handleQuery() {
      const mid = this.msgId.trim()
      if (!mid) {
        this.$message.warning('请输入 Message ID')
        return
      }
      const msg = this.serviceId ? `${this.serviceId}.${mid}` : mid
      this.loading = true
      this.result = null
      this.queryLabel = ''
      try {
        const res = await queryMsgChain(msg)
        const d = res.data
        this.result = d
        const q = d.query || {}
        this.queryLabel = q.service_label
          ? `${q.service_id}.${q.msg_id}（${q.service_label}）`
          : `所有 Service 下的 msg ${q.msg_id}`
      } catch (e) {
        this.$message.error('查询失败：' + (e.message || '未知错误'))
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.msg-chain {
  padding: 16px;
}
.search-card {
  margin-bottom: 16px;
}
.search-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.search-label {
  font-size: 13px;
  color: #606266;
  margin-right: 6px;
}
.search-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}
.query-label {
  margin-left: 16px;
  font-size: 13px;
  color: #409eff;
}
.result-area {
  margin-top: 4px;
}
.stat-card {
  text-align: center;
  padding: 8px 0;
}
.stat-num {
  font-size: 32px;
  font-weight: bold;
  line-height: 1.2;
}
.stat-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.stat-config .stat-num { color: #409eff; }
.stat-live .stat-num   { color: #67c23a; }
.stat-warn .stat-num   { color: #e6a23c; }
.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: bold;
}
.empty-tip {
  text-align: center;
  color: #c0c4cc;
  padding: 24px 0;
  font-size: 13px;
}
.empty-placeholder {
  text-align: center;
  padding: 80px 0;
}
.mono {
  font-family: 'Consolas', 'Monaco', monospace;
}
</style>
