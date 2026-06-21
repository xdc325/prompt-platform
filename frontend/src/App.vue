<template>
  <div id="app">
    <header v-if="authStore.token">
      <nav>
        <router-link to="/projects">项目列表</router-link>
        <span class="user">{{ authStore.user?.email }}</span>
        <button @click="logout">退出登录</button>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import ToastContainer from './components/ToastContainer.vue'

const router = useRouter()

const authStore = reactive({
  token: localStorage.getItem('access_token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),

  setAuth(token, user) {
    this.token = token
    this.user = user
    localStorage.setItem('access_token', token)
    localStorage.setItem('user', JSON.stringify(user))
  },

  clear() {
    this.token = null
    this.user = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
  },
})

function logout() {
  authStore.clear()
  router.push('/login')
}

window.__auth = authStore
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
header { background: #1a1a2e; color: white; padding: 12px 24px; }
nav { display: flex; align-items: center; gap: 20px; }
nav a { color: #e0e0e0; text-decoration: none; }
nav a:hover { color: white; }
nav .user { margin-left: auto; color: #aaa; font-size: 14px; }
nav button { background: #e74c3c; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
main { max-width: 1200px; margin: 24px auto; padding: 0 24px; }
</style>
