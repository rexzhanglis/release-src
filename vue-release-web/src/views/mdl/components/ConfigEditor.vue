<template>
  <div ref="editorContainer" class="config-editor"></div>
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
      editor: null
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
      this.$emit('change', this.editor.getValue())
    })
  },
  watch: {
    content(val) {
      if (this.editor && val !== this.editor.getValue()) {
        this.editor.setValue(val)
      }
    }
  },
  beforeDestroy() {
    if (this.editor) {
      this.editor.dispose()
    }
  }
}
</script>

<style scoped>
.config-editor {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>
