<template>
  <div class="label-layout">

    <!-- LEFT: Canvas -->
    <div class="canvas-panel card">
      <div v-if="!image" class="no-image">
        <p>{{ loading ? 'Đang tải...' : 'Không còn ảnh cần label 🎉' }}</p>
        <button v-if="!loading" class="btn btn-ghost" @click="fetchNext">Thử lại</button>
      </div>

      <div v-else>
        <div class="canvas-header">
          <span class="filename">{{ image.filename }}</span>
          <span :class="['tag', `tag-${image.status.toLowerCase()}`]">{{ image.status }}</span>
          <!-- Auto-save status -->
          <span :class="['save-status', saveStatusClass]">{{ saveStatusText }}</span>
        </div>

        <div class="canvas-wrap" ref="canvasWrap">
          <img
            ref="imgEl"
            :src="image.url"
            @load="onImageLoad"
            class="canvas-img"
            draggable="false"
          />
          <canvas
            ref="canvas"
            class="canvas-overlay"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
            @mouseleave="onMouseLeave"
          />
        </div>

        <div class="canvas-hint" v-if="image.task_type === 'detection'">
          Kéo để vẽ bbox • Click vào bbox để xóa
        </div>
        <div class="canvas-hint" v-else>
          Chọn class bên phải rồi bấm Submit
        </div>
      </div>
    </div>

    <!-- RIGHT: Controls -->
    <div class="controls-panel">

      <!-- Task type switcher -->
      <div class="card control-section">
        <label class="section-label">Task type</label>
        <div class="radio-group">
          <label class="radio-label">
            <input type="radio" v-model="taskType" value="detection" @change="onTaskTypeChange" /> Detection
          </label>
          <label class="radio-label">
            <input type="radio" v-model="taskType" value="classification" @change="onTaskTypeChange" /> Classification
          </label>
        </div>
      </div>

      <!-- Classes -->
      <div class="card control-section">
        <label class="section-label">Classes</label>
        <div class="class-list">
          <div
            v-for="c in classes" :key="c.class_id"
            :class="['class-item', { active: selectedClassId === c.class_id }]"
          >
            <template v-if="editingClassId !== c.class_id">
              <span class="class-name" @click="onSelectClass(c.class_id)">{{ c.name }}</span>
              <button class="btn-icon" @click.stop="startEdit(c)" title="Đổi tên">✏️</button>
            </template>
            <template v-else>
              <input
                v-model="editingName"
                class="class-edit-input"
                @keyup.enter="saveEdit(c)"
                @keyup.escape="cancelEdit"
                @blur="saveEdit(c)"
                ref="editInput"
              />
            </template>
          </div>
        </div>

        <div class="add-class">
          <input v-model="newClass" placeholder="Thêm class mới..." @keyup.enter="addClass" />
          <button class="btn btn-ghost" @click="addClass">+</button>
        </div>
      </div>

      <!-- Boxes list (detection) -->
      <div v-if="image?.task_type === 'detection'" class="card control-section">
        <label class="section-label">Boxes ({{ boxes.length }})</label>
        <div class="box-list">
          <div v-for="(b, i) in boxes" :key="i" class="box-item">
            <span class="box-label">{{ b.class_name }}</span>
            <span class="box-coords">
              {{ Math.round(b.x) }},{{ Math.round(b.y) }}
              {{ Math.round(b.w) }}×{{ Math.round(b.h) }}
            </span>
            <button class="btn-icon" @click="onRemoveBox(i)">✕</button>
          </div>
          <div v-if="!boxes.length" class="empty-hint">Chưa có bbox nào</div>
        </div>
      </div>

      <!-- Submit -->
      <div class="card control-section">
        <button
          class="btn btn-success submit-btn"
          :disabled="!canSubmit || submitting"
          @click="submit"
        >
          {{ submitting ? 'Đang lưu...' : 'Submit ✓' }}
        </button>
        <button class="btn btn-ghost submit-btn" style="margin-top:8px" @click="skip">
          Bỏ qua →
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'

const props = defineProps(['annotator'])

