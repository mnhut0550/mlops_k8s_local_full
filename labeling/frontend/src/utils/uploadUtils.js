// ── Constants ────────────────────────────────────────────────
export const BATCH_SIZE       = 20
export const MAX_DISPLAY      = 200
export const LABEL_READ_CHUNK = 50

// ── File type helpers ────────────────────────────────────────
export function isImage(f) {
  return f.type.startsWith('image/') ||
    /\.(jpe?g|png|webp|gif|bmp|tiff?|avif|heic)$/i.test(f.name)
}

export function formatSize(bytes) {
  if (bytes < 1024)    return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

// "root/cat/img1.jpg" → "cat" (parts[1] = subfolder = class)
export function extractClass(file, fromFolder) {
  if (!fromFolder) return ''
  const parts = (file.webkitRelativePath || '').split('/')
  return parts.length >= 3 ? parts[1] : ''
}

// "img1.jpg" → "img1"
export function getStem(filename) {
  return filename.replace(/\.[^.]+$/, '')
}

// Load image to get natural dimensions
export function getImgDims(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload  = () => { URL.revokeObjectURL(url); resolve({ w: img.naturalWidth, h: img.naturalHeight }) }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Cannot load image')) }
    img.src = url
  })
}
