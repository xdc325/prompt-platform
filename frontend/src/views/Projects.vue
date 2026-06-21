<template>
  <div class="projects">
    <div class="header">
      <h1>项目列表</h1>
      <button @click="showCreate = true">+ 新建项目</button>
    </div>

    <div v-if="showCreate" class="create-form">
      <input v-model="newName" placeholder="项目名称" @keyup.enter="createProject" />
      <textarea v-model="newDesc" placeholder="描述（可选）"></textarea>
      <button @click="createProject" :disabled="creating">创建</button>
      <button @click="showCreate = false" class="cancel">取消</button>
    </div>

    <div v-if="loading" class="state">加载中...</div>
    <div v-else-if="error" class="state error">{{ error }}</div>
    <div v-else class="list">
      <div
        v-for="p in projects"
        :key="p.id"
        class="card"
        :class="{ selected: selectedProject?.id === p.id }"
        @click="selectProject(p.id)"
      >
        <div class="card-header">
          <h3>{{ p.name }}</h3>
          <button
            class="delete-project-btn"
            :disabled="deletingProject === p.id"
            @click.stop="confirmDeleteProject(p.id)"
          >
            {{ deletingProject === p.id ? '删除中...' : '删除' }}
          </button>
        </div>
        <p>{{ p.description || '暂无描述' }}</p>
        <span class="date">{{ new Date(p.created_at).toLocaleDateString() }}</span>
      </div>
      <p v-if="projects.length === 0" class="empty">暂无项目，点击上方按钮创建第一个</p>
    </div>

    <div v-if="selectedProject" class="prompts-section">
      <h2>{{ selectedProject.name }} — 提示词</h2>
      <button @click="showCreatePrompt = true">+ 新建提示词</button>
      <div v-if="showCreatePrompt" class="create-form">
        <input v-model="promptName" placeholder="提示词名称" @keyup.enter="createPrompt" />
        <textarea v-model="promptDesc" placeholder="描述（可选）"></textarea>
        <button @click="createPrompt" :disabled="creatingPrompt">创建</button>
        <button @click="showCreatePrompt = false" class="cancel">取消</button>
      </div>
      <div v-if="loadingPrompts" class="state">加载提示词...</div>
      <div v-else>
        <div
          v-for="p in prompts"
          :key="p.id"
          class="prompt-card"
          @click="$router.push(`/prompts/${p.id}`)"
        >
          <h3>{{ p.name }}</h3>
          <p>{{ p.description || '暂无描述' }}</p>
          <span>更新于：{{ new Date(p.updated_at).toLocaleString() }}</span>
        </div>
        <p v-if="prompts.length === 0" class="empty">暂无提示词，点击上方按钮创建第一个</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client.js'
import { useToast } from '../composables/useToast.js'

const route = useRoute()
const toast = useToast()

const projects = ref([])
const loading = ref(true)
const error = ref('')
const showCreate = ref(false)
const newName = ref('')
const newDesc = ref('')
const creating = ref(false)

const selectedProject = ref(null)
const prompts = ref([])
const loadingPrompts = ref(false)
const showCreatePrompt = ref(false)
const promptName = ref('')
const promptDesc = ref('')
const creatingPrompt = ref(false)
const deletingProject = ref(null)

onMounted(async () => {
  try {
    const data = await api.listProjects()
    projects.value = data.items
    if (route.params.projectId) {
      selectProject(route.params.projectId)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function createProject() {
  creating.value = true
  try {
    await api.createProject({ name: newName.value, description: newDesc.value || null })
    showCreate.value = false
    newName.value = ''
    newDesc.value = ''
    const data = await api.listProjects()
    projects.value = data.items
    toast.success('项目创建成功')
  } catch (e) {
    toast.error(e.message)
  } finally {
    creating.value = false
  }
}

async function selectProject(id) {
  selectedProject.value = projects.value.find(p => p.id === id)
  loadingPrompts.value = true
  try {
    const data = await api.listPrompts(id)
    prompts.value = data.items
  } catch (e) {
    toast.error('加载提示词失败')
  } finally {
    loadingPrompts.value = false
  }
}

async function createPrompt() {
  creatingPrompt.value = true
  try {
    await api.createPrompt(selectedProject.value.id, { name: promptName.value, description: promptDesc.value || null })
    showCreatePrompt.value = false
    promptName.value = ''
    promptDesc.value = ''
    const data = await api.listPrompts(selectedProject.value.id)
    prompts.value = data.items
    toast.success('提示词创建成功')
  } catch (e) {
    toast.error(e.message)
  } finally {
    creatingPrompt.value = false
  }
}

async function confirmDeleteProject(projectId) {
  if (!confirm('确定要删除这个项目吗？项目下的所有提示词和版本都会被删除，此操作不可撤销。')) return
  deletingProject.value = projectId
  try {
    await api.deleteProject(projectId)
    if (selectedProject.value?.id === projectId) {
      selectedProject.value = null
      prompts.value = []
    }
    const data = await api.listProjects()
    projects.value = data.items
    toast.success('项目已删除')
  } catch (e) {
    toast.error(e.message)
  } finally {
    deletingProject.value = null
  }
}
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.header button { padding: 10px 20px; background: #2ecc71; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.state { text-align: center; color: #999; padding: 24px; }
.state.error { color: #e74c3c; }
.empty { color: #999; text-align: center; padding: 24px; }
.list { display: grid; gap: 12px; }
.card { background: white; padding: 16px; border-radius: 8px; border: 1px solid #e0e0e0; cursor: pointer; transition: all 0.15s; }
.card:hover { border-color: #1a1a2e; }
.card.selected { border-color: #3498db; border-width: 2px; background: #f0f7ff; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
.card-header h3 { margin-bottom: 0; }
.delete-project-btn { padding: 2px 8px; border: 1px solid #e74c3c; border-radius: 4px; background: white; color: #e74c3c; cursor: pointer; font-size: 11px; white-space: nowrap; }
.delete-project-btn:hover { background: #fde8e8; }
.delete-project-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.card p { color: #666; font-size: 14px; }
.card .date { color: #999; font-size: 12px; }
.create-form { background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; }
.create-form input, .create-form textarea { display: block; width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; }
.create-form textarea { height: 80px; }
.create-form button { padding: 8px 16px; background: #2ecc71; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 8px; }
.create-form button:disabled { opacity: 0.6; cursor: not-allowed; }
.create-form button.cancel { background: #999; }
.prompts-section { margin-top: 40px; }
.prompts-section h2 { margin-bottom: 16px; }
.prompt-card { background: white; padding: 16px; border-radius: 8px; border: 1px solid #e0e0e0; cursor: pointer; margin-bottom: 8px; transition: border-color 0.15s; }
.prompt-card:hover { border-color: #3498db; }
.prompt-card span { color: #999; font-size: 12px; }
</style>
