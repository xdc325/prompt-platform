import { reactive } from 'vue'

const toasts = reactive([])
let nextId = 0

export function useToast() {
  function add(message, type = 'info', duration = 3000) {
    const id = nextId++
    toasts.push({ id, message, type })
    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
    return id
  }

  function remove(id) {
    const idx = toasts.findIndex(t => t.id === id)
    if (idx !== -1) toasts.splice(idx, 1)
  }

  return {
    toasts,
    success: (msg) => add(msg, 'success'),
    error: (msg) => add(msg, 'error', 5000),
    info: (msg) => add(msg, 'info'),
    remove,
  }
}
