const BASE = '/api/v1'

async function request(method, path, body = null) {
  const headers = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('access_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
    credentials: 'include',
  })

  const data = await res.json()
  if (!data.success) throw new Error(data.error || '请求失败')
  return data.data
}

export const api = {
  // Auth
  login: (body) => request('POST', '/auth/login', body),
  register: (body) => request('POST', '/auth/register', body),
  me: () => request('GET', '/auth/me'),

  // Projects
  createProject: (body) => request('POST', '/projects', body),
  listProjects: (page = 1) => request('GET', `/projects?page=${page}`),
  getProject: (id) => request('GET', `/projects/${id}`),
  deleteProject: (id) => request('DELETE', `/projects/${id}`),

  // Prompts
  listPrompts: (projectId, page = 1) => request('GET', `/projects/${projectId}/prompts?page=${page}`),
  getPrompt: (id) => request('GET', `/prompts/${id}`),
  createPrompt: (projectId, body) => request('POST', `/projects/${projectId}/prompts`, body),

  // Versions
  listVersions: (promptId) => request('GET', `/prompts/${promptId}/versions`),
  createVersion: (promptId, body) => request('POST', `/prompts/${promptId}/versions`, body),
  submitReview: (promptId, versionId) => request('POST', `/prompts/${promptId}/versions/${versionId}/submit`),
  deleteVersion: (promptId, versionId) => request('DELETE', `/prompts/${promptId}/versions/${versionId}`),
  diffVersions: (promptId, v1, v2) => request('GET', `/prompts/${promptId}/versions/${v1}/diff/${v2}`),
  publishVersion: (promptId, versionId) => request('POST', `/prompts/${promptId}/versions/${versionId}/publish`),

  // Tests
  createTestSuite: (promptId, body) => request('POST', `/prompts/${promptId}/test-suites`, body),
  listTestSuites: (promptId) => request('GET', `/prompts/${promptId}/test-suites`),
  deleteTestSuite: (promptId, suiteId) => request('DELETE', `/prompts/${promptId}/test-suites/${suiteId}`),
  runTest: (promptId, suiteId, versionId, model = 'deepseek-chat') => request('POST', `/prompts/${promptId}/test-suites/${suiteId}/run`, { version_id: versionId, model }),
  getTestRun: (runId) => request('GET', `/test-runs/${runId}`),

  // Playground
  playground: (promptId, body) => request('POST', `/prompts/${promptId}/playground`, body),
}
