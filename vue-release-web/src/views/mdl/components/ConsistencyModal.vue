<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="配置一致性巡检"
    width="900px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <!-- 筛选 -->
    <el-form :inline="true" size="small" style="margin-bottom:12px">
      <el-form-item label="服务类型">
        <el-select
          v-model="filterServiceType"
          clearable
          placeholder="全部"
          style="width:150px"
          @change="runCheck"
        >
          <el-option
            v-for="st in serviceTypes"
            :key="st.id"
            :label="st.name"
            :value="st.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="文件名">
        <el-input
          v-model="filterFilename"
          clearable
          placeholder="如 feeder_handler.cfg"
          style="width:200px"
          @change="runCheck"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="el-icon-search" :loading="loading" @click="runCheck">
          开始巡检
        </el-button>
      </el-form-item>
      <el-form-item v-if="report.length">
        <el-tag :type="inconsistentCount > 0 ? 'danger' : 'success'" style="font-size:13px">
          {{ inconsistentCount > 0 ? `发现 ${inconsistentCount} 组不一致` : '全部一致' }}
        </el-tag>
      </el-form-item>
    </el-form>

    <!-- 结果列表 -->
    <div v-loading="loading">
      <template v-if="report.length">
        <!-- 只显示有差异的，一致的折叠 -->
        <div class="check-legend">
          <el-checkbox v-model="showConsistent">显示一致项</el-checkbox>
        </div>
        <el-collapse v-model="openGroups">
          <el-collapse-item
            v-for="(group, idx) in filteredReport"
            :key="idx"
            :name="idx"
          >
            <template slot="title">
              <span class="group-title">
                <el-tag
                  :type="group.consistent ? 'success' : 'danger'"
                  size="small"
                  style="margin-right:8px"
                >{{ group.consistent ? '一致' : `差异 ${group.diff_keys.length} 项` }}</el-tag>
                <span class="group-name">{{ group.service_type }}</span>
                <i class="el-icon-arrow-right group-sep"></i>
                <span class="group-file">{{ group.filename }}</span>
                <span class="group-inst-count">（{{ group.instance_count }} 个实例）</span>
              </span>
            </template>

            <div v-if="group.consistent" class="consistent-tip">
              <i class="el-icon-circle-check" style="color:#67c23a"></i>
              所有实例的此文件配置完全一致
            </div>
            <template v-else>
              <el-table
                :data="group.diff_keys"
                size="mini"
                border
                style="width:100%"
              >
                <el-table-column prop="key" label="配置 Key" width="240" show-overflow-tooltip />
                <el-table-column label="各实例值">
                  <template slot-scope="{ row }">
                    <div
                      v-for="(val, instName) in row.values"
                      :key="instName"
                      class="inst-value-row"
                    >
                      <span class="inst-name-label">{{ instName }}</span>
                      <code class="inst-value-code">{{ val }}</code>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </el-collapse-item>
        </el-collapse>
      </template>

      <div v-else-if="!loading && hasChecked" class="empty-tip">
        <i class="el-icon-circle-check" style="font-size:40px;color:#67c23a"></i>
        <p>未发现配置差异</p>
      </div>
      <div v-else-if="!loading" class="empty-tip">
        <i class="el-icon-search" style="font-size:40px;color:#dcdfe6"></i>
        <p style="color:#909399">点击"开始巡检"对比实例间配置差异</p>
      </div>
    </div>

    <div slot="footer">
      <el-button @click="dialogVisible = false">关闭</el-button>
    </div>
  </el-dialog>
</template>

<script>
import { consistencyCheck, getServiceTypes } from '@/api/configMgmt'

export default {
  name: 'ConsistencyModal',
  props: {
    value: { type: Boolean, default: false }
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(v) { this.$emit('input', v) }
    },
    filteredReport() {
      if (this.showConsistent) return this.report
      return this.report.filter(g => !g.consistent)
    },
    inconsistentCount() {
      return this.report.filter(g => !g.consistent).length
    }
  },
  data() {
    return {
      loading: false,
      hasChecked: false,
      report: [],
      serviceTypes: [],
      filterServiceType: null,
      filterFilename: '',
      showConsistent: false,
      openGroups: [],
    }
  },
  methods: {
    async handleOpen() {
      if (!this.serviceTypes.length) {
        try {
          const res = await getServiceTypes()
          this.serviceTypes = res.data || []
        } catch {}
      }
    },
    async runCheck() {
      this.loading = true
      this.hasChecked = false
      try {
        const params = {}
        if (this.filterServiceType) params.service_type_id = this.filterServiceType
        if (this.filterFilename.trim()) params.filename = this.filterFilename.trim()
        const res = await consistencyCheck(params)
        this.report = res.data.report || []
        this.hasChecked = true
        // 默认展开有差异的项
        this.openGroups = this.report
          .map((g, i) => ({ consistent: g.consistent, i }))
          .filter(x => !x.consistent)
          .map(x => x.i)
      } catch (e) {
        this.$message.error('巡检失败')
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.check-legend {
  margin-bottom: 10px;
  font-size: 13px;
  color: #606266;
}

.group-title {
  display: flex;
  align-items: center;
  font-size: 13px;
}
.group-name {
  font-weight: 600;
  color: #303133;
}
.group-sep {
  margin: 0 6px;
  color: #c0c4cc;
  font-size: 12px;
}
.group-file {
  color: #409eff;
  font-family: monospace;
}
.group-inst-count {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.consistent-tip {
  color: #67c23a;
  font-size: 13px;
  padding: 8px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.inst-value-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 4px;
  gap: 8px;
  font-size: 12px;
}
.inst-name-label {
  min-width: 160px;
  color: #606266;
  font-size: 11px;
  padding-top: 2px;
  flex-shrink: 0;
}
.inst-value-code {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 3px;
  padding: 1px 6px;
  font-family: monospace;
  font-size: 12px;
  color: #303133;
  word-break: break-all;
}

.empty-tip {
  text-align: center;
  padding: 40px 0;
  color: #909399;
  font-size: 13px;
}
</style>
