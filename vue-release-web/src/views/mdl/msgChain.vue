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
            <div class="stat-num" style="color:#409eff">{{ result.edges ? result.edges.length : result.chains.length }}</div>
            <div class="stat-desc">条转发路径</div>
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

      <!-- 拓扑图 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <div slot="header" class="card-header">
          <i class="el-icon-share" style="color:#409eff" />
          <span>转发拓扑图（配置文件追溯）</span>
          <el-tag size="mini" type="info" style="margin-left:8px">从外部源 → 转发机</el-tag>
        </div>

        <div v-if="topoLayers.length === 0" class="empty-tip">
          未找到包含该消息的配置
        </div>

        <!-- 按层展示：每层横向排节点，层间用箭头连接 -->
        <div v-else class="topo-container">
          <div v-for="(layer, li) in topoLayers" :key="li" class="topo-row">
            <!-- 层标题 -->
            <div class="topo-layer-label">{{ layerLabel(li, topoLayers.length, layer) }}</div>
            <!-- 节点区 -->
            <div class="topo-nodes">
              <div
                v-for="node in layer"
                :key="node.id"
                class="chain-node"
                :class="nodeClass(node)"
              >
                <div class="node-type-tag">{{ nodeTypeLabel(node) }}</div>
                <div class="node-ip">{{ node.node }}</div>
                <div class="node-instance" :title="node.instance">{{ node.instance }}</div>
                <div v-if="node.services && node.services.length" class="node-services">
                  <el-tag
                    v-for="s in node.services" :key="s.msg_label"
                    size="mini" type="primary" style="margin:1px 1px 0 0"
                  >{{ s.msg_label }}</el-tag>
                </div>
              </div>
            </div>
            <!-- 层间箭头（不在最后一层显示） -->
            <div v-if="li < topoLayers.length - 1" class="topo-arrow-row">
              <span class="topo-arrow">↓</span>
            </div>
          </div>

          <!-- 边明细（折叠展示，辅助理解多对多关系） -->
          <el-collapse style="margin-top:12px">
            <el-collapse-item name="edges">
              <template slot="title">
                <span style="font-size:12px;color:#909399">
                  <i class="el-icon-connection" /> 查看连接明细（{{ result.edges && result.edges.length || 0 }} 条边）
                </span>
              </template>
              <div v-if="result.edges && result.edges.length" class="edge-list">
                <div v-for="(e, i) in result.edges" :key="i" class="edge-item">
                  <span class="mono">{{ e.from }}</span>
                  <span class="edge-arrow"> → </span>
                  <span class="mono">{{ e.to }}</span>
                  <el-tag
                    v-for="s in e.services" :key="s.msg_label"
                    size="mini" type="info" style="margin-left:4px"
                  >{{ s.msg_label }}</el-tag>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
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
  computed: {
    /**
     * 将 nodes + edges 转为分层数组，用于拓扑图展示。
     * 使用拓扑排序（Kahn 算法）按层分组。
     */
    topoLayers() {
      if (!this.result || !this.result.nodes) return []
      const nodes = this.result.nodes   // { id: node }
      const edges = this.result.edges || []

      if (!Object.keys(nodes).length) return []

      // 构建入度表和邻接表
      const inDegree = {}
      const children = {}  // from -> [to]
      for (const nid of Object.keys(nodes)) {
        inDegree[nid] = 0
        children[nid] = []
      }
      for (const e of edges) {
        if (!(e.to in inDegree)) inDegree[e.to] = 0
        if (!(e.from in children)) children[e.from] = []
        inDegree[e.to]++
        children[e.from].push(e.to)
      }

      // Kahn 分层
      const layers = []
      let queue = Object.keys(inDegree).filter(id => inDegree[id] === 0)
      const visited = new Set()

      while (queue.length) {
        layers.push(queue.map(id => nodes[id]).filter(Boolean))
        queue.forEach(id => visited.add(id))
        const next = []
        for (const id of queue) {
          for (const child of (children[id] || [])) {
            inDegree[child]--
            if (inDegree[child] === 0 && !visited.has(child)) {
              next.push(child)
            }
          }
        }
        queue = next
      }

      // 如果有孤立节点（无边）也加入
      const remaining = Object.keys(nodes).filter(id => !visited.has(id))
      if (remaining.length) {
        layers.push(remaining.map(id => nodes[id]).filter(Boolean))
      }

      return layers
    },
  },
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

    layerLabel(li, total, layer) {
      if (li === total - 1) return '末端转发机'
      if (li === 0) {
        const types = (layer || []).map(n => n.type)
        if (types.every(t => t === 'external')) return '外部源（交易所）'
        if (types.every(t => t === 'receiver')) return '接收机'
        return '源端'
      }
      return `中间层 ${li}`
    },

    nodeClass(node) {
      return {
        'node-external':    node.type === 'external',
        'node-receiver':    node.type === 'receiver',
        'node-forwarder':   node.type === 'forwarder',
        'node-aggregator':  node.type === 'aggregator',
      }
    },

    nodeTypeLabel(node) {
      return {
        external:   '外部源',
        receiver:   '接收机',
        forwarder:  '转发机',
        aggregator: '聚合转发',
      }[node.type] || node.type
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

/* 拓扑图容器 */
.topo-container {
  padding: 4px 0;
}
.topo-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.topo-layer-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 6px;
  padding-left: 4px;
  border-left: 3px solid #dcdfe6;
  padding-left: 6px;
}
.topo-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}
.topo-arrow-row {
  display: flex;
  align-items: center;
  padding: 2px 0 2px 20px;
  margin-bottom: 4px;
}
.topo-arrow {
  font-size: 20px;
  color: #c0c4cc;
}

/* 边明细 */
.edge-list {
  max-height: 200px;
  overflow-y: auto;
  font-size: 12px;
}
.edge-item {
  padding: 3px 0;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
}
.edge-arrow {
  color: #c0c4cc;
  margin: 0 2px;
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
.node-receiver {
  border-color: #e6a23c;
  background: #fdf6ec;
}
.node-forwarder {
  border-color: #409eff;
  background: #ecf5ff;
}
.node-aggregator {
  border-color: #67c23a;
  background: #f0f9eb;
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
.node-external .node-type-tag   { background: #f56c6c; }
.node-receiver .node-type-tag   { background: #e6a23c; }
.node-forwarder .node-type-tag  { background: #409eff; }
.node-aggregator .node-type-tag { background: #67c23a; }
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
