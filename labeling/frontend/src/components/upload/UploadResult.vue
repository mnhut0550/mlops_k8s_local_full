<template>
  <div>
    <div v-if="result" class="card result-card">
      <template v-if="result.mode === 'yolo'">
        <div class="result-title">✅ Upload YOLO thành công!</div>
        <div class="result-rows">
          <div>🖼 Ảnh đã upload: <strong>{{ result.uploaded }}</strong></div>
          <div>🏷 Ảnh có label: <strong>{{ result.withLabel }}</strong></div>
          <div>📦 Annotations tạo: <strong>{{ result.annotated }}</strong></div>
        </div>
      </template>
      <template v-else>
        <div class="result-title">✅ Upload thành công!</div>
        <div class="result-rows">
          <div>🖼 Ảnh đã upload: <strong>{{ result.uploaded }}</strong></div>
          <div v-if="result.auto_labeled > 0">🏷 Auto-labeled: <strong>{{ result.auto_labeled }}</strong></div>
        </div>
      </template>
    </div>

    <div v-if="errorMsg" class="card error-card">
      ❌ {{ errorMsg }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  result:   Object,
  errorMsg: String,
})
</script>

<style scoped>
.result-card { border: 1px solid #22c55e; background: #052e16; }
.result-title { font-weight: 700; color: #4ade80; margin-bottom: 10px; }
.result-rows  { display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
.error-card   { border: 1px solid #ef4444; background: #2d0707; color: #fca5a5; }
</style>
