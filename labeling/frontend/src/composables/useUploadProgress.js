import { ref, computed } from 'vue'

// Module-level singleton — shared across all imports
const uploading    = ref(false)
const doneCount    = ref(0)
const totalItems   = ref(0)
const currentBatch = ref(0)
const totalBatches = ref(0)
const uploadPhase  = ref('')
const initLoading  = ref(false)
const initMsg      = ref('')
const initDone     = ref(0)
const initTotal    = ref(0)
const uploadError  = ref('')     // set khi upload thất bại

// Computeds also at module level — no per-call re-creation
const progressPct  = computed(() => totalItems.value  ? Math.round((doneCount.value / totalItems.value)  * 100) : 0)
const initPct      = computed(() => initTotal.value   ? Math.round((initDone.value  / initTotal.value)   * 100) : 0)
const toastVisible = computed(() => initLoading.value || uploading.value)
const toastPhase   = computed(() => initLoading.value ? (initMsg.value || 'Đang xử lý...') : (uploadPhase.value || 'Đang upload...'))
const toastPct     = computed(() => initLoading.value ? initPct.value : progressPct.value)
const toastDone    = computed(() => initLoading.value ? initDone.value  : doneCount.value)
const toastTotal   = computed(() => initLoading.value ? initTotal.value : totalItems.value)

export function useUploadProgress() {
  function resetProgress() {
    uploading.value    = false
    doneCount.value    = 0
    totalItems.value   = 0
    currentBatch.value = 0
    totalBatches.value = 0
    uploadPhase.value  = ''
    uploadError.value  = ''
  }

  return {
    uploading, doneCount, totalItems, currentBatch, totalBatches, uploadPhase,
    initLoading, initMsg, initDone, initTotal, uploadError,
    progressPct, initPct,
    toastVisible, toastPhase, toastPct, toastDone, toastTotal,
    resetProgress,
  }
}