const AUTO_SAVE_DELAY = 3000   // ms không thao tác thì tự save

// ── State ─────────────────────────────────────────────────────
const image           = ref(null)
const loading         = ref(false)
const submitting      = ref(false)
const taskType        = ref('detection')
const classes         = ref([])
const selectedClassId = ref(null)
const newClass        = ref('')
const boxes           = ref([])     // [{class_id, class_name, x, y, w, h}] image coords

// Inline edit
const editingClassId = ref(null)
const editingName    = ref('')
const editInput      = ref(null)

// Auto-save state
const isDirty    = ref(false)
const saveState  = ref('clean')   // 'clean' | 'dirty' | 'saving' | 'saved'
const savedAt    = ref(null)
let autoSaveTimer = null

// Canvas refs
const canvas     = ref(null)
const imgEl      = ref(null)
const canvasWrap = ref(null)

let drawing    = false
let startX     = 0
let startY     = 0
let currentBox = null
let scaleX     = 1
let scaleY     = 1

// ── Computed ──────────────────────────────────────────────────
const selectedClass = computed(() =>
  classes.value.find(c => c.class_id === selectedClassId.value) || null
)

const canSubmit = computed(() => {
  if (!image.value) return false
  if (image.value.task_type === 'detection') return boxes.value.length > 0 && selectedClassId.value !== null
  return selectedClassId.value !== null
})

const saveStatusText = computed(() => {
  if (saveState.value === 'dirty')  return '● Chưa lưu'
  if (saveState.value === 'saving') return '⟳ Đang lưu...'
  if (saveState.value === 'saved' && savedAt.value) {
    return `✓ ${savedAt.value.toLocaleTimeString('vi-VN')}`
  }
  return ''
})

const saveStatusClass = computed(() => ({
  'status-dirty':  saveState.value === 'dirty',
  'status-saving': saveState.value === 'saving',
  'status-saved':  saveState.value === 'saved',
}))

// ── Lifecycle ─────────────────────────────────────────────────
onMounted(() => {
  loadClasses()
  fetchNext()
})

onUnmounted(() => {
  clearTimeout(autoSaveTimer)
})

// ── Auto-save ─────────────────────────────────────────────────
function markDirty() {
  if (!canSubmit.value) return
  isDirty.value   = true
  saveState.value = 'dirty'
  clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(autoSave, AUTO_SAVE_DELAY)
}

function clearAutoSave() {
  clearTimeout(autoSaveTimer)
  autoSaveTimer = null
  isDirty.value  = false
  saveState.value = 'clean'
}

async function autoSave() {
  if (!canSubmit.value || !isDirty.value) return
  await doSubmit(/* navigateNext= */ false)
}

// ── Core submit (không fetchNext) ─────────────────────────────
async function doSubmit(navigateNext = true) {
  if (!image.value || submitting.value) return
  submitting.value = true
  saveState.value  = 'saving'
  try {
    const image_w = imgEl.value?.naturalWidth  || 0
    const image_h = imgEl.value?.naturalHeight || 0

    if (image.value.task_type === 'detection') {
      await axios.post('/api/annotations/batch', boxes.value.map(b => ({
        image_id:  image.value.image_id,
        class_id:  b.class_id,
        bbox:      { x: b.x, y: b.y, w: b.w, h: b.h, image_w, image_h },
        annotator: props.annotator || 'anonymous',
      })))
    } else {
      await axios.post('/api/annotations', {
        image_id:  image.value.image_id,
        class_id:  selectedClassId.value,
        annotator: props.annotator || 'anonymous',
      })
    }

    isDirty.value   = false
    saveState.value = 'saved'
    savedAt.value   = new Date()

    if (navigateNext) await fetchNext()
  } catch (e) {
    saveState.value = 'dirty'   // retry nếu lỗi
    scheduleAutoSave()
  } finally {
    submitting.value = false
  }
}

function scheduleAutoSave() {
  clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(autoSave, AUTO_SAVE_DELAY)
}

