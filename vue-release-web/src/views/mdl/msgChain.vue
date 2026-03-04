<template>
  <div class="msg-chain">
    <!-- 查询栏 -->
    <el-card shadow="never" class="search-card">
      <div class="search-bar">
        <span class="search-label">消息号</span>
        <el-select
          v-model="serviceId"
          placeholder="Service ID（可选）"
          clearable filterable size="small" style="width:280px"
        >
          <el-option v-for="s in serviceList" :key="s.service_id" :label="s.label" :value="s.service_id" />
        </el-select>
        <span style="margin:0 6px;color:#909399">.</span>
        <el-input
          v-model="msgId"
          placeholder="Message ID，如 53"
          size="small" style="width:160px" clearable
          @keyup.enter.native="handleQuery"
        />
        <el-button type="primary" size="small" icon="el-icon-search"
          :loading="loading" style="margin-left:12px" @click="handleQuery">查询</el-button>
        <span v-if="queryLabel" class="query-label">查询：<b>{{ queryLabel }}</b></span>
      </div>
      <div class="search-tip">
        选 Service ID + 填 Message ID 查询完整转发链路，不选 Service ID 则匹配所有 Service。
      </div>
    </el-card>

    <div v-if="result" class="result-area">
      <!-- 统计 -->
      <el-row :gutter="12" style="margin-bottom:16px">
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#409eff">{{ result.chains.length }}</div>
            <div class="stat-desc">条完整链路</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#67c23a">{{ result.live.length }}</div>
            <div class="stat-desc">实时活跃订阅</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#909399">{{ Object.keys(result.nodes).length }}</div>
            <div class="stat-desc">涉及节点数</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#e6a23c">{{ result.unreachable.length }}</div>
            <div class="stat-desc">无法连接</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 完整链路 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <div slot="header" class="card-header">
          <i class="el-icon-sort" style="color:#409eff" />
          <span>完整转发链路（配置文件追溯）</span>
          <el-tag size="mini" type="info" style="margin-left:8px">从源头到转发机</el-tag>
        </div>

        <div v-if="result.chains.length === 0" class="empty-tip">
          未找到包含该消息的配置
        </div>

        <div v-for="(chain, ci) in result.chains" :key="ci" class="chain-row">
          <span class="chain-index">链路 {{ ci + 1 }}</span>
          <div class="chain-nodes">
            <template v-for="(node, ni) in chain">
              <!-- 节点 -->
              <div :key="'n' + ni" class="chain-node" :class="nodeClass(node)">
                <div class="node-type-tag">{{ nodeTypeLabel(node) }}</div>
                <div class="node-ip">{{ node.node }}</div>
                <div class="node-instance" :title="node.instance">{{ node.instance }}</div>
                <div v-if="node.services && node.services.length" class="node-services">
                  <el-tag
                    v-for="s in node.services" :key="s.service_name"
                    size="mini" type="primary" style="margin:1px 1px 0 0"
                  >{{ s.msg_label }}</el-tag>
                </div>
              </div>
              <!-- 箭头 -->
              <div v-if="ni < chain.length - 1" :key="'a' + ni" class="chain-arrow">→</div>
            </template>
          </div>
        </div>
      </el-card>

      <!-- 实时订阅 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <div slot="header" class="card-header">
          <i class="el-icon-connection" style="color:#67c23a" />
          <span>实时订阅（heartbeat）</span>
          <el-tag size="mini" type="success" style="margin-left:8px">当前连接</el-tag>
        </div>
        <div v-if="result.live.length === 0" class="empty-tip">当前无下游订阅该消息</div>
        <el-table v-else :data="result.live" border size="small">
          <el-table-column label="转发机 IP" width="130">
            <template slot-scope="{ row }"><span class="mono">{{ row.forwarder_ip }}</span></template>
          </el-table-column>
          <el-table-column label="客户端地址" min-width="200" show-overflow-tooltip>
            <template slot-scope="{ row }"><span class="mono">{{ row.client_address }}</span></template>
          </el-table-column>
          <el-table-column label="订阅消息" width="100" align="center">
            <template slot-scope="{ row }">
              <el-tag v-for="s in row.matched_subscriptions" :key="s.label"
                size="mini" type="success" style="margin:1px">{{ s.label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="连接时间" width="130">
            <template slot-scope="{ row }">
              <span style="font-size:11px;color:#909399">{{ row.start_date }} {{ row.start_time }}</span>
            </template>
          </el-table-column>
          <el-table-column label="积压字节" width="90" align="right">
            <template slot-scope="{ row }">
              <span :style="{ color: row.pending_bytes > 0 ? '#e6a23c' : '#67c23a' }">
                {{ row.pending_bytes }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 无法连接 -->
      <el-card v-if="result.unreachable.length > 0" shadow="never">
        <div slot="header" class="card-header">
          <i class="el-icon-warning" style="color:#e6a23c" />
          <span>无法连接（heartbeat 超时）</span>
        </div>
        <el-table :data="result.unreachable" border size="small">
          <el-table-column prop="ip" label="IP" width="140" />
          <el-table-column prop="fqdn" label="FQDN" min-width="180" show-overflow-tooltip />
          <el-table-column prop="error" label="错误" min-width="200">
            <template slot-scope="{ row }">
              <span style="color:#f56c6c;font-size:11px">{{ row.error }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <div v-else-if="!loading" class="empty-placeholder">
      <i class="el-icon-share" style="font-size:48px;color:#dcdfe6" />
      <p style="color:#909399;margin-top:12px">输入消息号后点击查询，追溯完整转发链路</p>
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
      if (!mid) { this.$message.warning('请输入 Message ID'); return }
      const msg = this.serviceId ? `${this.serviceId}.${mid}` : mid
      this.loading = true
      this.result = null
      try {
        const res = await queryMsgChain(msg)
        this.result = res.data
        const q = res.data.query || {}
        this.queryLabel = q.service_label
          ? `${q.service_id}.${q.msg_id}（${q.service_label}）`
          : `所有 Service 下的 msg ${q.msg_id}`
      } catch (e) {
        this.$message.error('查询失败：' + (e.message || '未知错误'))
      } finally {
        this.loading = false
      }
    },

    nodeClass(node) {
      return {
        'node-external': node.type === 'external',
        'node-source': node.type === 'source',
        'node-forwarder': node.type === 'forwarder',
      }
    },

    nodeTypeLabel(node) {
      return { external: '外部源', source: '接入层', forwarder: '转发机' }[node.type] || node.type
    },
  },
}
</script>

<style scoped>
.msg-chain { padding: 16px; }
.search-card { margin-bottom: 16px; }
.search-bar { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.search-label { font-size: 13px; color: #606266; margin-right: 6px; }
.search-tip { margin-top: 10px; font-size: 12px; color: #909399; }
.query-label { margin-left: 16px; font-size: 13px; color: #409eff; }
.result-area { margin-top: 4px; }
.stat-card { text-align: center; padding: 6px 0; }
.stat-num { font-size: 28px; font-weight: bold; line-height: 1.3; }
.stat-desc { font-size: 12px; color: #909399; margin-top: 2px; }
.card-header { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: bold; }
.empty-tip { text-align: center; color: #c0c4cc; padding: 24px 0; font-size: 13px; }
.empty-placeholder { text-align: center; padding: 80px 0; }
.mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; }

/* 链路行 */
.chain-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
  padding: 10px;
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #ebeef5;
  overflow-x: auto;
}
.chain-index {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  min-width: 42px;
  padding-top: 18px;
  margin-right: 8px;
}
.chain-nodes {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0;
}
.chain-arrow {
  font-size: 18px;
  color: #c0c4cc;
  padding: 0 6px;
  margin-top: 10px;
  flex-shrink: 0;
}

/* 节点 */
.chain-node {
  min-width: 120px;
  max-width: 160px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 2px solid #dcdfe6;
  background: #fff;
  flex-shrink: 0;
  font-size: 11px;
}
.node-external {
  border-color: #f56c6c;
  background: #fef0f0;
}
.node-source {
  border-color: #e6a23c;
  background: #fdf6ec;
}
.node-forwarder {
  border-color: #409eff;
  background: #ecf5ff;
}
.node-type-tag {
  font-size: 10px;
  color: #fff;
  background: #909399;
  border-radius: 3px;
  padding: 0 4px;
  display: inline-block;
  margin-bottom: 3px;
}
.node-external .node-type-tag  { background: #f56c6c; }
.node-source .node-type-tag    { background: #e6a23c; }
.node-forwarder .node-type-tag { background: #409eff; }
.node-ip {
  font-family: monospace;
  font-size: 11px;
  font-weight: bold;
  color: #303133;
  word-break: break-all;
}
.node-instance {
  font-size: 10px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}
.node-services { margin-top: 4px; }
</style>
