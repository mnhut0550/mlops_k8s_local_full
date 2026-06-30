<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">Tiến độ gắn nhãn</h2>
      <button class="btn btn-ghost" @click="load">🔄 Refresh</button>
    </div>

    <div v-if="loading" class="loading">Đang tải...</div>

    <div v-else class="stats-grid">

      <!-- Overall -->
      <div class="card stat-card">
        <div class="stat-title">Tổng cộng</div>
        <div class="stat-number">{{ stats.total }}</div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: pct(stats.labeled, stats.total) + '%' }"></div>
        </div>
        <div class="stat-sub">{{ stats.labeled }} labeled · {{ stats.unlabeled }} chưa label</div>
      </div>

      <!-- Detection -->
      <div class="card stat-card">
        <div class="stat-title">Detection</div>
        <div class="stat-number">{{ stats.by_task?.detection?.total ?? 0 }}</div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: pct(stats.by_task?.detection?.labeled, stats.by_task?.detection?.total) + '%' }"></div>
        </div>
        <div class="stat-sub">{{ stats.by_task?.detection?.labeled ?? 0 }} labeled</div>
      </div>

      <!-- Classification -->
      <div class="card stat-card">
        <div class="stat-title">Classification</div>
        <div class="stat-number">{{ stats.by_task?.classification?.total ?? 0 }}</div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: pct(stats.by_task?.classification?.labeled, stats.by_task?.classification?.total) + '%' }"></div>
        </div>
        <div class="stat-sub">{{ stats.by_task?.classification?.labeled ?? 0 }} labeled</div>
      </div>

    </div>

    <!-- Per-annotator -->
    <div v-if="stats.by_annotator?.length" class="card" style="margin-top:16px">
      <div class="section-title">Theo annotator</div>
      <table class="annotator-table">
        <thead>
          <tr>
            <th>Annotator</th>
            <th>Ảnh đã label</th>
            <th>Bbox / label</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in stats.by_annotator" :key="a.annotator">
            <td>{{ a.annotator || 'anonymous' }}</td>
            <td>{{ a.images_labeled }}</td>
            <td>{{ a.annotations }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Per-class distribution -->
    <div v-if="stats.by_class?.length" class="card" style="margin-top:16px">
      <div class="section-title">Phân bố class</div>
      <div class="class-bars">
        <div v-for="c in stats.by_class" :key="c.label" class="class-bar-row">
          <span class="class-bar-label">{{ c.label }}</span>
          <div class="class-bar-track">
            <div class="class-bar-fill" :style="{ width: pct(c.count, maxClassCount) + '%' }"></div>
          </div>
          <span class="class-bar-count">{{ c.count }}</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const stats   = ref({})
const loading = ref(false)

const maxClassCount = computed(() => {
  const arr = stats.value.by_class ?? []
  return arr.reduce((m, c) => Math.max(m, c.count), 1)
})

function pct(a, b) {
  if (!b) return 0
  return Math.round((a / b) * 100)
}

async function load() {
  loading.value = true
  try {
    const res = await axios.get('/api/stats')
    stats.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 700; }
.loading { color: #64748b; }

.stats-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
}
.stat-card { text-align: center; }
.stat-title { font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: #64748b; margin-bottom: 8px; }
.stat-number { font-size: 40px; font-weight: 700; color: #38bdf8; margin-bottom: 12px; }
.progress-bar {
  height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin-bottom: 8px;
}
.progress-fill { height: 100%; background: #3b82f6; border-radius: 4px; transition: width .5s; }
.stat-sub { font-size: 13px; color: #64748b; }

.section-title { font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 14px; }

.annotator-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.annotator-table th {
  text-align: left; padding: 8px 12px;
  color: #64748b; font-weight: 500; font-size: 12px;
  border-bottom: 1px solid #334155;
}
.annotator-table td { padding: 10px 12px; border-bottom: 1px solid #1e293b; }
.annotator-table tr:last-child td { border-bottom: none; }

.class-bars { display: flex; flex-direction: column; gap: 10px; }
.class-bar-row { display: flex; align-items: center; gap: 12px; }
.class-bar-label { width: 120px; font-size: 13px; text-align: right; color: #94a3b8; }
.class-bar-track { flex: 1; height: 10px; background: #334155; border-radius: 5px; overflow: hidden; }
.class-bar-fill { height: 100%; background: #22c55e; border-radius: 5px; transition: width .5s; }
.class-bar-count { width: 40px; font-size: 13px; color: #64748b; }
</style>
