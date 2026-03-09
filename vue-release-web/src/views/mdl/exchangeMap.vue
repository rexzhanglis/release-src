<template>
  <div class="exchange-map">
    <el-card shadow="never">
      <div slot="header" class="card-header">
        <i class="el-icon-connection" style="color:#409eff" />
        <span>接收机 IP → 交易所映射表</span>
        <div style="margin-left:auto;display:flex;align-items:center;gap:10px">
          <el-input
            v-model="keyword"
            placeholder="搜索交易所 / IP"
            prefix-icon="el-icon-search"
            clearable size="small"
            style="width:220px"
          />
          <el-select
            v-model="filterExchange"
            placeholder="筛选交易所"
            clearable size="small"
            style="width:160px"
          >
            <el-option v-for="name in exchangeNames" :key="name" :label="name" :value="name" />
          </el-select>
          <span class="total-tip">共 <b>{{ filtered.length }}</b> 条，<b>{{ exchangeNames.length }}</b> 个交易所</span>
        </div>
      </div>

      <el-table
        :data="filtered"
        border
        size="small"
        :row-class-name="tableRowClass"
        style="width:100%"
      >
        <el-table-column prop="exchange" label="交易所" width="180">
          <template slot-scope="{ row }">
            <el-tag :type="exchangeTagType(row.exchange)" size="small" style="font-weight:600">
              {{ row.exchange }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="我司接收机 IP" min-width="180">
          <template slot-scope="{ row }">
            <span class="mono">{{ row.ip }}</span>
          </template>
        </el-table-column>
        <el-table-column label="运营商" width="100">
          <template slot-scope="{ row }">
            <el-tag v-if="OPERATOR_MAP[row.ip.split(':')[0]]" size="mini" :type="operatorTagType(row.ip)">
              {{ OPERATOR_MAP[row.ip.split(':')[0]] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="180">
          <template slot-scope="{ row }">
            <span class="gray">{{ REMARK_MAP[row.ip] || '' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { getExchangeMap } from '@/api/forwarderChain'

const OPERATOR_MAP = {
  '10.22.240.122': '联通',  '10.22.240.123': '移动',
  '10.24.71.135':  '电信',  '10.24.71.136':  '联通',
  '10.22.240.37':  '移动',  '10.22.240.68':  '联通',
  '10.22.240.55':  '移动',  '10.22.240.86':  '联通',
  '10.21.249.51':  '移动',  '10.21.249.52':  '联通',
  '10.22.240.109': '电信',  '10.22.240.60':  '联通',
  '10.22.240.79':  '',
  '10.22.240.58':  '移动',  '10.22.240.59':  '联通',
  '10.226.21.197': '移动',  '10.226.99.2':   '联通',
  '10.22.240.206': '电信',  '10.22.241.200': '',
  '10.22.240.111': '电信',  '10.22.240.112': '联通',
  '10.22.240.91':  '电信',  '10.22.240.96':  'VDE',
  '10.22.240.207': '电信',
  '10.45.1.2':     'HKBN',
  '10.24.71.45':   '',      '10.24.71.23':   '',
  '10.24.71.36':   '',      '10.24.71.70':   '',
  '10.22.240.113': '',      '10.22.240.114': '',
  '10.20.205.181': 'VPN',
}

const REMARK_MAP = {
  '10.22.240.96:9010': '复用上交所联通专线（深L1期权）',
  '10.22.240.96:9011': '复用上交所联通专线（北交所债券）',
  '10.22.241.200':     '复用深L2移动专线（深L1股指/基指备）',
  '10.22.240.91':      '复用深交所新三板电信专线',
  '10.24.71.135':      '与国证指数同机，端口区分：9010=国证，9011=大商所指数',
  '10.24.71.136':      '与国证指数同机，端口区分：9010=国证，9011=大商所指数',
  '10.22.240.113':     '与福汇同机，端口区分：9010=南华指数，9011=福汇',
  '10.22.240.114':     '与福汇同机，端口区分：9010=南华指数，9011=福汇',
  '10.24.71.135:9010': '同机器 9011 端口接大商所指数',
  '10.24.71.136:9010': '同机器 9011 端口接大商所指数',
  '10.20.205.181':     '跳板机VPN，Windows接收机，无法追溯专线路由',
}

const EXCHANGE_TAG_TYPE = {
  '大商所': '', '大商所指数': 'info',
  '郑商所': 'warning', '中金所': 'danger',
  '上期所': '', '上交所': 'success',
  '上海黄金交易所': 'warning', '广期所': 'danger',
  '深交所L1': 'success', '深交所L1(VDE)': 'success', '深交所L2': 'success',
  '新三板': 'info', '北交所债券': 'info', '北交所债券(VDE)': 'info',
  '港交所(恒指)': '', '港交所(直连)': '',
  '国证指数': 'info', '中证指数': 'info', '申万指数': 'info',
  '南华指数': 'info', '福汇': '',
  '上证云': 'info',
}

export default {
  name: 'ExchangeMap',
  data() {
    return {
      mapList: [],
      keyword: '',
      filterExchange: '',
      OPERATOR_MAP,
      REMARK_MAP,
    }
  },
  computed: {
    exchangeNames() {
      return [...new Set(this.mapList.map(r => r.exchange))].sort()
    },
    filtered() {
      const kw = this.keyword.trim().toLowerCase()
      return this.mapList.filter(r => {
        if (this.filterExchange && r.exchange !== this.filterExchange) return false
        if (kw && !r.ip.includes(kw) && !r.exchange.toLowerCase().includes(kw)) return false
        return true
      })
    },
  },
  created() {
    this.fetchMap()
  },
  methods: {
    async fetchMap() {
      try {
        const res = await getExchangeMap()
        this.mapList = res.data || []
      } catch {
        this.$message.error('加载失败')
      }
    },
    exchangeTagType(name) {
      return EXCHANGE_TAG_TYPE[name] || ''
    },
    operatorTagType(ip) {
      const op = OPERATOR_MAP[ip.split(':')[0]] || ''
      return { '移动': '', '联通': 'success', '电信': 'warning', 'VDE': 'info', 'HKBN': 'info', 'VPN': 'info' }[op] || 'info'
    },
    tableRowClass({ row }) {
      const idx = this.exchangeNames.indexOf(row.exchange)
      return idx % 2 === 0 ? 'row-even' : 'row-odd'
    },
  },
}
</script>

<style scoped>
.exchange-map { padding: 16px; }
.card-header { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: bold; }
.total-tip { font-size: 12px; color: #909399; white-space: nowrap; }
.mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; color: #303133; }
.gray { color: #909399; font-size: 12px; }
</style>

<style>
.exchange-map .row-even td { background: #fafafa !important; }
.exchange-map .row-odd  td { background: #fff    !important; }
</style>
