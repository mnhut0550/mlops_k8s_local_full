<template>
  <div class="train-page">

    <!-- Trigger card -->
    <div class="card trigger-card">
      <h2>Trigger Training</h2>

      <div class="form-row">
        <label>Snapshot version</label>
        <select v-model="selectedSnapshot" :disabled="loading">
          <option value="">— Tạo snapshot mới —</option>
          <option v-for="s in snapshots" :key="s.snapshot_id" :value="s.snapshot_id">
            {{ s.snapshot_id }} &nbsp;·&nbsp; {{ fmtDate(s.created_at) }}
            &nbsp;·&nbsp; {{ s.total_images }} ảnh
          </option>
        </select>
      </div>

      <div class="form-row">
        <label>Người trigger</label>
        <input v-model="triggeredBy" placeholder="Tên của bạn" :disabled="loading" />
      </div>

      <button class="btn btn-primary train-btn" :disabled="loading" @click="startTrain">
        <span v-if="loading">⏳ Đang gửi...</span>
        <span v-else>🚀 Train</span>
      </button>

      <div v-if="result" class="result-box" :class="result.ok ? 'ok' : 'err'">
        <template v-if="result.ok">
          ✅ Đã trigger CI/CD với snapshot <strong>{{ result.snapshot_id }}</strong>
        </template>
        <template v-else>
          ❌ {{ result.error }}
        </template>
      </div>
    </div>

    <!-- History table -->
    <div class="card history-card">
      <h2>Lịch sử Training</h2>
      <div v-if="history.length === 0" class="empty">Chưa có lần train nào.</div>
      <table v-else class="history-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Snapshot</th>
            <th>Thời gian</th>
            <th>Người trigger</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in history" :key="h.id">
            <td>{{ h.id }}</td>
            <td><span class="tag tag-version">{{ h.snapshot_id }}</span></td>
            <td>{{ fmtDate(h.triggered_at) }}</td>
            <td>{{ h.triggered_by }}</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const API = '/api'

const snapshots      = ref([])
const history        = ref([])
const selectedSnapshot = ref('')
const triggeredBy    = ref(localStorage.getItem('annotator') || '')
const loading        = ref(false)
const result         = ref(null)

async function loadData() {
  const [snapRes, histRes] = await Promise.all([
    fetch(`${API}/snapshots`).then(r => r.json()),
    fetch(`${API}/train/history`).then(r => r.json()),
  ])
  snapshots.value = (snapRes.snapshots || []).reverse()  // mới nhất lên đầu
  history.value   = histRes.history || []
}

async function startTrain() {
  loading.value = true
  result.value  = null
  try {
    const resp = await fetch(`${API}/train/start`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        snapshot_id:  selectedSnapshot.value || null,
        triggered_by: triggeredBy.value || 'anonymous',
      }),
    })
    const data = await resp.json()
    if (!resp.ok) {
      result.value = { ok: false, error: data.detail || 'Lỗi không xác định' }
    } else {
      result.value = { ok: true, snapshot_id: data.snapshot_id }
      await loadData()
    }
  } catch (e) {
    result.value = { ok: false, error: e.message }
  } finally {
    loading.value = false
  }
}

function fmtDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('vi-VN', { hour12: false })
}

onMounted(loadData)
</script>

<style scoped>
.train-page {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

h2 { margin: 0 0 20px; font-size: 16px; color: #e2e8f0; }

.trigger-card, .history-card { display: flex; flex-direction: column; }

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.form-row label {
  width: 130px;
  font-size: 13px;
  color: #94a3b8;
  flex-shrink: 0;
}
.form-row select,
.form-row input {
  flex: 1;
  background: #0f172a;
  border: 1px solid #475569;
  color: #e2e8f0;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}
.form-row select:focus,
.form-row input:focus { border-color: #3b82f6; }

.train-btn { margin-top: 8px; width: 140px; padding: 10px 0; font-size: 14px; }

.result-box {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
}
.result-box.ok  { background: #14532d; color: #86efac; border: 1px solid #166534; }
.result-box.err { background: #450a0a; color: #fca5a5; border: 1px solid #7f1d1d; }

.empty { color: #475569; font-size: 13px; text-align: center; padding: 24px 0; }

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.history-table th {
  text-align: left;
  padding: 8px 12px;
  color: #64748b;
  border-bottom: 1px solid #334155;
  font-weight: 500;
}
.history-table td {
  padding: 10px 12px;
  color: #cbd5e1;
  border-bottom: 1px solid #1e293b;
}
.history-table tr:last-child td { border-bottom: none; }

.tag-version {
  background: #1e3a5f;
  color: #93c5fd;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 12px;
}
</style>
