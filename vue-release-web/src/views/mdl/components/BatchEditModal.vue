<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="批量修改配置"
    width="850px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <el-alert type="info" :closable="false" style="margin-bottom: 16px">
      将对选中的 {{ checkedInstanceIds.length }} 个实例进行批量修改
    </el-alert>

    <el-form label-width="100px">
      <el-form-item label="配置文件">
        <el-select
          v-model="filename"
          placeholder="选择配置文件"
          style="width: 100%"
          @change="handleFilenameChange"
        >
          <el-option v-for="f in filenames" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-divider content-position="left">选择要修改的配置项</el-divider>

    <div class="schema-area" v-loading="loadingSchema">
      <div v-if="treeData.length" class="tree-edit-layout">
        <!-- 左侧树 -->
        <div class="tree-side">
          <el-tree
            ref="schemaTree"
            :data="treeData"
            :props="{ label: 'label', children: 'children' }"
            node-key="path"
            show-checkbox
            default-expand-all
            :expand-on-click-node="false"
            @check="handleTreeCheck"
          >
            <span slot-scope="{ data }" class="tree-node">
              <span class="tree-node-label">{{ data.label }}</span>
              <el-tag
                v-if="!data.children && data.allSame"
                size="mini" type="info" style="margin-left:6px"
              >
                {{ formatValueTag(data.currentValue) }}
              </el-tag>
              <el-tag
                v-else-if="!data.children && !data.allSame"
                size="mini" type="warning" style="margin-left:6px"
              >
                值不同
              </el-tag>
            </span>
          </el-tree>
        </div>

        <!-- 右侧编辑区 -->
        <div class="edit-side">
          <div v-if="selectedItems.length === 0" class="edit-empty">
            <p style="color:#999;text-align:center;padding:20px">从左侧勾选要修改的配置项</p>
          </div>
          <div v-else class="edit-list">
            <div v-for="item in selectedItems" :key="item.path" class="edit-item">
              <div class="edit-item-header">
                <span class="edit-item-path">{{ item.path }}</span>
                <el-tag v-if="item.allSame" size="mini" type="info" style="margin-left:6px">
                  统一值: {{ formatDisplay(item.currentValue) }}
                </el-tag>
                <el-tag v-else size="mini" type="warning" style="margin-left:6px">各实例值不同</el-tag>
              </div>
              <div v-if="!item.allSame" class="instance-values">
                <div v-for="instName in allInstanceNames" :key="instName" class="instance-value-row">
                  <span class="inst-name">{{ instName }}</span>
                  <span class="inst-val" :class="{'missing-val': item.instanceValues[instName] === undefined}">
                    {{ item.instanceValues[instName] === undefined ? '(不存在)' : formatDisplay(item.instanceValues[instName]) }}
                  </span>
                </div>
              </div>
              <div v-else class="instance-values">
                 <el-collapse v-model="item.activeNames">
                   <el-collapse-item title="查看各实例当前值（全部相同）" name="1">
                     <div v-for="instName in allInstanceNames" :key="instName" class="instance-value-row">
                       <span class="inst-name">{{ instName }}</span>
                       <span class="inst-val" :class="{'missing-val': item.instanceValues[instName] === undefined}">
                         {{ item.instanceValues[instName] === undefined ? '(不存在)' : formatDisplay(item.instanceValues[instName]) }}
                       </span>
                     </div>
                   </el-collapse-item>
                 </el-collapse>
              </div>
              <el-input
                v-model="item.newValue"
                :placeholder="item.allSame ? `当前: ${formatDisplay(item.currentValue)}` : '输入新值（将覆盖所有实例）'"
                size="small"
              >
                <template slot="prepend">新值</template>
              </el-input>
            </div>
          </div>
        </div>
      </div>
      <p v-else-if="!loadingSchema && filename" style="color:#999;text-align:center;padding:20px">该配置文件无内容</p>
      <p v-else-if="!loadingSchema" style="color:#999;text-align:center;padding:20px">请先选择配置文件</p>
    </div>

    <div slot="footer">
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="selectedItems.length === 0"
        @click="handleSubmit"
      >
        应用修改 ({{ selectedItems.length }} 项)
      </el-button>
    </div>
  </el-dialog>
</template>

<script>
import { getConfigSchema, batchUpdateConfig } from '@/api/configMgmt'

