<template>
  <div class="exchange-map">
    <el-card shadow="never" class="filter-card">
      <div class="filter-bar">
        <el-input
          v-model="keyword"
          placeholder="搜索交易所名称 / IP"
          prefix-icon="el-icon-search"
          clearable
          size="small"
          style="width:280px"
        />
        <el-select
          v-model="filterExchange"
          placeholder="筛选交易所"
          clearable size="small"
          style="width:200px;margin-left:10px"
        >
          <el-option v-for="name in exchangeNames" :key="name" :label="name" :value="name" />
        </el-select>
        <span class="total-tip">共 <b>{{ filtered.length }}</b> 条 IP 映射，涉及 <b>{{ exchangeNames.length }}</b> 个交易所</span>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top:12px">
      <div slot="header" class="card-header">
        <i class="el-icon-connection" style="color:#409eff" />
        <span>交易所对端 IP 映射表</span>
        <el-tag size="mini" type="info" style="margin-left:8px">来源：交易所专线路由（主备）.doc</el-tag>
      </div>

      <!-- 按交易所分组展示 -->
      <div v-for="group in groupedFiltered" :key="group.exchange" class="exchange-group">
        <div class="group-header">
          <span class="group-name">{{ group.exchange }}</span>
          <el-tag size="mini" type="info">{{ group.ips.length }} 个 IP</el-tag>
        </div>
        <div class="ip-grid">
          <div
            v-for="item in group.ips"
            :key="item.ip"
            class="ip-chip"
          >
            <span class="ip-text">{{ item.ip }}</span>
          </div>
        </div>
      </div>

      <div v-if="groupedFiltered.length === 0" class="empty-tip">
        无匹配结果
      </div>
    </el-card>
  </div>
</template>

<script>
import { getExchangeMap } from '@/api/forwarderChain'

export default {
  name: 'ExchangeMap',
  data() {
    return {
      mapList: [],   // [{ ip, exchange }, ...]
      keyword: '',
      filterExchange: '',
    }
  },
  computed: {
    exchangeNames() {
      const names = [...new Set(this.mapList.map(r => r.exchange))]
      return names.sort()
    },
    filtered() {
      const kw = this.keyword.trim().toLowerCase()
      return this.mapList.filter(r => {
        if (this.filterExchange && r.exchange !== this.filterExchange) return false
        if (kw && !r.ip.includes(kw) && !r.exchange.toLowerCase().includes(kw)) return false
        return true
      })
    },
    groupedFiltered() {
      const map = {}
      for (const r of this.filtered) {
        if (!map[r.exchange]) map[r.exchange] = []
        map[r.exchange].push(r)
      }
      return Object.entries(map)
        .sort(([a], [b]) => a.localeCompare(b, 'zh'))
        .map(([exchange, ips]) => ({ exchange, ips }))
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
      } catch (e) {
        this.$message.error('加载失败')
      }
    },
  },
}
</script>

<style scoped>
.exchange-map { padding: 16px; }
.filter-card { margin-bottom: 0; }
.filter-bar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.total-tip { margin-left: 16px; font-size: 13px; color: #909399; }
.card-header { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: bold; }

.exchange-group {
  margin-bottom: 20px;
}
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}
.group-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.ip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ip-chip {
  background: #f4f4f5;
  border: 1px solid #e9e9eb;
  border-radius: 4px;
  padding: 3px 10px;
}
.ip-text {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: #303133;
}
.empty-tip {
  text-align: center;
  color: #c0c4cc;
  padding: 40px 0;
  font-size: 13px;
}
</style>
