<template>
  <Teleport to="body">
    <div v-if="visible" class="overlay" @click.self="emit('cancel')">
      <div class="dialog">
        <div class="dialog-icon">{{ icon }}</div>
        <div class="dialog-title">{{ title }}</div>
        <div class="dialog-body">
          <slot />
        </div>
        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="emit('cancel')">Hủy</button>
          <button class="btn btn-success" @click="emit('confirm')">{{ confirmLabel }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible:      { type: Boolean, default: false },
  title:        { type: String,  default: 'Xác nhận' },
  icon:         { type: String,  default: '📤' },
  confirmLabel: { type: String,  default: 'Xác nhận' },
})
const emit = defineEmits(['confirm', 'cancel'])
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; z-index: 10000;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  animation: fadeIn .15s ease;
}
.dialog {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 32px 36px;
  min-width: 360px;
  max-width: 480px;
  box-shadow: 0 24px 64px rgba(0,0,0,.6);
  animation: slideUp .2s ease;
  text-align: center;
}
.dialog-icon  { font-size: 40px; margin-bottom: 12px; }
.dialog-title { font-size: 18px; font-weight: 700; margin-bottom: 14px; }
.dialog-body  { font-size: 14px; color: #94a3b8; line-height: 1.7; margin-bottom: 24px; }
.dialog-actions { display: flex; gap: 12px; justify-content: center; }
.dialog-actions .btn { min-width: 100px; }

@keyframes fadeIn  { from { opacity: 0 } to { opacity: 1 } }
@keyframes slideUp { from { transform: translateY(20px); opacity: 0 } to { transform: none; opacity: 1 } }
</style>
