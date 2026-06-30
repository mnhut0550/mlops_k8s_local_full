<template>
  <Teleport to="body">
    <div class="toast-shell" :class="{ visible: show, error: isError }">

      <!-- Active: đang upload / init -->
      <template v-if="state === 'active'">
        <div class="toast-head">
          <span class="toast-spinner">⏳</span>
          <span class="toast-phase">{{ toastPhase }}</span>
          <span class="toast-pct">{{ toastPct }}%</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: toastPct + '%' }"></div>
        </div>
        <div class="toast-foot">
          {{ toastDone.toLocaleString() }} / {{ toastTotal.toLocaleString() }}
          <template v-if="currentBatch && totalBatches">
            &nbsp;·&nbsp; batch {{ currentBatch }}/{{ totalBatches }}
          </template>
        </div>
      </template>

      <!-- Done -->
      <template v-else-if="state === 'done'">
        <div class="toast-result">✅ Upload hoàn tất!</div>
      </template>

      <!-- Error -->
      <template v-else-if="state === 'error'">
        <div class="toast-result">❌ Lỗi: {{ uploadError }}</div>
      </template>

    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useUploadProgress } from '@/composables/useUploadProgress'

const {
  uploading, initLoading, uploadError,
  toastPhase, toastPct, toastDone, toastTotal,
  currentBatch, totalBatches,
} = useUploadProgress()

// state: 'hidden' | 'active' | 'done' | 'error'
const state   = ref('hidden')
const show    = ref(false)
const isError = ref(false)

let showTimer  = null   // đảm bảo toast hiện tối thiểu MIN_MS
let hideTimer  = null
const MIN_MS   = 1500   // tối thiểu hiển thị 1.5s dù upload nhanh đến đâu
let shownAt    = 0

watch([uploading, initLoading], ([up, init]) => {
  const active = up || init
  clearTimeout(hideTimer)

  if (active) {
    clearTimeout(showTimer)
    shownAt      = Date.now()
    state.value  = 'active'
    isError.value = false
    show.value   = true
  } else if (show.value) {
    // Đợi tối thiểu MIN_MS kể từ lúc hiện trước khi chuyển sang done/error
    const elapsed = Date.now() - shownAt
    const delay   = Math.max(0, MIN_MS - elapsed)

    showTimer = setTimeout(() => {
      state.value   = uploadError.value ? 'error' : 'done'
      isError.value = !!uploadError.value
      hideTimer = setTimeout(() => {
        show.value  = false
        state.value = 'hidden'
      }, 2500)
    }, delay)
  }
})
</script>

<style scoped>
.toast-shell {
  position: fixed; bottom: 24px; right: 24px; z-index: 9999;
  width: 300px; background: #1e293b; border: 1px solid #3b82f6;
  border-radius: 12px; padding: 14px 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,.5);
  opacity: 0; transform: translateY(12px); pointer-events: none;
  transition: opacity .22s ease, transform .22s ease;
}
.toast-shell.visible { opacity: 1; transform: translateY(0); pointer-events: auto; }
.toast-shell.error   { border-color: #ef4444; }

.toast-head    { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.toast-spinner { font-size: 14px; flex-shrink: 0; }
.toast-phase   { font-size: 13px; color: #cbd5e1; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toast-pct     { font-size: 15px; font-weight: 700; color: #60a5fa; flex-shrink: 0; }

.bar-track { height: 5px; background: #0f172a; border-radius: 3px; overflow: hidden; margin-bottom: 7px; }
.bar-fill  { height: 100%; background: linear-gradient(90deg, #2563eb, #60a5fa); border-radius: 3px; transition: width .3s ease; }

.toast-foot   { font-size: 11px; color: #64748b; }
.toast-result { font-size: 14px; font-weight: 600; color: #4ade80; }
.error .toast-result { color: #fca5a5; }
</style>
