<template>
  <div class="toast-container">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast"
      :class="t.type"
      @click="remove(t.id)"
    >
      {{ t.message }}
    </div>
  </div>
</template>

<script setup>
import { useToast } from '../composables/useToast.js'
const { toasts, remove } = useToast()
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 360px;
}
.toast {
  padding: 12px 16px;
  border-radius: 6px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  animation: slideIn 0.25s ease;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.toast.success { background: #27ae60; }
.toast.error { background: #e74c3c; }
.toast.info { background: #3498db; }
@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
</style>
