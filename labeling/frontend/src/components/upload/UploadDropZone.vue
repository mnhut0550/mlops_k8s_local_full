<template>
  <div class="card upload-area"
       :class="{ dragging }"
       @dragover.prevent="dragging = true"
       @dragleave="dragging = false"
       @drop.prevent="onDrop">
    <div class="upload-icon">📁</div>
    <p>Kéo thả ảnh vào đây, hoặc</p>
    <div class="btn-row">
      <label class="btn btn-primary">
        Chọn file
        <input type="file" multiple accept="image/*" hidden
               @change="e => emit('add-files', e.target.files, false)" />
      </label>
      <label class="btn btn-ghost">
        Chọn folder
        <input ref="folderInput" type="file" multiple hidden
               @change="e => emit('add-files', e.target.files, true)" />
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const emit = defineEmits(['add-files'])

const dragging    = ref(false)
const folderInput = ref(null)

onMounted(() => {
  // webkitdirectory không phải standard — set trực tiếp lên DOM
  folderInput.value?.setAttribute('webkitdirectory', '')
})

function onDrop(e) {
  dragging.value = false
  emit('add-files', e.dataTransfer.files, false)
}
</script>

<style scoped>
.upload-area {
  display: flex; flex-direction: column; align-items: center;
  padding: 48px; border: 2px dashed #475569; transition: border-color .2s; cursor: default;
}
.upload-area.dragging { border-color: #3b82f6; background: #1e3a5f; }
.upload-icon { font-size: 48px; margin-bottom: 12px; }
.btn-row { display: flex; gap: 12px; margin-top: 12px; }
label.btn { cursor: pointer; }
</style>
