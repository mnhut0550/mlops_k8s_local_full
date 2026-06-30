import { ref } from 'vue'
import axios from 'axios'
import { BATCH_SIZE, getStem, getImgDims } from '@/utils/uploadUtils'

export function useUpload(cls, yolo, progress) {
  const result   = ref(null)
  const errorMsg = ref(null)

  function upload() {
    if (yolo.yoloMode.value) uploadYolo()
    else                     uploadClassification()
  }

  // ── Classification ───────────────────────────────────────
  async function uploadClassification() {
    progress.uploading.value    = true
    progress.doneCount.value    = 0
    progress.totalItems.value   = cls.entries.value.length
    progress.currentBatch.value = 0
    result.value   = null
    errorMsg.value = null

    const chunks = chunkArray(cls.entries.value, BATCH_SIZE)
    progress.totalBatches.value = chunks.length

    let totalUploaded = 0, totalAutoLabeled = 0
    try {
      for (const chunk of chunks) {
        progress.currentBatch.value++
        progress.uploadPhase.value = `Upload ảnh · batch ${progress.currentBatch.value}/${progress.totalBatches.value}`
        const form = new FormData()
        chunk.forEach(e => {
          form.append('files',       e.file)
          form.append('class_names', e.className || '')
        })
        const res = await axios.post(
          `/api/images/upload?task_type=${cls.taskType.value}&annotator=upload`,
          form, { headers: { 'Content-Type': 'multipart/form-data' } }
        )
        totalUploaded    += res.data.uploaded     || 0
        totalAutoLabeled += res.data.auto_labeled || 0
        progress.doneCount.value += chunk.length
      }
      result.value      = { uploaded: totalUploaded, auto_labeled: totalAutoLabeled }
      cls.entries.value = []
    } catch (e) {
      const msg = e.response?.data?.detail || e.message
      errorMsg.value             = `Upload thất bại batch ${progress.currentBatch.value}: ${msg}`
      progress.uploadError.value = msg
    } finally {
      progress.uploading.value   = false
      progress.uploadPhase.value = ''
    }
  }

  // ── YOLO Detection ───────────────────────────────────────
  async function uploadYolo() {
    progress.uploading.value    = true
    progress.doneCount.value    = 0
    progress.totalItems.value   = yolo.yoloImages.value.length
    progress.currentBatch.value = 0
    progress.uploadPhase.value  = 'Chuẩn bị classes...'
    result.value   = null
    errorMsg.value = null

    try {
      // Phase 0: upsert classes
      let classMap = {}
      if (yolo.yoloClasses.value.length > 0) {
        const r = await axios.post('/api/classes/ensure', { names: yolo.yoloClasses.value })
        classMap = r.data.classes
      }

      const chunks = chunkArray(yolo.yoloImages.value, BATCH_SIZE)
      progress.totalBatches.value = chunks.length

      let totalUploaded = 0, totalAnnotated = 0, totalWithLabel = 0

      for (const chunk of chunks) {
        progress.currentBatch.value++
        progress.uploadPhase.value = `Upload ảnh · batch ${progress.currentBatch.value}/${progress.totalBatches.value}`

        // Upload images
        const form = new FormData()
        chunk.forEach(f => form.append('files', f))
        const res = await axios.post(
          '/api/images/upload?task_type=detection&annotator=upload',
          form, { headers: { 'Content-Type': 'multipart/form-data' } }
        )
        totalUploaded += res.data.uploaded || 0

        // Build annotations
        progress.uploadPhase.value = `Gắn nhãn bbox · batch ${progress.currentBatch.value}/${progress.totalBatches.value}`
        const nameToFile   = new Map(chunk.map(f => [f.name, f]))
        const annotations  = []

        await Promise.all((res.data.images || []).map(async ({ image_id, filename }) => {
          const boxes = yolo.yoloParsed.value.get(getStem(filename))
          if (!boxes?.length) return
          const imgFile = nameToFile.get(filename)
          if (!imgFile) return
          let dims
          try { dims = await getImgDims(imgFile) } catch { return }

          totalWithLabel++
          for (const box of boxes) {
            const className = yolo.yoloClasses.value[box.class_idx]
            if (className == null) continue
            const class_id = classMap[className]
            if (!class_id) continue
            annotations.push({
              image_id, class_id, annotator: 'upload',
              bbox: {
                x: (box.cx - box.w / 2) * dims.w,
                y: (box.cy - box.h / 2) * dims.h,
                w:  box.w * dims.w,
                h:  box.h * dims.h,
                image_w: dims.w,
                image_h: dims.h,
              },
            })
            totalAnnotated++
          }
        }))

        if (annotations.length) await axios.post('/api/annotations/batch', annotations)
        progress.doneCount.value += chunk.length
      }

      result.value = { mode: 'yolo', uploaded: totalUploaded, annotated: totalAnnotated, withLabel: totalWithLabel }
      yolo.resetYolo()
    } catch (e) {
      const msg = e.response?.data?.detail || e.message
      errorMsg.value             = `Upload thất bại: ${msg}`
      progress.uploadError.value = msg
    } finally {
      progress.uploading.value   = false
      progress.uploadPhase.value = ''
    }
  }

  return { result, errorMsg, upload }
}

function chunkArray(arr, size) {
  const chunks = []
  for (let i = 0; i < arr.length; i += size) chunks.push(arr.slice(i, i + size))
  return chunks
}
