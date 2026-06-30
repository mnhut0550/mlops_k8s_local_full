<template>
  <div>
    <!-- UPLOADING STATE -->
    <div v-if="uploading" class="card upload-screen">
      <div class="us-icon">🎯</div>
      <div class="us-title">Đang upload + annotate...</div>
      <div class="us-meta">
        {{ totalItems.toLocaleString() }} ảnh
        <span v-if="yoloClasses.length"> · {{ yoloClasses.length }} classes</span>
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

    <!-- Normal state -->
    <template v-else>
      <div class="card yolo-banner">
        <div class="yolo-title">🎯 YOLO Detection format</div>
        <div class="yolo-stats">
          <span>🖼 {{ yoloStats.total }} ảnh</span>
          <span>🏷 {{ yoloParsed.size }} nhãn</span>
          <span v-if="yoloStats.withoutLabel > 0" class="warn">
            ⚠️ {{ yoloStats.withoutLabel }} ảnh không có label → UNLABELED
          </span>
        </div>
        <div style="margin-top:8px">
          <span class="section-label">Classes (classes.txt)</span>
          <div class="class-chips">
            <span v-for="(c, i) in yoloClasses" :key="i" class="chip">
              <span class="chip-idx">{{ i }}</span> {{ c }}
            </span>
          </div>
        </div>
      </div>

      <div class="card action-row">
        <span class="count-label">{{ yoloStats.total }} ảnh sẵn sàng</span>
        <div class="btn-group">
          <button class="btn btn-ghost" @click="emit('reset')">← Chọn lại</button>
          <button class="btn btn-success" @click="emit('upload')">Upload + Annotate</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  yoloStats:    Object,
  yoloClasses:  Array,
  yoloParsed:   Map,
  uploading:    Boolean,
  doneCount:    Number,
  totalItems:   Number,
  currentBatch: Number,
  totalBatches: Number,
  progressPct:  Number,
  uploadPhase:  String,
})
const emit = defineEmits(['upload', 'reset'])
</script>

<style scoped>
/* Upload screen */
.upload-screen {
  display: flex; flex-direction: column; align-items: center;
  padding: 48px 32px; gap: 12px; text-align: center;
}
.us-icon  { font-size: 48px; line-height: 1; }
.us-title { font-size: 22px; font-weight: 700; color: #a78bfa; }
.us-meta  { font-size: 14px; color: #94a3b8; margin-bottom: 4px; }
.us-bar-track {
  width: 100%; max-width: 480px; height: 10px;
  background: #0f172a; border-radius: 5px; overflow: hidden;
}
.us-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
  border-radius: 5px; transition: width .4s ease;
}
.us-pct   { font-size: 32px; font-weight: 800; color: #a78bfa; line-height: 1; }
.us-count { font-size: 14px; color: #64748b; }
.us-phase { font-size: 12px; color: #475569; min-height: 18px; }

.yolo-banner { border: 1px solid #7c3aed; background: #1e1040; }
.yolo-title  { font-size: 16px; font-weight: 700; color: #a78bfa; margin-bottom: 10px; }
.yolo-stats  { display: flex; flex-wrap: wrap; gap: 16px; font-size: 14px; margin-bottom: 8px; }
.warn        { color: #fbbf24; }
.section-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; display: block; margin-bottom: 6px; }
.class-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.chip        { background: #1e3a5f; border: 1px solid #3b82f6; border-radius: 16px; padding: 3px 10px; font-size: 13px; }
.chip-idx    { background: #312e81; border-radius: 4px; padding: 0 4px; font-size: 11px; color: #c4b5fd; margin-right: 4px; }

.action-row  { display: flex; justify-content: space-between; align-items: center; }
.count-label { font-size: 14px; color: #94a3b8; }
.btn-group   { display: flex; gap: 8px; }
</style>
