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
            <div class="stat-num" style="color:#409eff">{{ result.edges ? result.edges.length : 0 }}</div>
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
          <el-tag size="mini" type="info" style="margin-left:8px">外部源 → 接收机 → 转发机（从左到右）</el-tag>
          <el-tag v-if="result.live && result.live.length > 0" size="mini" type="success" style="margin-left:4px">
            <i class="el-icon-user" /> 绿色边框节点有下游客户端，点击查看
          </el-tag>
          <span style="margin-left:auto;display:flex;gap:8px;align-items:center">
            <span class="legend-dot" style="background:#f56c6c"></span><span class="legend-text">外部源</span>
            <span class="legend-dot" style="background:#e6a23c"></span><span class="legend-text">接收机</span>
            <span class="legend-dot" style="background:#409eff"></span><span class="legend-text">转发机</span>
            <span class="legend-dot" style="background:#67c23a"></span><span class="legend-text">聚合转发</span>
          </span>
        </div>

        <div v-if="topoLayers.length === 0" class="empty-tip">
          未找到包含该消息的配置
        </div>
        <div v-else class="topo-scroll">
        <div ref="topoWrap" class="topo-wrap" :style="{ height: svgHeight + 'px', width: svgWidth + 'px' }">
          <!-- SVG 画连线 -->
          <svg
            v-if="svgReady"
            class="topo-svg"
            :width="svgWidth"
            :height="svgHeight"
          >
            <defs>
              <marker id="arrow-blue"  markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L8,3 z" fill="#409eff" />
              </marker>
              <marker id="arrow-gray"  markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L0,6 L8,3 z" fill="#c0c4cc" />
              </marker>
            </defs>
            <path
              v-for="(edge, i) in svgEdges"
              :key="i"
              :d="edge.d"
              :stroke="edge.color"
              stroke-width="1.5"
              fill="none"
              :marker-end="edge.markerEnd"
              opacity="0.7"
            />
          </svg>

          <!-- 节点（绝对定位） -->
          <div
            v-for="node in layoutNodes"
            :key="node.id"
            class="topo-node"
            :class="[nodeClass(node), { 'node-has-live': liveByForwarder[node.id] && liveByForwarder[node.id].length > 0 }]"
            :style="{ left: node.x + 'px', top: node.y + 'px', width: NODE_W + 'px' }"
            @mouseenter="hoveredNode = node.id"
            @mouseleave="hoveredNode = null"
          >
            <div class="node-type-tag">{{ nodeTypeLabel(node) }}</div>
            <div class="node-name" :title="node.instance">{{ nodeDisplayName(node) }}</div>
            <div class="node-ip">{{ node.id }}</div>
            <div v-if="node.services && node.services.length" class="node-services">
              <el-tag
                v-for="s in node.services" :key="s.msg_label"
                size="mini" type="primary" style="margin:1px 1px 0 0"
              >{{ s.msg_label }}</el-tag>
            </div>
            <!-- 下游客户端气泡 -->
            <el-popover
              v-if="liveByForwarder[node.id] && liveByForwarder[node.id].length > 0"
              placement="right"
              width="380"
              trigger="click"
              popper-class="client-popover"
            >
              <div class="client-pop-header">
                <i class="el-icon-connection" style="color:#67c23a" />
                {{ node.id }} 的下游客户端（{{ liveByForwarder[node.id].length }} 个）
              </div>
              <el-table
                :data="liveByForwarder[node.id]"
                border size="mini"
                max-height="280"
                style="margin-top:8px"
              >
                <el-table-column label="客户端地址" min-width="140" show-overflow-tooltip>
                  <template slot-scope="{ row }">
                    <span class="mono">{{ row.client_address }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="连接时间" width="100">
                  <template slot-scope="{ row }">
                    <span style="font-size:10px;color:#909399">{{ row.start_date }}<br>{{ row.start_time }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="积压" width="60" align="right">
                  <template slot-scope="{ row }">
                    <span :style="{ color: row.pending_bytes > 0 ? '#e6a23c' : '#67c23a', fontSize: '11px' }">
                      {{ row.pending_bytes }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
              <div slot="reference" class="node-client-badge">
                <i class="el-icon-user" />
                {{ liveByForwarder[node.id].length }}
              </div>
            </el-popover>
          </div>
        </div>
        </div>
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

const NODE_W = 150   // 节点宽度
const NODE_H = 80    // 节点高度（估算，含 services tag 时更高）
const COL_GAP = 80   // 列间距
const ROW_GAP = 20   // 行间距
const PAD = 20       // 画布 padding

export default {
  name: 'MsgChain',
  data() {
    return {
      NODE_W,
      serviceList: [],
      serviceId: null,
      msgId: '',
      loading: false,
      result: null,
      queryLabel: '',
      svgReady: false,
      hoveredNode: null,
    }
  },
  computed: {
    /** Kahn 拓扑分层，返回 [[nodeId, ...], ...] */
    topoLayers() {
      if (!this.result || !this.result.nodes) return []
      const nodes = this.result.nodes
      const edges = this.result.edges || []
      if (!Object.keys(nodes).length) return []

      const inDegree = {}
      const children = {}
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

      const layers = []
      let queue = Object.keys(inDegree).filter(id => inDegree[id] === 0)
      const visited = new Set()
      while (queue.length) {
        layers.push([...queue])
        queue.forEach(id => visited.add(id))
        const next = []
        for (const id of queue) {
          for (const child of (children[id] || [])) {
            inDegree[child]--
            if (inDegree[child] === 0 && !visited.has(child)) next.push(child)
          }
        }
        queue = next
      }
      const remaining = Object.keys(nodes).filter(id => !visited.has(id))
      if (remaining.length) layers.push(remaining)
      return layers
    },

    /** 计算每个节点的绝对坐标 */
    layoutNodes() {
      if (!this.result || !this.topoLayers.length) return []
      const nodes = this.result.nodes
      const result = []
      const nodeH = NODE_H + 16  // 预留 services tag 空间

      this.topoLayers.forEach((layer, col) => {
        const x = PAD + col * (NODE_W + COL_GAP)
        const totalH = layer.length * nodeH + (layer.length - 1) * ROW_GAP
        const startY = PAD + Math.max(0, (this.svgHeight - totalH) / 2 - PAD)

        layer.forEach((id, row) => {
          const node = nodes[id]
          if (!node) return
          result.push({
            ...node,
            x,
            y: startY + row * (nodeH + ROW_GAP),
          })
        })
      })
      return result
    },

    /** nodeId -> {x, y, cx, cy} 中心点查找表 */
    nodePositionMap() {
      const map = {}
      const nodeH = NODE_H + 16
      this.layoutNodes.forEach(n => {
        map[n.id] = {
          x: n.x,
          y: n.y,
          cx: n.x + NODE_W / 2,
          cy: n.y + nodeH / 2,
        }
      })
      return map
    },

    svgWidth() {
      if (!this.topoLayers.length) return 600
      return PAD * 2 + this.topoLayers.length * (NODE_W + COL_GAP) - COL_GAP
    },

    svgHeight() {
      if (!this.topoLayers.length) return 300
      const maxLen = Math.max(...this.topoLayers.map(l => l.length))
      const nodeH = NODE_H + 16
      return PAD * 2 + maxLen * nodeH + (maxLen - 1) * ROW_GAP
    },

    /** forwarder_ip → live clients 列表 */
    liveByForwarder() {
      if (!this.result || !this.result.live) return {}
      const map = {}
      for (const item of this.result.live) {
        const ip = item.forwarder_ip
        if (!map[ip]) map[ip] = []
        map[ip].push(item)
      }
      return map
    },

    /** 生成 SVG 贝塞尔曲线边 */
    svgEdges() {
      if (!this.result || !this.result.edges) return []
      const posMap = this.nodePositionMap
      const nodeH = NODE_H + 16
      return this.result.edges.map(e => {
        const from = posMap[e.from]
        const to = posMap[e.to]
        if (!from || !to) return null

        // 从 from 节点右侧中心 → to 节点左侧中心
        const x1 = from.x + NODE_W
        const y1 = from.cy
        const x2 = to.x
        const y2 = to.cy
        const cx1 = x1 + (x2 - x1) * 0.45
        const cx2 = x2 - (x2 - x1) * 0.45
        const d = `M ${x1} ${y1} C ${cx1} ${y1} ${cx2} ${y2} ${x2} ${y2}`

        const fromNode = this.result.nodes[e.from]
        const isExternal = fromNode && fromNode.type === 'external'
        return {
          d,
          color: isExternal ? '#c0c4cc' : '#409eff',
          markerEnd: isExternal ? 'url(#arrow-gray)' : 'url(#arrow-blue)',
        }
      }).filter(Boolean)
    },
  },
  watch: {
    result(val) {
      if (val) {
        this.svgReady = false
        this.$nextTick(() => { this.svgReady = true })
      }
    },
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
      this.svgReady = false
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
        'node-external':   node.type === 'external',
        'node-receiver':   node.type === 'receiver',
        'node-forwarder':  node.type === 'forwarder',
        'node-aggregator': node.type === 'aggregator',
      }
    },

    nodeTypeLabel(node) {
      return { external: '外部源', receiver: '接收机', forwarder: '转发机', aggregator: '聚合转发' }[node.type] || node.type
    },

    nodeDisplayName(node) {
      // 优先显示实例名（去掉过长的 IP 后缀部分），兜底用 id
      const inst = node.instance || ''
      if (!inst || inst === node.id) return node.id
      // 截断超长名称
      return inst.length > 20 ? inst.slice(0, 18) + '…' : inst
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

/* 图例 */
.legend-dot {
  width: 10px; height: 10px; border-radius: 50%; display: inline-block;
}
.legend-text { font-size: 12px; color: #606266; }

/* 滚动外层 */
.topo-scroll {
  overflow-x: auto;
  overflow-y: auto;
  max-height: 600px;
}

/* 拓扑图容器：相对定位，节点绝对定位 */
.topo-wrap {
  position: relative;
}

/* SVG 画在最底层 */
.topo-svg {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

/* 节点 */
.topo-node {
  position: absolute;
  padding: 7px 9px;
  border-radius: 8px;
  border: 2px solid #dcdfe6;
  background: #fff;
  font-size: 11px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  cursor: default;
  transition: box-shadow 0.15s, transform 0.15s;
  box-sizing: border-box;
}
.topo-node:hover {
  box-shadow: 0 3px 10px rgba(0,0,0,0.18);
  transform: translateY(-1px);
  z-index: 10;
}
.node-external  { border-color: #f56c6c; background: #fef0f0; }
.node-receiver  { border-color: #e6a23c; background: #fdf6ec; }
.node-forwarder { border-color: #409eff; background: #ecf5ff; }
.node-aggregator{ border-color: #67c23a; background: #f0f9eb; }

.node-type-tag {
  font-size: 10px; color: #fff; background: #909399;
  border-radius: 3px; padding: 0 4px;
  display: inline-block; margin-bottom: 4px;
}
.node-external  .node-type-tag { background: #f56c6c; }
.node-receiver  .node-type-tag { background: #e6a23c; }
.node-forwarder .node-type-tag { background: #409eff; }
.node-aggregator .node-type-tag { background: #67c23a; }

.node-name {
  font-size: 12px; font-weight: 600; color: #303133;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 2px;
}
.node-ip {
  font-family: monospace; font-size: 10px; color: #606266;
  word-break: break-all;
}
.node-services { margin-top: 4px; }

/* 有实时客户端的节点高亮 */
.node-has-live {
  box-shadow: 0 0 0 2px #67c23a, 0 1px 4px rgba(0,0,0,0.08);
}

/* 客户端气泡徽章 */
.node-client-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: 5px;
  padding: 1px 7px;
  border-radius: 10px;
  background: #67c23a;
  color: #fff;
  font-size: 10px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.node-client-badge:hover {
  background: #4caf50;
}

/* Popover 内 header */
.client-pop-header {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