export default {
  name: 'BatchEditModal',
  props: {
    value: {
      type: Boolean,
      default: false
    },
    checkedInstanceIds: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) }
    }
  },
  data() {
    return {
      filename: '',
      filenames: [],
      loadingSchema: false,
      submitting: false,
      treeData: [],
      selectedItems: [],
      valuesMap: {},
      allInstanceNames: []
    }
  },
  methods: {
    async handleOpen() {
      this.filename = ''
      this.filenames = []
      this.treeData = []
      this.selectedItems = []
      this.valuesMap = {}
      this.allInstanceNames = []

      if (!this.checkedInstanceIds.length) return

      this.loadingSchema = true
      try {
        const res = await getConfigSchema({ instance_ids: this.checkedInstanceIds })
        const data = res.data
        this.filenames = data.filenames || []
        if (this.filenames.length === 1) {
          this.filename = this.filenames[0]
          await this.handleFilenameChange(this.filename)
        }
      } catch (e) {
        this.$message.error('获取配置文件列表失败')
      } finally {
        this.loadingSchema = false
      }
    },

    async handleFilenameChange(val) {
      if (!val) {
        this.treeData = []
        this.selectedItems = []
        this.valuesMap = {}
        this.allInstanceNames = []
        return
      }

      this.loadingSchema = true
      try {
        const res = await getConfigSchema({
          instance_ids: this.checkedInstanceIds,
          filename: val
        })
        const data = res.data
        this.valuesMap = data.values_map || {}
        
        // 收集所有实例名
        const names = new Set()
        Object.values(this.valuesMap).forEach(instMap => {
          Object.keys(instMap).forEach(n => names.add(n))
        })
        this.allInstanceNames = Array.from(names).sort()

        this.treeData = this.jsonToTree(data.schema || {}, '', '', this.valuesMap)
        this.selectedItems = []
      } catch (e) {
        this.$message.error('获取配置结构失败')
      } finally {
        this.loadingSchema = false
      }
    },

    jsonToTree(value, prefix, label, vMap) {
      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        const nodes = []
        for (const [k, v] of Object.entries(value)) {
          const path = prefix ? `${prefix}.${k}` : k
          nodes.push(this.jsonToTree(v, path, k, vMap))
        }
        if (!label) return nodes
        return { label, path: prefix, children: nodes }
      }

      if (Array.isArray(value)) {
        const children = value.map((item, idx) => {
          const path = `${prefix}[${idx}]`
          return this.jsonToTree(item, path, `[${idx}]`, vMap)
        })
        return { label: label || prefix, path: prefix, children }
      }

      const instanceValues = vMap[prefix] || {}
      const vals = Object.values(instanceValues)
      const allSame = vals.length > 0 && vals.every(v => JSON.stringify(v) === JSON.stringify(vals[0]))
      return {
        label: label || prefix,
        path: prefix,
        currentValue: allSame ? vals[0] : value,
        allSame,
        instanceValues
      }
    },

    handleTreeCheck() {
      const checked = this.$refs.schemaTree.getCheckedNodes(true, false)
      const leafNodes = checked.filter(n => !n.children)
      const existingMap = {}
      this.selectedItems.forEach(item => { existingMap[item.path] = item.newValue })
      this.selectedItems = leafNodes.map(n => ({
        path: n.path,
        currentValue: n.currentValue,
        allSame: n.allSame,
        instanceValues: n.instanceValues || {},
        newValue: existingMap[n.path] !== undefined ? existingMap[n.path] : '',
        activeNames: [] // for collapse
      }))
    },

    formatValueTag(value) {
      if (value === null) return 'null'
      if (typeof value === 'boolean') return value ? 'true' : 'false'
      if (typeof value === 'number') return String(value)
      if (Array.isArray(value)) return `[${value.length}]`
      const str = String(value)
      return str.length > 15 ? str.slice(0, 15) + '...' : str
    },

    formatDisplay(value) {
      if (value === null) return 'null'
      if (Array.isArray(value)) return JSON.stringify(value)
      return String(value)
    },

    parseValue(str) {
      if (str === '') return str
      try { return JSON.parse(str) } catch (e) { return str }
    },

    async handleSubmit() {
      const validItems = this.selectedItems.filter(item => item.newValue !== '')
      if (!validItems.length) {
        this.$message.warning('请至少填写一个新值')
        return
      }

      const updates = {}
      for (const item of validItems) {
        updates[item.path] = this.parseValue(item.newValue)
      }

      this.submitting = true
      try {
        await batchUpdateConfig({
          instance_ids: this.checkedInstanceIds,
          filename: this.filename,
          updates
        })
        this.$message.success(`批量修改成功，更新了 ${validItems.length} 个配置项`)
        this.dialogVisible = false
        this.$emit('success')
      } catch (e) {
        this.$message.error('批量修改失败')
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.tree-edit-layout {
  display: flex;
  gap: 16px;
  min-height: 300px;
}
.tree-side {
  flex: 1;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
  overflow-y: auto;
  max-height: 400px;
}
.edit-side {
  flex: 1;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
  overflow-y: auto;
  max-height: 400px;
}
.edit-item {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}
.edit-item-header {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}
.edit-item-path {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}
.instance-values {
  margin-bottom: 6px;
  font-size: 12px;
  color: #606266;
}
.instance-value-row {
  display: flex;
  gap: 8px;
  padding: 2px 0;
}
.inst-name { color: #409eff; min-width: 120px; }
.inst-val { color: #606266; }
.tree-node { display: flex; align-items: center; }
.tree-node-label { font-size: 13px; }
.missing-val { color: #f56c6c; font-style: italic; }
</style>
