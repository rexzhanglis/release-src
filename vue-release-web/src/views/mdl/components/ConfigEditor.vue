<template>
  <div class="config-editor-wrap">
    <div class="editor-toolbar">
      <span v-if="autoSaveStatus === 'saving'" class="autosave-tip saving">
        <i class="el-icon-loading"></i> 保存中...
      </span>
      <span v-else-if="autoSaveStatus === 'saved'" class="autosave-tip saved">
        <i class="el-icon-check"></i> 已自动保存
      </span>
      <span v-else-if="autoSaveStatus === 'modified'" class="autosave-tip modified">
        <i class="el-icon-edit"></i> 未保存
      </span>
    </div>
    <div ref="editorContainer" class="config-editor"></div>
  </div>
</template>

<script>
import * as monaco from 'monaco-editor'

export default {
  name: 'ConfigEditor',
  props: {
    content: {
      type: String,
      default: '{}'
    }
  },
  data() {
    return {
      editor: null,
      autoSaveTimer: null,
      autoSaveStatus: '', // '' | 'modified' | 'saving' | 'saved'
    }
  },
  mounted() {
    this.editor = monaco.editor.create(this.$refs.editorContainer, {
      value: this.content,
      language: 'json',
      theme: 'vs',
      minimap: { enabled: false },
      fontSize: 14,
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: 2,
      formatOnPaste: true
    })
    this.editor.onDidChangeModelContent(() => {
      const val = this.editor.getValue()
      this.$emit('change', val)
      this.scheduleAutoSave()
    })
    // Ctrl+S / Cmd+S 立即保存
    this.editor.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
      () => {
        clearTimeout(this.autoSaveTimer)
        this.$emit('save')
        this.autoSaveStatus = 'saving'
        setTimeout(() => { this.autoSaveStatus = 'saved' }, 800)
      }
    )
  },
  methods: {
    scheduleAutoSave() {
      this.autoSaveStatus = 'modified'
      clearTimeout(this.autoSaveTimer)
      this.autoSaveTimer = setTimeout(() => {
        this.autoSaveStatus = 'saving'
        this.$emit('save')
        setTimeout(() => { this.autoSaveStatus = 'saved' }, 800)
      }, 3000)
    },
  },
  watch: {
    content(val) {
      if (this.editor && val !== this.editor.getValue()) {
        this.editor.setValue(val)
        this.autoSaveStatus = ''
      }
    }
  },
  beforeDestroy() {
    clearTimeout(this.autoSaveTimer)
    if (this.editor) {
      this.editor.dispose()
    }
  }
}
</script>

<style scoped>
.config-editor-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.editor-toolbar {
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 8px;
  font-size: 12px;
}
.autosave-tip { display: flex; align-items: center; gap: 4px; }
.autosave-tip.modified { color: #e6a23c; }
.autosave-tip.saving   { color: #909399; }
.autosave-tip.saved    { color: #67c23a; }

.config-editor {
  flex: 1;
  width: 100%;
  min-height: 400px;
}
</style>
