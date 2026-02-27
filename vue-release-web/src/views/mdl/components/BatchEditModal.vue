<template>
  <el-dialog
    :visible.sync="dialogVisible"
    title="批量修改配置"
    width="900px"
    :close-on-click-modal="false"
    @open="handleOpen"
  >
    <!-- 选中实例列表 -->
    <div class="instance-summary">
      <div class="instance-summary-title">
        <i class="el-icon-monitor" style="color:#409eff"></i>
        将对以下 <strong>{{ checkedInstanceIds.length }}</strong> 个实例进行批量修改
      </div>
      <div class="instance-tags">
        <span
          v-for="inst in checkedInstances"
          :key="inst.id"
          class="inst-tag"
        >
          <span class="inst-tag-name">{{ inst.name }}</span>
          <span v-if="inst.host_ip" class="inst-tag-ip">{{ inst.host_ip }}</span>
          <el-tooltip v-if="inst.host_ip" content="复制 SSH 命令" placement="top">
            <i
              class="el-icon-copy-document inst-tag-copy"
              @click="copySSH(inst)"
            ></i>
          </el-tooltip>
        </span>
      </div>
    </div>

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

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- ======== Tab 1: 结构化修改 ======== -->
      <el-tab-pane label="结构化修改" name="structured">
        <div class="schema-area" v-loading="loadingSchema">
          <el-divider content-position="left">选择要修改的配置项</el-divider>
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
                    <el-button
                      size="mini" type="danger" icon="el-icon-delete" circle plain
                      style="margin-left:auto"
                      title="删除该配置项（所有实例）"
                      @click="handleMarkDelete(item)"
                    />
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

        <!-- 新增 key -->
        <el-divider content-position="left">新增配置项</el-divider>
        <el-form :inline="true" size="small" style="margin-bottom:8px">
          <el-form-item label="key路径">
            <el-input v-model="newKeyPath" placeholder="如 server.port" style="width:200px" />
          </el-form-item>
          <el-form-item label="值">
            <el-input v-model="newKeyValue" placeholder="值（支持JSON）" style="width:200px" />
          </el-form-item>
          <el-form-item>
            <el-button type="success" icon="el-icon-plus" @click="handleAddKey">添加</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- ======== Tab 2: 文本查找替换 ======== -->
      <el-tab-pane label="文本查找替换" name="text_replace">
        <div class="text-replace-area">
          <el-form label-width="80px" size="small" style="margin-bottom:12px">
            <el-form-item label="查找">
              <el-input
                v-model="searchText"
                placeholder="输入要查找的文本（区分大小写）"
                clearable
              />
            </el-form-item>
            <el-form-item label="替换为">
              <el-input
                v-model="replaceText"
                placeholder="替换为（留空表示删除）"
                clearable
              />
            </el-form-item>
          </el-form>

          <div style="margin-bottom:12px">
            <el-button
              type="primary"
              icon="el-icon-search"
              :loading="previewing"
              :disabled="!filename || !searchText"
              @click="handlePreview"
            >预览</el-button>
            <span v-if="previewResults.length" style="margin-left:12px;color:#606266;font-size:13px">
              共 {{ previewMatchTotal }} 处匹配，影响 {{ previewChangedCount }} 个实例
            </span>
          </div>

          <!-- 预览结果表格 -->
          <div v-if="previewResults.length" class="preview-table-wrap">
            <el-table :data="previewResults" size="small" border style="width:100%">
              <el-table-column prop="instance_name" label="实例" min-width="160" />
              <el-table-column prop="match_count" label="匹配数" width="80" align="center">
                <template slot-scope="{ row }">
                  <el-tag :type="row.match_count > 0 ? 'danger' : 'info'" size="mini">
                    {{ row.match_count }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="差异预览" min-width="300">
                <template slot-scope="{ row }">
                  <div v-if="row.error" style="color:#f56c6c;font-size:12px">{{ row.error }}</div>
                  <div v-else-if="row.match_count === 0" style="color:#999;font-size:12px">无匹配</div>
                  <div v-else-if="row.diff_preview && row.diff_preview.length" class="diff-preview">
                    <div v-for="(d, idx) in row.diff_preview" :key="idx" class="diff-line">
                      <span class="diff-lineno">L{{ d.line }}</span>
                      <span class="diff-old">- {{ d.old }}</span>
                      <span class="diff-new">+ {{ d.new }}</span>
                    </div>
                    <div v-if="row.match_count > 5" class="diff-more">... 共 {{ row.match_count }} 处</div>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <div v-else-if="previewDone" style="color:#999;text-align:center;padding:16px">
            所有实例均无匹配内容
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <div slot="footer">
      <el-button @click="dialogVisible = false">取消</el-button>

      <!-- 结构化修改确认 -->
      <el-button
        v-if="activeTab === 'structured'"
        type="primary"
        :loading="submitting"
        :disabled="selectedItems.length === 0 && addedItems.length === 0"
        @click="handleSubmit"
      >
        应用修改 ({{ selectedItems.length + addedItems.length }} 项)
      </el-button>

      <!-- 文本替换确认 -->
      <el-button
        v-if="activeTab === 'text_replace'"
        type="warning"
        :loading="replacing"
        :disabled="previewChangedCount === 0"
        @click="handleApplyReplace"
      >
        应用替换 ({{ previewChangedCount }} 个实例)
      </el-button>
    </div>
  </el-dialog>
</template>

<script>
import { getConfigSchema, batchUpdateConfig, textReplace } from '@/api/configMgmt'

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
    },
    checkedInstances: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    dialogVisible: {
      get() { return this.value },
      set(val) { this.$emit('input', val) }
    },
    previewMatchTotal() {
      return this.previewResults.reduce((sum, r) => sum + (r.match_count || 0), 0)
    },
    previewChangedCount() {
      return this.previewResults.filter(r => r.changed).length
    }
  },
  data() {
    return {
      activeTab: 'structured',
      filename: '',
      filenames: [],
      loadingSchema: false,
      submitting: false,
      treeData: [],
      selectedItems: [],
      valuesMap: {},
      allInstanceNames: [],
      addedItems: [],
      newKeyPath: '',
      newKeyValue: '',
      // 文本替换
      searchText: '',
      replaceText: '',
      previewing: false,
      replacing: false,
      previewResults: [],
      previewDone: false
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
      this.addedItems = []
      this.newKeyPath = ''
      this.newKeyValue = ''
      this.activeTab = 'structured'
      this.searchText = ''
      this.replaceText = ''
      this.previewResults = []
      this.previewDone = false

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
      // 切换文件时清空预览
      this.previewResults = []
      this.previewDone = false

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
        activeNames: []
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

    handleMarkDelete(item) {
      this.$confirm(`确认删除配置项 "${item.path}"？将对所有选中实例生效。`, '删除确认', {
        type: 'warning'
      }).then(() => {
        item.newValue = '__DELETE__'
        item.isDelete = true
      }).catch(() => {})
    },

    handleAddKey() {
      const path = this.newKeyPath.trim()
      const val = this.newKeyValue.trim()
      if (!path) {
        this.$message.warning('请输入 key 路径')
        return
      }
      if (this.addedItems.find(i => i.path === path) || this.selectedItems.find(i => i.path === path)) {
        this.$message.warning('该路径已存在')
        return
      }
      this.addedItems.push({ path, newValue: val, isAdd: true })
      this.newKeyPath = ''
      this.newKeyValue = ''
    },

    async handleSubmit() {
      const modifyItems = this.selectedItems.filter(item => item.newValue !== '')
      const allItems = [...modifyItems, ...this.addedItems]
      if (!allItems.length) {
        this.$message.warning('请至少填写一个新值或新增一个配置项')
        return
      }

      const updates = {}
      for (const item of allItems) {
        updates[item.path] = item.newValue === '__DELETE__' ? '__DELETE__' : this.parseValue(item.newValue)
      }

      this.submitting = true
      try {
        await batchUpdateConfig({
          instance_ids: this.checkedInstanceIds,
          filename: this.filename,
          updates
        })
        this.$message.success(`批量操作成功，共 ${allItems.length} 项`)
        this.dialogVisible = false
        this.$emit('success')
      } catch (e) {
        this.$message.error('批量修改失败')
      } finally {
        this.submitting = false
      }
    },

    copySSH(inst) {
      const cmd = `ssh ${inst.host_ip}`
      if (navigator.clipboard) {
        navigator.clipboard.writeText(cmd).then(() => {
          this.$message.success(`已复制: ${cmd}`)
        })
      } else {
        // 降级方案
        const el = document.createElement('textarea')
        el.value = cmd
        document.body.appendChild(el)
        el.select()
        document.execCommand('copy')
        document.body.removeChild(el)
        this.$message.success(`已复制: ${cmd}`)
      }
    },

    // -------- 文本替换 --------

    async handlePreview() {
      if (!this.filename || !this.searchText) return
      this.previewing = true
      this.previewDone = false
      this.previewResults = []
      try {
        const res = await textReplace({
          instance_ids: this.checkedInstanceIds,
          filename: this.filename,
          search_text: this.searchText,
          replace_text: this.replaceText,
          preview: true
        })
        this.previewResults = res.data.results || []
        this.previewDone = true
      } catch (e) {
        this.$message.error('预览失败')
      } finally {
        this.previewing = false
      }
    },

    async handleApplyReplace() {
      if (this.previewChangedCount === 0) return
      try {
        await this.$confirm(
          `将对 ${this.previewChangedCount} 个实例应用文本替换（共 ${this.previewMatchTotal} 处），确认继续？`,
          '确认替换', { type: 'warning' }
        )
      } catch (e) { return }

      this.replacing = true
      try {
        const res = await textReplace({
          instance_ids: this.checkedInstanceIds,
          filename: this.filename,
          search_text: this.searchText,
          replace_text: this.replaceText,
          preview: false
        })
        const d = res.data
        this.$message.success(`替换完成，共修改 ${d.changed_count} 个实例`)
        this.dialogVisible = false
        this.$emit('success')
      } catch (e) {
        this.$message.error('替换失败')
      } finally {
        this.replacing = false
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
  max-height: 360px;
}
.edit-side {
  flex: 1;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
  overflow-y: auto;
  max-height: 360px;
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

/* 实例摘要 */
.instance-summary {
  background: #f0f7ff;
  border: 1px solid #d0e8ff;
  border-radius: 4px;
  padding: 10px 14px;
  margin-bottom: 14px;
}
.instance-summary-title {
  font-size: 13px;
  color: #303133;
  margin-bottom: 8px;
}
.instance-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.inst-tag {
  display: inline-flex;
  align-items: center;
  background: #fff;
  border: 1px solid #c6e0f5;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 12px;
  gap: 6px;
}
.inst-tag-name {
  font-weight: 600;
  color: #303133;
}
.inst-tag-ip {
  color: #409eff;
  font-family: monospace;
}
.inst-tag-copy {
  color: #909399;
  cursor: pointer;
  font-size: 13px;
}
.inst-tag-copy:hover {
  color: #409eff;
}

/* 文本替换 Tab */
.text-replace-area {
  padding: 8px 0;
}
.preview-table-wrap {
  max-height: 340px;
  overflow-y: auto;
}
.diff-preview {
  font-family: monospace;
  font-size: 12px;
}
.diff-line {
  display: flex;
  flex-direction: column;
  margin-bottom: 4px;
  padding: 2px 4px;
  background: #fafafa;
  border-radius: 2px;
}
.diff-lineno {
  color: #909399;
  font-size: 11px;
}
.diff-old {
  color: #f56c6c;
  white-space: pre-wrap;
  word-break: break-all;
}
.diff-new {
  color: #67c23a;
  white-space: pre-wrap;
  word-break: break-all;
}
.diff-more {
  color: #909399;
  font-size: 11px;
  font-style: italic;
}
</style>