// ── Classes ───────────────────────────────────────────────────
async function loadClasses() {
  const res = await axios.get('/api/classes')
  classes.value = res.data.classes
  if (classes.value.length && selectedClassId.value === null) {
    selectedClassId.value = classes.value[0].class_id
  }
}

async function addClass() {
  const name = newClass.value.trim()
  if (!name) return
  const res = await axios.post('/api/classes', { name })
  newClass.value = ''
  await loadClasses()
  selectedClassId.value = res.data.class_id
}

function onSelectClass(classId) {
  selectedClassId.value = classId
  // classification: chọn class là đã đủ để save
  if (image.value?.task_type === 'classification') markDirty()
}

function startEdit(c) {
  editingClassId.value = c.class_id
  editingName.value    = c.name
  nextTick(() => { if (editInput.value?.[0]) editInput.value[0].focus() })
}

async function saveEdit(c) {
  if (editingClassId.value === null) return
  const name = editingName.value.trim()
  if (!name || name === c.name) { cancelEdit(); return }
  try {
    await axios.put(`/api/classes/${c.class_id}`, { name })
    await loadClasses()
  } catch (e) {
    alert(e.response?.data?.detail || 'Lỗi đổi tên')
  }
  cancelEdit()
}

function cancelEdit() {
  editingClassId.value = null
  editingName.value    = ''
}

// ── Images ────────────────────────────────────────────────────
async function fetchNext() {
  clearAutoSave()
  loading.value = true
  image.value   = null
  boxes.value   = []
  try {
    const res = await axios.get(`/api/images/next?task_type=${taskType.value}`)
    image.value = res.data.image
    if (image.value) await nextTick(() => redraw())
  } finally {
    loading.value = false
  }
}

async function onTaskTypeChange() {
  // Lưu ảnh hiện tại trước khi chuyển task type
  if (isDirty.value && canSubmit.value) await doSubmit(false)
  await fetchNext()
}

// ── Canvas ────────────────────────────────────────────────────
function onImageLoad() {
  const img = imgEl.value
  const cvs = canvas.value
  cvs.width  = img.clientWidth
  cvs.height = img.clientHeight
  scaleX = img.naturalWidth  / img.clientWidth
  scaleY = img.naturalHeight / img.clientHeight
  redraw()
}

function canvasPos(e) {
  const rect = canvas.value.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function onMouseDown(e) {
  if (image.value?.task_type !== 'detection') return
  const pos = canvasPos(e)
  drawing = true; startX = pos.x; startY = pos.y; currentBox = null
}

function onMouseMove(e) {
  if (!drawing) return
  const pos  = canvasPos(e)
  currentBox = {
    x: Math.min(startX, pos.x), y: Math.min(startY, pos.y),
    w: Math.abs(pos.x - startX), h: Math.abs(pos.y - startY),
  }
  redraw()
}

function onMouseUp() {
  if (!drawing) return
  drawing = false
  if (currentBox && currentBox.w > 5 && currentBox.h > 5 && selectedClass.value) {
    boxes.value.push({
      class_id:   selectedClass.value.class_id,
      class_name: selectedClass.value.name,
      x: currentBox.x * scaleX, y: currentBox.y * scaleY,
      w: currentBox.w * scaleX, h: currentBox.h * scaleY,
    })
    markDirty()
  }
  currentBox = null
  redraw()
}

function onMouseLeave() {
  if (drawing) { drawing = false; currentBox = null; redraw() }
}

function onRemoveBox(i) {
  boxes.value.splice(i, 1)
  redraw()
  if (boxes.value.length > 0) markDirty()
  else clearAutoSave()
}

const COLORS = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#a855f7','#06b6d4']

function redraw() {
  const cvs = canvas.value
  if (!cvs) return
  const ctx = cvs.getContext('2d')
  ctx.clearRect(0, 0, cvs.width, cvs.height)
  boxes.value.forEach((b, i) => {
    const color = COLORS[i % COLORS.length]
    const bx = b.x / scaleX, by = b.y / scaleY, bw = b.w / scaleX, bh = b.h / scaleY
    ctx.strokeStyle = color; ctx.lineWidth = 2
    ctx.strokeRect(bx, by, bw, bh)
    ctx.font = '12px system-ui'
    const tw = ctx.measureText(b.class_name).width + 8
    ctx.fillStyle = color; ctx.fillRect(bx, by - 18, tw, 18)
    ctx.fillStyle = '#fff'; ctx.fillText(b.class_name, bx + 4, by - 4)
  })
  if (currentBox) {
    ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 2
    ctx.setLineDash([4, 4])
    ctx.strokeRect(currentBox.x, currentBox.y, currentBox.w, currentBox.h)
    ctx.setLineDash([])
  }
}

// ── Public actions ────────────────────────────────────────────
async function submit() {
  clearAutoSave()
  await doSubmit(true)
}

async function skip() {
  // Auto-save trước khi bỏ qua
  if (isDirty.value && canSubmit.value) await doSubmit(false)
  await fetchNext()
}
</script>

<style scoped>
.label-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 16px;
  height: calc(100vh - 100px);
}

