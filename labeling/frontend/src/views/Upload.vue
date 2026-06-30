<template>
  <div class="page">
    <h2 class="page-title">Upload ảnh</h2>

    <template v-if="!hasFiles">
      <!-- Đang đọc file -->
      <div v-if="initLoading" class="loading-card">
        <div class="loading-spinner"></div>
        <div class="loading-text">{{ initMsg || 'Đang đọc file...' }}</div>
        <div v-if="initTotal > 0" class="loading-sub">
          {{ initDone.toLocaleString() }} / {{ initTotal.toLocaleString() }}
        </div>
      </div>
      <!-- Chưa chọn gì -->
      <template v-else>
        <UploadDropZone @add-files="addFiles" />
        <FormatGuide />
      </template>
    </template>

    <YoloBanner
      v-if="yoloMode"
      :yolo-stats="yoloStats"
      :yolo-classes="yoloClasses"
      :yolo-parsed="yoloParsed"
      :uploading="uploading"
      :done-count="doneCount"
      :total-items="totalItems"
      :current-batch="currentBatch"
      :total-batches="totalBatches"
      :progress-pct="progressPct"
      :upload-phase="uploadPhase"
      @upload="requestUpload"
      @reset="reset"
    />

    <ClassificationPanel
      v-else
      :entries="entries"
      :task-type="taskType"
      :detected-classes="detectedClasses"
      :display-entries="displayEntries"
      :uploading="uploading"
      :done-count="doneCount"
      :total-items="totalItems"
      :current-batch="currentBatch"
      :total-batches="totalBatches"
      :progress-pct="progressPct"
      :upload-phase="uploadPhase"
      @update:task-type="v => (taskType.value = v)"
      @upload="requestUpload"
      @reset="reset"
    />

    <UploadResult :result="result" :error-msg="errorMsg" />

    <!-- Toast nằm ở App.vue → persist khi chuyển tab -->

    <!-- Confirm dialog -->
    <ConfirmDialog
      :visible="showConfirm"
      :title="confirmTitle"
      icon="📤"
      confirm-label="Upload ngay"
      @confirm="doUpload"
      @cancel="showConfirm = false"
    >
      <div v-if="confirmIsYolo">
        <strong style="color:#a78bfa">YOLO Detection</strong><br />
        {{ yoloStats?.total }} ảnh &nbsp;·&nbsp;
        {{ yoloStats?.withLabel }} nhãn &nbsp;·&nbsp;
        {{ yoloClasses.length }} classes
      </div>
      <div v-else>
        <strong style="color:#60a5fa">{{ taskType === 'classification' ? 'Classification' : 'Detection (manual)' }}</strong><br />
        {{ entries.length }} ảnh
        <template v-if="detectedClasses.length">
          &nbsp;·&nbsp; {{ detectedClasses.length }} classes
        </template>
      </div>
    </ConfirmDialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useYoloInit }       from '@/composables/useYoloInit'
import { useUploadProgress } from '@/composables/useUploadProgress'
import { useUpload }         from '@/composables/useUpload'
import { useFileSelect }     from '@/composables/useFileSelect'

import UploadDropZone      from '@/components/upload/UploadDropZone.vue'
import FormatGuide         from '@/components/upload/FormatGuide.vue'
import YoloBanner          from '@/components/upload/YoloBanner.vue'
import ClassificationPanel from '@/components/upload/ClassificationPanel.vue'
import UploadResult        from '@/components/upload/UploadResult.vue'
import ConfirmDialog       from '@/components/upload/ConfirmDialog.vue'

// ── Composables ──────────────────────────────────────────────
const yolo     = useYoloInit()
const progress = useUploadProgress()
const cls      = useFileSelect(yolo)
const { result, errorMsg, upload } = useUpload(cls, yolo, progress)

// ── Flatten for template ─────────────────────────────────────
const {
  yoloMode, yoloClasses, yoloParsed, yoloStats,
} = yolo

const {
  uploading, doneCount, totalItems,
  currentBatch, totalBatches, progressPct, uploadPhase,
  initLoading, initMsg, initDone, initTotal,
} = progress

const {
  entries, taskType, lastFromFolder, detectedClasses, displayEntries,
  addFiles, resetCls,
} = cls

// ── Có file chưa ─────────────────────────────────────────────
const hasFiles = computed(() => yoloMode.value ? (yoloStats.value?.total > 0) : entries.value.length > 0)

// ── Confirm dialog ───────────────────────────────────────────
// Folder upload: browser đã hỏi "Upload X files?" → skip confirm của mình
// File lẻ / drag-drop: hiện ConfirmDialog
const showConfirm   = ref(false)
const confirmIsYolo = ref(false)

const confirmTitle = computed(() =>
  confirmIsYolo.value
    ? `Upload ${yoloStats.value?.total ?? 0} ảnh YOLO?`
    : `Upload ${entries.value.length} ảnh?`
)

function requestUpload() {
  if (lastFromFolder.value) {
    upload()          // browser đã confirm rồi
  } else {
    confirmIsYolo.value = yoloMode.value
    showConfirm.value   = true
  }
}

function doUpload() {
  showConfirm.value = false
  upload()
}

// ── Global reset ─────────────────────────────────────────────
function reset() {
  resetCls()
  yolo.resetYolo()
  progress.resetProgress()
  result.value   = null
  errorMsg.value = null
}
</script>

<style scoped>
.page       { max-width: 1280px; margin: 0 auto; padding: 32px 24px; }
.page-title { font-size: 24px; font-weight: 700; margin-bottom: 24px; }

.loading-card {
  display: flex; flex-direction: column; align-items: center;
  gap: 14px; padding: 64px 32px;
  background: #1e293b; border: 1px solid #334155;
  border-radius: 12px; text-align: center;
}
.loading-spinner {
  width: 40px; height: 40px;
  border: 3px solid #334155; border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font-size: 16px; color: #cbd5e1; }
.loading-sub  { font-size: 13px; color: #64748b; }
</style>
