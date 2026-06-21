<template>
  <div class="login">
    <h1>Prompt 管理平台</h1>
    <form @submit.prevent="isRegister ? handleRegister() : handleLogin()">
      <input v-model="email" type="email" placeholder="邮箱" required />
      <input v-if="isRegister" v-model="displayName" placeholder="显示名称" required />
      <input v-model="password" type="password" placeholder="密码" minlength="8" required />
      <button type="submit" :disabled="submitting">{{ isRegister ? '注册' : '登录' }}</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <p class="hint">
      {{ isRegister ? '已有账号？' : '没有账号？' }}
      <a href="#" @click.prevent="isRegister = !isRegister; error = ''">{{ isRegister ? '去登录' : '去注册' }}</a>
    </p>
    <p class="demo-hint">演示：任意邮箱注册即可体验</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client.js'

const router = useRouter()
const isRegister = ref(false)
const email = ref('')
const displayName = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function handleLogin() {
  submitting.value = true
  try {
    const data = await api.login({ email: email.value, password: password.value })
    window.__auth.setAuth(data.access_token, data.user)
    router.push('/projects')
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

async function handleRegister() {
  submitting.value = true
  try {
    const data = await api.register({ email: email.value, password: password.value, display_name: displayName.value })
    window.__auth.setAuth(data.access_token, data.user)
    router.push('/projects')
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login { max-width: 400px; margin: 100px auto; text-align: center; }
h1 { margin-bottom: 32px; color: #1a1a2e; }
input { display: block; width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; }
button { width: 100%; padding: 12px; background: #1a1a2e; color: white; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; margin-top: 16px; }
.error { color: #e74c3c; margin-top: 12px; }
.hint { color: #999; margin-top: 20px; font-size: 13px; }
.hint a { color: #3498db; text-decoration: none; }
.hint a:hover { text-decoration: underline; }
.demo-hint { color: #bbb; margin-top: 8px; font-size: 12px; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
