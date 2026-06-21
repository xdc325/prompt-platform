import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Projects from '../views/Projects.vue'
import PromptDetail from '../views/PromptDetail.vue'

const routes = [
  { path: '/', redirect: '/projects' },
  { path: '/login', component: Login, meta: { guest: true } },
  { path: '/projects', component: Projects, meta: { auth: true } },
  { path: '/projects/:projectId', component: Projects, meta: { auth: true } },
  { path: '/prompts/:promptId', component: PromptDetail, meta: { auth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.auth && !token) return '/login'
  if (to.meta.guest && token) return '/projects'
})

export default router