.canvas-panel { display: flex; flex-direction: column; overflow: hidden; }
.no-image {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; gap: 16px;
  color: #64748b; font-size: 16px;
}
.canvas-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.filename { font-size: 13px; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; flex: 1; }

/* Save status */
.save-status { font-size: 11px; white-space: nowrap; }
.status-dirty  { color: #f59e0b; }
.status-saving { color: #38bdf8; }
.status-saved  { color: #22c55e; }

.canvas-wrap {
  display: grid; flex: 1; overflow: hidden;
  align-items: center; justify-content: center;
  background: #0f172a; border-radius: 8px;
}
.canvas-wrap > img, .canvas-wrap > canvas { grid-area: 1 / 1; }
.canvas-img {
  max-width: 100%; max-height: 100%;
  object-fit: contain; display: block; user-select: none;
  width: 100%; height: 100%;
}
.canvas-overlay { display: block; cursor: crosshair; justify-self: center; align-self: center; }
.canvas-hint { font-size: 12px; color: #64748b; margin-top: 8px; }

.controls-panel { display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
.control-section { padding: 14px; }
.section-label {
  font-size: 11px; font-weight: 600; color: #64748b;
  text-transform: uppercase; letter-spacing: .05em;
  display: block; margin-bottom: 10px;
}
.radio-group { display: flex; flex-direction: column; gap: 8px; }
.radio-label { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }

.class-list { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.class-item {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; border-radius: 8px; border: 1px solid #334155;
  background: #0f172a; transition: all .15s; min-height: 34px;
}
.class-item:hover { border-color: #475569; }
.class-item.active { border-color: #3b82f6; background: #1e3a5f; }
.class-name { flex: 1; font-size: 13px; color: #cbd5e1; cursor: pointer; user-select: none; }
.class-item.active .class-name { color: #93c5fd; font-weight: 600; }
.class-edit-input {
  flex: 1; background: #1e293b; border: 1px solid #3b82f6;
  color: #e2e8f0; padding: 2px 8px; border-radius: 4px; font-size: 13px; outline: none;
}
.btn-icon {
  background: none; border: none; color: #475569;
  cursor: pointer; font-size: 12px; padding: 2px 4px; flex-shrink: 0;
}
.btn-icon:hover { color: #94a3b8; }
.add-class { display: flex; gap: 6px; }
.add-class input {
  flex: 1; background: #0f172a; border: 1px solid #334155;
  color: #e2e8f0; padding: 6px 10px; border-radius: 6px; font-size: 13px; outline: none;
}

.box-list { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
.box-item {
  display: flex; align-items: center; gap: 6px;
  background: #0f172a; padding: 6px 10px; border-radius: 6px; font-size: 12px;
}
.box-label { font-weight: 600; color: #38bdf8; }
.box-coords { flex: 1; color: #64748b; }
.empty-hint { color: #475569; font-size: 12px; text-align: center; padding: 8px; }
.submit-btn { width: 100%; padding: 12px; font-size: 15px; }
</style>
