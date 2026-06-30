import { ref, shallowRef, computed } from 'vue'

const yieldFrame = () => new Promise(r => setTimeout(r, 0))
import { isImage, extractClass, MAX_DISPLAY } from '@/utils/uploadUtils'
import { useUploadProgress } from './useUploadProgress'

const LOAD_CHUNK = 2000

export function useFileSelect(yolo) {
  const entries        = shallowRef([])
  const taskType       = ref('classification')
  const lastFromFolder = ref(false)

  const { initLoading, initMsg, initDone, initTotal } = useUploadProgress()

  const displayEntries = computed(() => entries.value.slice(0, MAX_DISPLAY))

  const detectedClasses = computed(() => {
    const counts = {}
    for (const e of entries.value) {
      if (e.className) counts[e.className] = (counts[e.className] || 0) + 1
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
  })

  async function addFiles(rawFiles, fromFolder) {
    const files = Array.from(rawFiles)
    lastFromFolder.value = fromFolder

    if (fromFolder && files.length > 0) {
      const classesFile = yolo.detectYolo(files)
      if (classesFile) {
        await yolo.initYolo(files, classesFile)
        return
      }
    }

    yolo.yoloMode.value = false
    const imgs = files.filter(f => isImage(f))
    if (imgs.length === 0) return

    initLoading.value = true
    initMsg.value     = 'Đang tải ' + imgs.length.toLocaleString() + ' ảnh...'
    initTotal.value   = imgs.length
    initDone.value    = 0

    const next = []
    for (let i = 0; i < imgs.length; i += LOAD_CHUNK) {
      const slice = imgs.slice(i, i + LOAD_CHUNK)
      for (const f of slice) {
        next.push({
          file: f,
          className: extractClass(f, fromFolder),
          url: URL.createObjectURL(f),
        })
      }
      initDone.value = Math.min(i + LOAD_CHUNK, imgs.length)
      await yieldFrame()
    }

    entries.value     = [...entries.value, ...next]
    initLoading.value = false
  }

  function onDrop(rawFiles) {
    addFiles(rawFiles, false)
  }

  function resetCls() {
    entries.value  = []
    taskType.value = 'classification'
  }

  return {
    entries, taskType, lastFromFolder,
    displayEntries, detectedClasses,
    addFiles, onDrop, resetCls,
  }
}
