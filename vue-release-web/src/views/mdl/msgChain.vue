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
        <el-button size="small" icon="el-icon-refresh"
          :loading="rebuilding" style="margin-left:8px" @click="handleRebuildIndex">刷新索引</el-button>
        <span v-if="indexStatus" class="index-status">
          <i class="el-icon-time" />
          索引：{{ indexStatus.total }} 条，最近重建 {{ indexStatus.latest_built_at || '未知' }}
          <el-tag v-if="indexStatus.is_running" type="warning" size="mini" style="margin-left:4px">重建中</el-tag>
        </span>
        <span v-if="queryLabel" class="query-label">查询：<b>{{ queryLabel }}</b></span>
      </div>
      <div class="search-tip">
        选 Service ID + 填 Message ID 查询完整转发链路，不选 Service ID 则匹配所有 Service。
        索引由系统自动维护，配置变更后自动更新；如需立即刷新可点击「刷新索引」。
      </div>
    </el-card>

    <div v-if="result" class="result-area">
      <!-- 统计 -->
      <el-row :gutter="12" style="margin-bottom:16px">
        <el-col :span="8">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#409eff">{{ result.edges ? result.edges.length : 0 }}</div>
            <div class="stat-desc">条转发路径</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#67c23a">{{ result.live.length }}</div>
            <div class="stat-desc">实时活跃订阅</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" class="stat-card">
            <div class="stat-num" style="color:#909399">{{ Object.keys(result.nodes).length }}</div>
            <div class="stat-desc">涉及节点数</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 拓扑图 -->
      <el-card shadow="never" style="margin-bottom:16px">
        <div slot="header" class="card-header">
          <i class="el-icon-share" style="color:#409eff" />
          <span>转发拓扑图（配置文件追溯）</span>
          <el-radio-group v-model="viewMode" size="mini" style="margin-left:12px">
            <el-radio-button label="graph">拓扑图</el-radio-button>
            <el-radio-button label="text">文字链路</el-radio-button>
          </el-radio-group>
          <el-tag v-if="viewMode === 'graph'" size="mini" type="info" style="margin-left:8px">外部源 → 接收机 → 转发机（从左到右）</el-tag>
          <el-tag v-if="result.live && result.live.length > 0" size="mini" type="success" style="margin-left:4px">
            <i class="el-icon-user" /> 绿色边框节点有下游客户端，点击查看
          </el-tag>
          <span style="margin-left:auto;display:flex;gap:8px;align-items:center">
            <template v-if="viewMode === 'graph'">
              <span class="legend-dot" style="background:#f56c6c"></span><span class="legend-text">接收机(外部)</span>
              <span class="legend-dot" style="background:#e6a23c"></span><span class="legend-text">接收机</span>
              <span class="legend-dot" style="background:#409eff"></span><span class="legend-text">转发机</span>
              <span class="legend-dot" style="background:#67c23a"></span><span class="legend-text">聚合转发</span>
              <span class="legend-dot" style="background:#9c27b0"></span><span class="legend-text">上证云</span>
              <span class="legend-line-dash"></span><span class="legend-text">心跳连接</span>
              <el-tooltip content="滚轮缩放 · 拖空白区域平移 · 拖节点移动" placement="top">
                <i class="el-icon-info" style="color:#909399;cursor:help" />
              </el-tooltip>
              <el-button size="mini" icon="el-icon-refresh-left" @click="resetView">重置视图</el-button>
            </template>
          </span>
        </div>

        <div v-if="topoLayers.length === 0" class="empty-tip">
          未找到包含该消息的配置
        </div>

        <!-- ===== 文字链路模式 ===== -->
        <div v-else-if="viewMode === 'text'" class="text-chain-wrap">
          <div v-for="(tree, idx) in chainForest" :key="idx" class="text-chain-tree">
            <div
              v-for="row in flattenTree(tree)"
              :key="row.id + '-' + row.depth"
              class="text-chain-row"
              :style="{ paddingLeft: (row.depth * 24 + 8) + 'px' }"
            >
              <span v-if="row.depth > 0" class="text-chain-indent" :class="{ 'text-chain-indent-live': row._edgeSource === 'live' }">└─</span>
              <span class="text-chain-type" :class="'tc-' + row.type">{{ row.typeLabel }}</span>
              <span class="text-chain-name" :title="row.instance">{{ row.displayName }}</span>
              <span class="text-chain-ip">({{ row.id }})</span>
              <el-tag v-if="row._edgeSource === 'live'" size="mini" type="success" style="margin-left:4px">心跳</el-tag>
              <el-tag
                v-for="s in row.services" :key="s.msg_label"
                size="mini" type="info" style="margin-left:4px"
              >{{ s.msg_label }}</el-tag>
              <el-popover
                v-if="liveByForwarder[row.id] && liveByForwarder[row.id].length > 0"
                placement="right"
                width="380"
                trigger="click"
                popper-class="client-popover"
              >
                <div class="client-pop-header">
                  <i class="el-icon-connection" style="color:#67c23a" />
                  {{ row.id }} 的下游客户端（{{ liveByForwarder[row.id].length }} 个）
                </div>
                <el-table
                  :data="liveByForwarder[row.id]"
                  border size="mini"
                  max-height="280"
                  style="margin-top:8px"
                >
                  <el-table-column label="客户端地址" min-width="140" show-overflow-tooltip>
                    <template slot-scope="{ row: r }">
                      <span class="mono">{{ r.client_address }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="连接时间" width="100">
                    <template slot-scope="{ row: r }">
                      <span style="font-size:10px;color:#909399">{{ r.start_date }}<br>{{ r.start_time }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="积压" width="60" align="right">
                    <template slot-scope="{ row: r }">
                      <span :style="{ color: r.pending_bytes > 0 ? '#e6a23c' : '#67c23a', fontSize: '11px' }">
                        {{ r.pending_bytes }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
                <span slot="reference" class="text-chain-live text-chain-live-click">
                  <i class="el-icon-user" /> {{ liveByForwarder[row.id].length }} 个下游
                </span>
              </el-popover>
            </div>
          </div>
          <div v-if="chainForest.length === 0" class="empty-tip">无链路数据</div>
        </div>

        <!-- ===== 拓扑图模式 ===== -->
        <div
          v-else
          ref="topoScroll"
          class="topo-scroll"
          @wheel.prevent="onWheel"
          @mousedown="onCanvasMousedown"
          @mousemove="onMousemove"
          @mouseup="onMouseup"
          @mouseleave="onMouseup"
        >
          <div
            ref="topoWrap"
            class="topo-wrap"
            :style="wrapStyle"
          >
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
                <marker id="arrow-blue-sel" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L8,3 z" fill="#1565c0" />
                </marker>
                <marker id="arrow-gray-sel" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L8,3 z" fill="#606266" />
                </marker>
                <marker id="arrow-green" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L8,3 z" fill="#67c23a" />
                </marker>
                <marker id="arrow-green-sel" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L8,3 z" fill="#4caf50" />
                </marker>
              </defs>
              <!-- 透明宽热区 -->
              <path
                v-for="(edge, i) in svgEdges"
                :key="'hit-' + i"
                :d="edge.d"
                stroke="transparent"
                stroke-width="12"
                fill="none"
                style="cursor:pointer"
                @click="selectEdge(edge, i)"
              />
              <!-- 实际连线 -->
              <path
                v-for="(edge, i) in svgEdges"
                :key="i"
                :d="edge.d"
                :stroke="selectedEdgeIndex === i ? edge.selectedColor : edge.color"
                :stroke-width="selectedEdgeIndex === i ? 3 : 1.5"
                :stroke-dasharray="edge.dashArray"
                fill="none"
                :marker-end="selectedEdgeIndex === i ? edge.selectedMarkerEnd : edge.markerEnd"
                :opacity="selectedEdgeIndex === i ? 1 : 0.7"
                style="pointer-events:none"
              />
              <!-- 选中边信息气泡 -->
              <g v-if="selectedEdgeIndex !== null && svgEdges[selectedEdgeIndex]">
                <rect
                  :x="svgEdges[selectedEdgeIndex].mx - 90"
                  :y="svgEdges[selectedEdgeIndex].my - 32"
                  width="180" height="54"
                  rx="6" ry="6"
                  fill="white"
                  stroke="#1565c0"
                  stroke-width="1.5"
                />
                <text
                  :x="svgEdges[selectedEdgeIndex].mx"
                  :y="svgEdges[selectedEdgeIndex].my - 14"
                  text-anchor="middle"
                  font-size="11"
                  fill="#303133"
                  font-weight="600"
                >{{ svgEdges[selectedEdgeIndex].fromLabel }}</text>
                <text
                  :x="svgEdges[selectedEdgeIndex].mx"
                  :y="svgEdges[selectedEdgeIndex].my + 2"
                  text-anchor="middle"
                  font-size="10"
                  fill="#909399"
                >↓</text>
                <text
                  :x="svgEdges[selectedEdgeIndex].mx"
                  :y="svgEdges[selectedEdgeIndex].my + 16"
                  text-anchor="middle"
                  font-size="11"
                  fill="#303133"
                  font-weight="600"
                >{{ svgEdges[selectedEdgeIndex].toLabel }}</text>
                <circle
                  :cx="svgEdges[selectedEdgeIndex].mx + 84"
                  :cy="svgEdges[selectedEdgeIndex].my - 26"
                  r="8"
                  fill="#f56c6c"
                  style="cursor:pointer"
                  @click="selectedEdgeIndex = null"
                />
                <text
                  :x="svgEdges[selectedEdgeIndex].mx + 84"
                  :y="svgEdges[selectedEdgeIndex].my - 22"
                  text-anchor="middle"
                  font-size="10"
                  fill="white"
                  style="pointer-events:none"
                >✕</text>
              </g>
            </svg>

            <!-- 节点（绝对定位） -->
            <div
              v-for="node in layoutNodes"
              :key="node.id"
              class="topo-node"
              :class="[nodeClass(node), { 'node-has-live': liveByForwarder[node.id] && liveByForwarder[node.id].length > 0 }]"
              :style="{ left: node.x + 'px', top: node.y + 'px', width: NODE_W + 'px' }"
              @mousedown.stop="onNodeMousedown($event, node)"
            >
              <div class="node-type-tag">{{ nodeTypeLabel(node) }}</div>
              <span v-if="node.service_type === 'sse_cloud'" class="node-sse-badge">上证云</span>
              <div class="node-name" :title="node.instance">{{ nodeDisplayName(node) }}</div>
              <div v-if="node.exchange" class="node-exchange">{{ node.exchange }}</div>
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
                <div slot="reference" class="node-client-badge" @mousedown.stop>
                  <i class="el-icon-user" />
                  {{ liveByForwarder[node.id].length }}
                </div>
              </el-popover>
            </div>
          </div>
        </div>
      </el-card>

    </div>

    <div v-else-if="!loading" class="empty-placeholder">
      <i class="el-icon-share" style="font-size:48px;color:#dcdfe6" />
      <p style="color:#909399;margin-top:12px">输入消息号后点击查询，追溯完整转发链路</p>
    </div>
  </div>
</template>

<script>
import { queryMsgChain, getServices, rebuildChainIndex, getChainIndexStatus } from '@/api/forwarderChain'

const NODE_W = 150   // 节点宽度
const NODE_H = 80    // 节点高度（估算，含 services tag 时更高）
const COL_GAP = 80   // 列间距
const ROW_GAP = 20   // 行间距
const PAD = 20       // 画布 padding
const ZOOM_MIN = 0.3
const ZOOM_MAX = 2.5

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
      selectedEdgeIndex: null,
      viewMode: 'text',   // 'graph' | 'text'
      rebuilding: false,
      indexStatus: null,
      _statusTimer: null,

      // 画布变换状态
      zoom: 1,
      panX: 0,
      panY: 0,

      // 节点手动偏移 { nodeId: { dx, dy } }
      nodeOverrides: {},

      // 拖拽状态
      _drag: null,   // { type: 'canvas' | 'node', nodeId?, startX, startY, origPanX?, origPanY?, origDx?, origDy? }
    }
  },
  computed: {
    wrapStyle() {
      return {
        position: 'relative',
        width: this.svgWidth + 'px',
        height: this.svgHeight + 'px',
        transform: `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`,
        transformOrigin: '0 0',
        willChange: 'transform',
      }
    },

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

    /** 计算每个节点的绝对坐标（含手动偏移） */
    layoutNodes() {
      if (!this.result || !this.topoLayers.length) return []
      const nodes = this.result.nodes
      const result = []
      const nodeH = NODE_H + 16

      this.topoLayers.forEach((layer, col) => {
        const baseX = PAD + col * (NODE_W + COL_GAP)
        const totalH = layer.length * nodeH + (layer.length - 1) * ROW_GAP
        const startY = PAD + Math.max(0, (this.svgHeight - totalH) / 2 - PAD)

        layer.forEach((id, row) => {
          const node = nodes[id]
          if (!node) return
          const override = this.nodeOverrides[id] || { dx: 0, dy: 0 }
          result.push({
            ...node,
            x: baseX + override.dx,
            y: startY + row * (nodeH + ROW_GAP) + override.dy,
          })
        })
      })
      return result
    },

    /** nodeId -> {x, y, cx, cy} */
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
      return PAD * 2 + this.topoLayers.length * (NODE_W + COL_GAP) - COL_GAP + 200
    },

    svgHeight() {
      if (!this.topoLayers.length) return 300
      const maxLen = Math.max(...this.topoLayers.map(l => l.length))
      const nodeH = NODE_H + 16
      return PAD * 2 + maxLen * nodeH + (maxLen - 1) * ROW_GAP + 100
    },

    /** forwarder_ip → live clients */
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
      return this.result.edges.map(e => {
        const from = posMap[e.from]
        const to = posMap[e.to]
        if (!from || !to) return null

        const x1 = from.x + NODE_W
        const y1 = from.cy
        const x2 = to.x
        const y2 = to.cy
        const cx1 = x1 + (x2 - x1) * 0.45
        const cx2 = x2 - (x2 - x1) * 0.45
        const d = `M ${x1} ${y1} C ${cx1} ${y1} ${cx2} ${y2} ${x2} ${y2}`

        // 贝塞尔中点 t=0.5
        const mx = 0.125*x1 + 0.375*cx1 + 0.375*cx2 + 0.125*x2
        const my = 0.125*y1 + 0.375*y1  + 0.375*y2  + 0.125*y2

        const fromNode = this.result.nodes[e.from]
        const toNode   = this.result.nodes[e.to]
        const isExternal = fromNode && fromNode.type === 'external'
        const isLive = e.source === 'live'
        const labelOf = n => (n && n.instance && n.instance !== n.id) ? n.instance : (n ? n.id : '')

        return {
          d, mx, my,
          fromId: e.from, toId: e.to,
          fromLabel: labelOf(fromNode) + (isLive ? ' [心跳]' : ''),
          toLabel: labelOf(toNode),
          services: e.services || [],
          source: e.source || 'config',
          color: isLive ? '#67c23a' : (isExternal ? '#c0c4cc' : '#409eff'),
          selectedColor: isLive ? '#4caf50' : (isExternal ? '#606266' : '#1565c0'),
          markerEnd: isLive ? 'url(#arrow-green)' : (isExternal ? 'url(#arrow-gray)' : 'url(#arrow-blue)'),
          selectedMarkerEnd: isLive ? 'url(#arrow-green-sel)' : (isExternal ? 'url(#arrow-gray-sel)' : 'url(#arrow-blue-sel)'),
          dashArray: isLive ? '6,3' : '',
        }
      }).filter(Boolean)
    },

    /**
     * 将 nodes + edges 构建成森林（多棵树），用于文字链路展示。
     * 每棵树从一个根节点（无入边）开始，children 按实例名排序。
     */
    chainForest() {
      if (!this.result || !this.result.nodes) return []
      const nodes = this.result.nodes
      const edges = this.result.edges || []
      if (!Object.keys(nodes).length) return []

      // 构建 children map，记录边的来源（config/live）
      const childrenMap = {}
      const edgeSourceMap = {}  // "from->to" => source
      const inDegree = {}
      for (const nid of Object.keys(nodes)) {
        childrenMap[nid] = []
        inDegree[nid] = 0
      }
      for (const e of edges) {
        if (childrenMap[e.from]) childrenMap[e.from].push(e.to)
        if (e.to in inDegree) inDegree[e.to]++
        edgeSourceMap[e.from + '->' + e.to] = e.source || 'config'
      }

      // 根节点 = 入度为 0
      const roots = Object.keys(nodes).filter(id => (inDegree[id] || 0) === 0)

      // 递归构建树，记录从父节点到子节点的边来源
      const buildTree = (nodeId, visited, parentId) => {
        if (visited.has(nodeId)) return null
        visited.add(nodeId)
        const node = nodes[nodeId]
        if (!node) return null
        const edgeSource = parentId ? (edgeSourceMap[parentId + '->' + nodeId] || 'config') : 'config'
        const kids = (childrenMap[nodeId] || [])
          .map(cid => buildTree(cid, visited, nodeId))
          .filter(Boolean)
          .sort((a, b) => {
            // config 边排前面，live 边排后面
            if (a._edgeSource !== b._edgeSource) return a._edgeSource === 'live' ? 1 : -1
            return (a.instance || '').localeCompare(b.instance || '')
          })
        return { ...node, children: kids, _edgeSource: edgeSource }
      }

      return roots.map(r => buildTree(r, new Set(), null)).filter(Boolean)
    },
  },
  watch: {
    result(val) {
      if (val) {
        this.svgReady = false
        this.selectedEdgeIndex = null
        this.nodeOverrides = {}
        this.$nextTick(() => { this.svgReady = true })
      }
    },
  },
  created() {
    this.fetchServices()
    this.fetchIndexStatus()
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
  beforeDestroy() {
    if (this._statusTimer) clearInterval(this._statusTimer)
    window.removeEventListener('mousemove', this._boundMousemove)
    window.removeEventListener('mouseup', this._boundMouseup)
  },
  methods: {
    async fetchServices() {
      try {
        const res = await getServices()
        this.serviceList = res.data || []
      } catch {}
    },

    async fetchIndexStatus() {
      try {
        const res = await getChainIndexStatus()
        this.indexStatus = res.data
      } catch {}
    },

    async handleRebuildIndex() {
      this.rebuilding = true
      try {
        const res = await rebuildChainIndex()
        this.$message.success(res.data?.message || '索引重建已启动')
        if (this._statusTimer) clearInterval(this._statusTimer)
        this._statusTimer = setInterval(async () => {
          await this.fetchIndexStatus()
          if (this.indexStatus && !this.indexStatus.is_running) {
            clearInterval(this._statusTimer)
            this._statusTimer = null
            this.rebuilding = false
          }
        }, 3000)
      } catch (e) {
        this.$message.error('触发失败：' + (e.message || '未知错误'))
        this.rebuilding = false
      }
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

    resetView() {
      this.zoom = 1
      this.panX = 0
      this.panY = 0
      this.nodeOverrides = {}
    },

    // ── 缩放 ──────────────────────────────────────────────
    onWheel(e) {
      const delta = e.deltaY > 0 ? 0.9 : 1.1
      const newZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, this.zoom * delta))

      // 以鼠标位置为缩放中心
      const rect = this.$refs.topoScroll.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      this.panX = mx - (mx - this.panX) * (newZoom / this.zoom)
      this.panY = my - (my - this.panY) * (newZoom / this.zoom)
      this.zoom = newZoom
    },

    // ── 画布平移 ──────────────────────────────────────────
    onCanvasMousedown(e) {
      if (e.button !== 0) return
      // 若点在节点上，节点自己会 stop，这里只处理空白区域
      this._drag = {
        type: 'canvas',
        startX: e.clientX,
        startY: e.clientY,
        origPanX: this.panX,
        origPanY: this.panY,
      }
      this.$refs.topoScroll.style.cursor = 'grabbing'
    },

    // ── 节点拖拽 ──────────────────────────────────────────
    onNodeMousedown(e, node) {
      if (e.button !== 0) return
      const override = this.nodeOverrides[node.id] || { dx: 0, dy: 0 }
      this._drag = {
        type: 'node',
        nodeId: node.id,
        startX: e.clientX,
        startY: e.clientY,
        origDx: override.dx,
        origDy: override.dy,
      }
      e.currentTarget.style.cursor = 'grabbing'
    },

    onMousemove(e) {
      if (!this._drag) return
      const dx = e.clientX - this._drag.startX
      const dy = e.clientY - this._drag.startY

      if (this._drag.type === 'canvas') {
        this.panX = this._drag.origPanX + dx
        this.panY = this._drag.origPanY + dy
      } else if (this._drag.type === 'node') {
        const id = this._drag.nodeId
        // 节点坐标在缩放空间内，需除以 zoom 转回逻辑坐标
        this.$set(this.nodeOverrides, id, {
          dx: this._drag.origDx + dx / this.zoom,
          dy: this._drag.origDy + dy / this.zoom,
        })
      }
    },

    onMouseup(e) {
      if (!this._drag) return
      if (this.$refs.topoScroll) this.$refs.topoScroll.style.cursor = ''
      this._drag = null
    },

    // ── 连线选中 ──────────────────────────────────────────
    selectEdge(edge, index) {
      this.selectedEdgeIndex = this.selectedEdgeIndex === index ? null : index
    },

    nodeClass(node) {
      return {
        'node-external':   node.type === 'external',
        'node-receiver':   node.type === 'receiver',
        'node-forwarder':  node.type === 'forwarder',
        'node-aggregator': node.type === 'aggregator',
        'node-sse-cloud':  node.service_type === 'sse_cloud',
      }
    },

    nodeTypeLabel(node) {
      return { external: '接收机', receiver: '接收机', forwarder: '转发机', aggregator: '聚合转发' }[node.type] || node.type
    },

    nodeDisplayName(node) {
      if (node.type === 'external') return node.exchange || node.id
      const inst = node.instance || ''
      if (!inst || inst === node.id) return node.id
      return inst.length > 20 ? inst.slice(0, 18) + '…' : inst
    },

    /** 将树递归展平为 [{...node, depth, typeLabel, displayName}, ...] */
    flattenTree(tree, depth = 0) {
      if (!tree) return []
      const typeLabels = { external: '接收机(外部)', receiver: '接收机', forwarder: '转发机', aggregator: '聚合转发' }
      const row = {
        ...tree,
        depth,
        typeLabel: typeLabels[tree.type] || tree.type,
        displayName: this.nodeDisplayName(tree),
      }
      const rows = [row]
      for (const child of (tree.children || [])) {
        rows.push(...this.flattenTree(child, depth + 1))
      }
      return rows
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
.index-status { margin-left: 16px; font-size: 12px; color: #909399; }
.result-area { margin-top: 4px; }
.stat-card { text-align: center; padding: 6px 0; }
.stat-num { font-size: 28px; font-weight: bold; line-height: 1.3; }
.stat-desc { font-size: 12px; color: #909399; margin-top: 2px; }
.card-header { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: bold; }
.empty-tip { text-align: center; color: #c0c4cc; padding: 24px 0; font-size: 13px; }
.empty-placeholder { text-align: center; padding: 80px 0; }
.mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; }

/* 图例 */
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.legend-text { font-size: 12px; color: #606266; }
.legend-line-dash {
  width: 18px; height: 0; border-top: 2px dashed #67c23a;
  display: inline-block; vertical-align: middle; margin-right: 2px;
}

/* 画布容器：固定高度，超出隐藏，捕获鼠标 */
.topo-scroll {
  overflow: hidden;
  height: 600px;
  cursor: grab;
  position: relative;
  background: #fafafa;
  border-radius: 4px;
  user-select: none;
}
.topo-scroll:active { cursor: grabbing; }

/* SVG 画在最底层 */
.topo-svg {
  position: absolute;
  top: 0;
  left: 0;
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
  cursor: grab;
  transition: box-shadow 0.15s;
  box-sizing: border-box;
}
.topo-node:hover {
  box-shadow: 0 3px 10px rgba(0,0,0,0.18);
  z-index: 10;
}
.topo-node:active { cursor: grabbing; }

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
.node-exchange {
  font-size: 12px; font-weight: 600; color: #f56c6c;
  margin-bottom: 2px;
}
.node-ip {
  font-family: monospace; font-size: 10px; color: #909399;
  word-break: break-all;
}
.node-services { margin-top: 4px; }

/* 上证云节点：在原有类型颜色基础上叠加紫色双边框，不覆盖背景 */
.node-sse-cloud { box-shadow: 0 0 0 2px #9c27b0, 0 1px 4px rgba(0,0,0,0.08); }

/* 上证云角标 */
.node-sse-badge {
  display: inline-block;
  font-size: 9px;
  color: #fff;
  background: #9c27b0;
  border-radius: 3px;
  padding: 0 4px;
  margin-left: 4px;
  vertical-align: middle;
  line-height: 16px;
}

.node-has-live {
  box-shadow: 0 0 0 2px #67c23a, 0 1px 4px rgba(0,0,0,0.08);
}
/* 上证云 + 有下游客户端：同时显示紫色和绿色双边框 */
.node-sse-cloud.node-has-live {
  box-shadow: 0 0 0 2px #9c27b0, 0 0 0 4px #67c23a, 0 1px 4px rgba(0,0,0,0.08);
}

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
.node-client-badge:hover { background: #4caf50; }

.client-pop-header {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ===== 文字链路模式 ===== */
.text-chain-wrap {
  padding: 16px 8px;
  max-height: 600px;
  overflow-y: auto;
  background: #fafafa;
  border-radius: 4px;
}
.text-chain-tree {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e4e7ed;
}
.text-chain-tree:last-child { border-bottom: none; margin-bottom: 0; }
.text-chain-row {
  padding: 4px 0;
  font-size: 13px;
  color: #303133;
  font-family: 'Consolas', 'Monaco', 'Menlo', monospace;
  line-height: 1.7;
  white-space: nowrap;
}
.text-chain-row:hover { background: #f0f7ff; }
.text-chain-indent {
  color: #c0c4cc;
  margin-right: 4px;
  user-select: none;
}
.text-chain-type {
  display: inline-block;
  font-size: 11px;
  color: #fff;
  border-radius: 3px;
  padding: 0 5px;
  margin-right: 6px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  vertical-align: middle;
  line-height: 18px;
}
.tc-external   { background: #f56c6c; }
.tc-receiver   { background: #e6a23c; }
.tc-forwarder  { background: #409eff; }
.tc-aggregator { background: #67c23a; }
.text-chain-name {
  font-weight: 600;
  margin-right: 4px;
}
.text-chain-ip {
  color: #909399;
  font-size: 12px;
}
.text-chain-live {
  margin-left: 8px;
  color: #67c23a;
  font-size: 11px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.text-chain-live-click {
  cursor: pointer;
  border-bottom: 1px dashed #67c23a;
  padding-bottom: 1px;
}
.text-chain-live-click:hover {
  color: #4caf50;
  border-bottom-color: #4caf50;
}
.text-chain-indent-live {
  color: #67c23a !important;
}
</style>
