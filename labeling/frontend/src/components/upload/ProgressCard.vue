<template>
  <Teleport to="body">
    <div class="toast-wrap" :class="{ show: visible || showDone }">

      <!-- Progress -->
      <div v-if="!showDone" class="toast">
        <div class="toast-top">
          <span class="toast-label">{{ phase }}</span>
          <span class="toast-pct">{{ pct }}%</span>
        </div>
        <div class="track">
          <div class="fill" :style="{ width: pct + '%' }"></div>
        </div>
        <div class="toast-detail">
          <template v-if="initLoading">
            Đọc label: {{ initDone }} / {{ initTotal }}
          </template>
          <template v-else>
            {{ doneCount }} / {{ totalItems }} ảnh &nbsp;·&nbsp;
            batch {{ currentBatch }} / {{ totalBatches }}
          </template>
        </div>
      </div>

      <!-- Done -->
      <div v-else class="toast toast-done">
        <span class="done-icon">✅</span>
        <span class="done-text">Hoàn tất!</span>
      </div>

    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const p = defineProps({
  visible:      Boolean,
  initLoading:  Boolean,
  initMsg:      String,
  initPct:      { type: Number, default: 0 },
  initDone:     { type: Number, default: 0 },
  initTotal:    { type: Number, default: 0 },
  uploadPhase:  String,
  progressPct:  { type: Number, default: 0 },
  doneCount:    { type: Number, default: 0 },
  totalItems:   { type: Number, default: 0 },
  currentBatch: { type: Number, default: 0 },
  totalBatches: { type: Number, default: 0 },
})

const phase = computed(() => p.initLoading ? (p.initMsg || 'Đang xử lý...') : (p.uploadPhase || 'Đang upload...'))
const pct   = computed(() => p.initLoading ? p.initPct : p.progressPct)

// Hiện "Done" 1.5s sau khi visible chuyển false
const showDone = ref(false)
let doneTimer = null

watch(() => p.visible, (val) => {
  if (!val && p.pct !== 0) {
    showDone.value = true
    clearTimeout(doneTimer)
    doneTimer = setTimeout(() => { showDone.value = false }, 1500)
  }
})
</script>

<style scoped>
.toast-wrap {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%) translateY(20px);
  z-index: 9999;
  min-width: 340px;
  max-width: 420px;
  opacity: 0;
  pointer-events: none;
  transition: opacity .25s ease, transform .25s ease;
}
.toast-wrap.show {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
  pointer-events: auto;
}

.toast {
  background: #0f1f35;
  border: 1.5px solid #3b82f6;
  border-radius: 14px;
  padding: 16px 20px;
  box-shadow: 0 8px 40px rgba(0,0,0,.55);
}
.toast-done {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  border-color: #22c55e; background: #052e16;
}

.toast-top   { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.toast-label { font-size: 13px; color: #cbd5e1; flex: 1; }
.toast-pct   { font-size: 24px; font-weight: 800; color: #60a5fa; margin-left: 12px; }

.track { height: 8px; background: #1e293b; border-radius: 4px; overflow: hidden; margin-bottom: 8px; }
.fill  { height: 100%; background: linear-gradient(90deg, #2563eb, #60a5fa); border-radius: 4px; transition: width .3s ease; }

.toast-detail { font-size: 12px; color: #64748b; }

.done-icon { font-size: 22px; }
.done-text { font-size: 16px; font-weight: 700; color: #4ade80; }
</style>
