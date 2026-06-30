import { ref, nextTick } from 'vue'
import { isImage, getStem, LABEL_READ_CHUNK } from '@/utils/uploadUtils'
import { useUploadProgress } from './useUploadProgress'

export function useYoloInit() {
  // Dùng singleton progress → toast thấy được
  const { initLoading, initMsg, initDone, initTotal } = useUploadProgress()

  // YOLO data (vẫn local — chỉ cần trong Upload view)
  const yoloMode    = ref(false)
  const yoloImages  = ref([])
  const yoloClasses = ref([])
  const yoloParsed  = ref(new Map())
  const yoloStats   = ref(null)

  // ── Detect YOLO structure ────────────────────────────────
  function detectYolo(files) {
    const seg = (f) => f.webkitRelativePath.split('/')
    const hasImages   = files.some(f => { const p = seg(f); return p.length >= 3 && p[1] === 'images' && isImage(f) })
    const hasLabels   = files.some(f => { const p = seg(f); return p.length >= 3 && p[1] === 'labels' && f.name.endsWith('.txt') })
    const classesFile = files.find(f => { const p = seg(f); return p.length === 2 && f.name === 'classes.txt' })
    return (hasImages && hasLabels && classesFile) ? classesFile : null
  }

  // ── Main init ────────────────────────────────────────────
  async function initYolo(files, classesFile) {
    yoloMode.value    = true
    initLoading.value = true
    initDone.value    = 0
    initTotal.value   = 0
    initMsg.value     = 'Đọc classes.txt...'

    const classText   = await classesFile.text()
    yoloClasses.value = classText.trim().split('\n').map(l => l.trim()).filter(Boolean)

    const seg      = (f) => f.webkitRelativePath.split('/')
    const imgFiles = files.filter(f => { const p = seg(f); return p.length >= 3 && p[1] === 'images' && isImage(f) })
    const lblFiles = files.filter(f => { const p = seg(f); return p.length >= 3 && p[1] === 'labels' && f.name.endsWith('.txt') })

    initTotal.value = lblFiles.length
    initMsg.value   = `Đọc ${lblFiles.length.toLocaleString()} label files...`

    const parsed = new Map()
    for (let i = 0; i < lblFiles.length; i += LABEL_READ_CHUNK) {
      await Promise.all(lblFiles.slice(i, i + LABEL_READ_CHUNK).map(async lf => {
        try {
          const stem = getStem(lf.name)
          const text = await lf.text()
          const boxes = text.trim().split('\n').filter(Boolean).map(line => {
            const pts = line.trim().split(/\s+/).map(Number)
            if (pts.length < 5 || pts.some(isNaN)) return null
            const [ci, cx, cy, w, h] = pts
            return { class_idx: ci, cx, cy, w, h }
          }).filter(Boolean)
          if (boxes.length) parsed.set(stem, boxes)
        } catch { /* skip */ }
      }))
      initDone.value = Math.min(i + LABEL_READ_CHUNK, lblFiles.length)
      await nextTick()
    }

    yoloImages.value = imgFiles
    yoloParsed.value = parsed

    const withLabel = imgFiles.filter(f => parsed.has(getStem(f.name))).length
    yoloStats.value = { total: imgFiles.length, withLabel, withoutLabel: imgFiles.length - withLabel }

    initLoading.value = false
    initMsg.value     = ''
  }

  function resetYolo() {
    yoloMode.value    = false
    yoloImages.value  = []
    yoloClasses.value = []
    yoloParsed.value  = new Map()
    yoloStats.value   = null
    initLoading.value = false
    initDone.value    = 0
    initTotal.value   = 0
  }

  return {
    yoloMode, yoloImages, yoloClasses, yoloParsed, yoloStats,
    detectYolo, initYolo, resetYolo,
  }
}
