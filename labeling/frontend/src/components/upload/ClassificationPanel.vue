<template>
  <div>
    <!-- Task type selector -->
    <div class="card task-row">
      <span class="section-label">Task type</span>
      <div class="radio-group">
        <label>
          <input type="radio" value="classification"
                 :checked="taskType === 'classification'"
                 @change="emit('update:taskType', 'classification')" />
          Classification
        </label>
        <label>
          <input type="radio" value="detection"
                 :checked="taskType === 'detection'"
                 @change="emit('update:taskType', 'detection')" />
          Detection (manual)
        </label>
      </div>
    </div>

    <!-- Class chips -->
    <div v-if="detectedClasses.length" class="card class-card">
      <span class="section-label">Classes phát hiện từ folder</span>
      <div class="class-chips">
        <span v-for="c in detectedClasses" :key="c.name" class="chip">
          {{ c.name }}
          <span class="chip-count">{{ c.count }}</span>
        </span>
      </div>
    </div>

    <!-- UPLOADING STATE — thay thế toàn bộ file list -->
    <div v-if="uploading" class="card upload-screen">
      <div class="us-icon">📤</div>
      <div class="us-title">Đang upload...</div>
      <div class="us-meta">
        {{ totalItems.toLocaleString() }} ảnh
        <span v-if="detectedClasses.length"> · {{ detectedClasses.length }} classes</span>
      </div>

      <div class="us-bar-track">
        <div class="us-bar-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div class="us-pct">{{ progressPct }}%</div>

      <div class="us-count">
        {{ doneCount.toLocaleString() }} / {{ totalItems.toLocaleString() }} ảnh
        <template v-if="currentBatch && totalBatches">
          &nbsp;·&nbsp; batch {{ currentBatch }} / {{ totalBatches }}
        </template>
      </div>

      <div class="us-phase">{{ uploadPhase }}</div>
    </div>

    <!-- File list — chỉ hiện khi chưa upload -->
    <div v-else-if="entries.length" class="card file-list-card">
      <div class="fl-header">
        <span class="fl-count">{{ entries.length }} ảnh
          <span v-if="entries.length > MAX_DISPLAY" class="fl-more">
            (hiện {{ MAX_DISPLAY }})
          </span>
        </span>
        <div class="fl-actions">
          <button class="btn btn-ghost btn-sm" @click="emit('reset')">← Chọn lại</button>
          <button class="btn btn-success btn-sm" @click="emit('upload')">
            Upload {{ entries.length }} ảnh
          </button>
        </div>
      </div>
      <div class="file-grid">
        <div v-for="(e, i) in displayEntries" :key="i" class="file-item">
          <img :src="e.url" :alt="e.file.name" />
          <div class="fi-name">{{ e.file.name }}</div>
          <div class="fi-class" :class="{ unlabeled: !e.className }">
            {{ e.className || 'UNLABELED' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { MAX_DISPLAY } from '@/utils/uploadUtils'

defineProps({
  entries:         Array,
  taskType:        String,
  detectedClasses: Array,
  displayEntries:  Array,
  uploading:       Boolean,
  doneCount:       Number,
  totalItems:      Number,
  currentBatch:    Number,
  totalBatches:    Number,
  progressPct:     Number,
  uploadPhase:     String,
})
const emit = defineEmits(['update:taskType', 'upload', 'reset'])
</script>

<style scoped>
.section-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; display: block; margin-bottom: 8px; }

.task-row    { display: flex; align-items: center; gap: 24px; }
.radio-group { display: flex; gap: 20px; font-size: 14px; }
.radio-group label { display: flex; align-items: center; gap: 6px; cursor: pointer; }

.class-card  { }
.class-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip        { background: #1e3a5f; border: 1px solid #3b82f6; border-radius: 16px; padding: 3px 12px; font-size: 13px; display: flex; align-items: center; gap: 6px; }
.chip-count  { background: #2563eb; border-radius: 10px; padding: 0 6px; font-size: 11px; }

/* ── Upload screen ───────────────────────────────── */
.upload-screen {
  display: flex; flex-direction: column; align-items: center;
  padding: 48px 32px; gap: 12px; text-align: center;
}
.us-icon  { font-size: 48px; line-height: 1; }
.us-title { font-size: 22px; font-weight: 700; color: #f1f5f9; }
.us-meta  { font-size: 14px; color: #94a3b8; margin-bottom: 4px; }

.us-bar-track {
  width: 100%; max-width: 480px; height: 10px;
  background: #0f172a; border-radius: 5px; overflow: hidden;
}
.us-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #60a5fa);
  border-radius: 5px;
  transition: width .4s ease;
}
.us-pct   { font-size: 32px; font-weight: 800; color: #60a5fa; line-height: 1; }
.us-count { font-size: 14px; color: #64748b; }
.us-phase { font-size: 12px; color: #475569; min-height: 18px; }

/* ── File list ───────────────────────────────────── */
.fl-header   { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.fl-actions  { display: flex; gap: 8px; align-items: center; }
.fl-count    { font-size: 14px; font-weight: 600; }
.fl-more     { color: #64748b; font-weight: 400; font-size: 13px; }
.btn-sm      { padding: 4px 10px; font-size: 12px; }

.file-grid   { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; max-height: 400px; overflow-y: auto; }
.file-item   { background: #0f172a; border-radius: 6px; overflow: hidden; font-size: 11px; }
.file-item img { width: 100%; aspect-ratio: 1; object-fit: cover; display: block; }
.fi-name     { padding: 4px 6px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fi-class    { padding: 2px 6px 4px; color: #3b82f6; }
.fi-class.unlabeled { color: #64748b; }
</style>
