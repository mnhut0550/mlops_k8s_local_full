<template>
  <div class="app">
    <nav class="nav">
      <span class="nav-brand">🏷️ Labeling Tool</span>
      <div class="nav-links">
        <router-link to="/">Upload</router-link>
        <router-link to="/label">Label</router-link>
        <router-link to="/progress">Progress</router-link>
        <router-link to="/train">Train</router-link>
      </div>
      <input v-model="annotator" placeholder="Tên của bạn" class="annotator-input" />
    </nav>
    <main class="main">
      <router-view :annotator="annotator" />
    </main>

    <UploadToast />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import UploadToast from '@/components/UploadToast.vue'

const annotator = ref(localStorage.getItem('annotator') || '')
watch(annotator, v => localStorage.setItem('annotator', v))
</script>

<style>
.app { min-height: 100vh; display: flex; flex-direction: column; }

.nav {
  display: flex; align-items: center; gap: 24px;
  padding: 12px 24px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
}
.nav-brand { font-weight: 700; font-size: 18px; color: #38bdf8; }
.nav-links { display: flex; gap: 16px; margin-right: auto; }
.nav-links a {
  color: #94a3b8; text-decoration: none; font-size: 14px;
  padding: 6px 12px; border-radius: 6px; transition: all .2s;
}
.nav-links a:hover, .nav-links a.router-link-active {
  color: #e2e8f0; background: #334155;
}
.annotator-input {
  background: #334155; border: 1px solid #475569;
  color: #e2e8f0; padding: 6px 12px; border-radius: 6px;
  font-size: 13px; width: 160px; outline: none;
}
.main { flex: 1; padding: 24px; }

/* Shared utilities */
.card {
  background: #1e293b; border: 1px solid #334155;
  border-radius: 12px; padding: 20px;
}
.btn {
  padding: 8px 16px; border-radius: 8px; border: none;
  cursor: pointer; font-size: 14px; font-weight: 500;
  transition: all .2s;
}
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:hover { background: #2563eb; }
.btn-success { background: #22c55e; color: white; }
.btn-success:hover { background: #16a34a; }
.btn-danger  { background: #ef4444; color: white; }
.btn-danger:hover  { background: #dc2626; }
.btn-ghost   { background: #334155; color: #e2e8f0; }
.btn-ghost:hover   { background: #475569; }
.btn:disabled { opacity: .5; cursor: not-allowed; }

.tag {
  display: inline-block; padding: 2px 8px; border-radius: 9999px;
  font-size: 12px; font-weight: 500;
}
.tag-unlabeled { background: #334155; color: #94a3b8; }
.tag-labeled   { background: #166534; color: #86efac; }
</style>
