<template>
  <div class="prompt-detail">
    <button class="back" @click="$router.push('/projects')">&larr; 返回项目列表</button>

    <div v-if="loading.prompt" class="loading">加载提示词...</div>
    <template v-else-if="prompt">
      <h1>{{ prompt.name }}</h1>
      <p class="desc">{{ prompt.description || '暂无描述' }}</p>

      <section>
        <h2>版本管理</h2>
        <button @click="showCreate = true" class="new-btn">+ 新建版本</button>

        <div v-if="showCreate" class="form">
          <textarea v-model="newContent" placeholder="提示词内容，用 {{变量名}} 做占位符" rows="8"></textarea>
          <input v-model="newChangelog" placeholder="变更说明（可选）" />
          <button @click="createVersion" :disabled="creating">创建草稿</button>
          <button @click="showCreate = false" class="cancel">取消</button>
        </div>

        <div v-if="diffSelection.length === 1" class="diff-hint">
          请选择第二个版本进行对比 — 点击另一个版本的 <strong>对比</strong> 按钮
          <button @click="diffSelection = []" class="cancel-hint">取消</button>
        </div>

        <div v-if="loading.versions" class="loading">加载版本列表...</div>
        <div v-else class="version-list">
          <div
            v-for="v in versions"
            :key="v.id"
            class="version-card"
            :class="{
              current: v.id === prompt.current_version_id,
              'diff-selected': diffSelection.includes(v.id),
            }"
          >
            <div class="v-header">
              <span class="v-number">v{{ v.version_number }}</span>
              <span class="v-status" :class="v.status">{{ statusLabel(v.status) }}</span>
              <span v-if="v.id === prompt.current_version_id" class="current-badge">当前版本</span>
              <span v-if="v.changelog" class="changelog-badge" :title="v.changelog">变更说明</span>
            </div>
            <div class="v-content-wrapper">
              <pre class="v-content" :class="{ collapsed: !expandedVersions.has(v.id) }">{{ v.content }}</pre>
              <button
                v-if="v.content && v.content.split('\n').length > 12"
                class="expand-btn"
                @click="toggleExpand(v.id)"
              >
                {{ expandedVersions.has(v.id) ? '收起' : '展开' }}
              </button>
            </div>
            <div class="v-actions">
              <button
                v-if="v.status === 'pending_review'"
                @click="publish(v.id)"
                :disabled="publishing === v.id"
              >
                {{ publishing === v.id ? '发布中...' : '发布' }}
              </button>
              <button
                v-if="v.status === 'draft'"
                @click="submitReview(v.id)"
                :disabled="submitting === v.id"
              >
                {{ submitting === v.id ? '提交中...' : '提交审核' }}
              </button>
              <button
                @click="toggleDiffSelection(v.id)"
                :class="{ active: diffSelection.includes(v.id) }"
              >
                {{ diffSelection.includes(v.id) ? '已选中' : '对比' }}
              </button>
              <button @click="openPlayground(v.id)">测试</button>
              <button
                v-if="v.status === 'draft' || v.status === 'archived'"
                @click="confirmDelete(v.id)"
                :disabled="deleting === v.id"
                class="delete-btn"
              >
                {{ deleting === v.id ? '删除中...' : '删除' }}
              </button>
            </div>
          </div>
          <p v-if="versions.length === 0" class="empty">暂无版本，创建第一个吧</p>
        </div>
      </section>

      <section class="test-suites-section">
        <h2>测试套件</h2>
        <button @click="showCreateSuite = true" class="new-btn">+ 新建测试套件</button>

        <div v-if="showCreateSuite" class="form">
          <input v-model="newSuiteName" placeholder="套件名称（如：回归测试）" />
          <div class="test-cases-editor">
            <div v-for="(tc, idx) in newSuiteCases" :key="idx" class="test-case-row">
              <input v-model="tc.input" :placeholder="'测试输入 ' + (idx + 1) + '（如：我要退货）'" />
              <input v-model="tc.expected" :placeholder="'期望包含（可选）'" />
              <button @click="newSuiteCases.splice(idx, 1)" class="remove-case-btn">×</button>
            </div>
            <button @click="newSuiteCases.push({ input: '', expected: '' })" class="add-case-btn">+ 添加测试用例</button>
          </div>
          <button @click="createTestSuite" :disabled="creatingSuite">创建套件</button>
          <button @click="showCreateSuite = false; newSuiteCases = [{ input: '', expected: '' }]" class="cancel">取消</button>
        </div>

        <div v-if="loading.suites" class="loading">加载测试套件...</div>
        <div v-else class="suite-list">
          <div v-for="s in testSuites" :key="s.id" class="suite-card">
            <div class="suite-header">
              <span class="suite-name">{{ s.name }}</span>
              <span class="suite-count">{{ s.test_cases?.length || 0 }} 个用例</span>
              <button @click="confirmDeleteSuite(s.id)" :disabled="deletingSuite === s.id" class="delete-btn small">
                {{ deletingSuite === s.id ? '删除中...' : '删除' }}
              </button>
            </div>
            <div class="suite-cases">
              <div v-for="(tc, idx) in s.test_cases" :key="idx" class="suite-case">
                <span class="case-idx">#{{ idx + 1 }}</span>
                <span class="case-input">输入：{{ tc.input }}</span>
                <span v-if="tc.expected" class="case-expected">期望包含：{{ tc.expected }}</span>
              </div>
            </div>
            <div class="suite-actions">
              <select v-model="runVersionId" class="run-version-select">
                <option value="">选择版本...</option>
                <option v-for="v in versions" :key="v.id" :value="v.id">v{{ v.version_number }} ({{ statusLabel(v.status) }})</option>
              </select>
              <select v-model="runModel" class="run-model-select">
                <option value="deepseek-chat">DeepSeek Chat</option>
                <option value="deepseek-reasoner">DeepSeek Reasoner</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                <option value="gpt-4o">GPT-4o</option>
                <option value="claude-sonnet-4-6">Claude Sonnet 4.6</option>
                <option value="claude-haiku-4-5">Claude Haiku 4.5</option>
              </select>
              <button @click="runTestSuite(s.id)" :disabled="!runVersionId || runningSuite === s.id">
                {{ runningSuite === s.id ? '运行中...' : '运行测试' }}
              </button>
            </div>
            <div v-if="testRunResult && testRunResult.suiteId === s.id" class="test-run-result">
              <h4>测试结果</h4>
              <div v-if="testRunResult.loading" class="loading">等待结果...</div>
              <template v-else>
                <div class="result-summary">
                  通过率：{{ (testRunResult.pass_rate * 100).toFixed(0) }}%
                  （{{ testRunResult.passed }}/{{ testRunResult.total }}）
                </div>
                <div v-for="(r, idx) in testRunResult.results" :key="idx" class="result-case" :class="{ passed: r.passed, failed: !r.passed }">
                  <span class="case-idx">#{{ r.case_index + 1 }}</span>
                  <span>{{ r.passed ? '✓ 通过' : '✗ 失败' }}</span>
                  <div v-if="r.output" class="result-output">输出：{{ r.output?.substring(0, 200) }}{{ r.output?.length > 200 ? '...' : '' }}</div>
                  <div v-if="r.error" class="result-error">错误：{{ r.error }}</div>
                </div>
              </template>
            </div>
          </div>
          <p v-if="testSuites.length === 0" class="empty">暂无测试套件，创建第一个来验证提示词质量</p>
        </div>
      </section>

      <section v-if="diffResult" class="diff-section">
        <div class="diff-header">
          <h2>版本对比：v{{ diffResult.version_a?.number }} &rarr; v{{ diffResult.version_b?.number }}</h2>
          <button @click="diffResult = null" class="close-diff">关闭</button>
        </div>
        <div v-for="(c, i) in diffResult.changes" :key="i" class="diff-change" :class="c.type">
          <span class="diff-type">{{ c.type }}</span>
          <div v-if="c.old" class="diff-old">- {{ c.old }}</div>
          <div v-if="c.new" class="diff-new">+ {{ c.new }}</div>
        </div>
        <p class="diff-summary">{{ diffResult.summary }}</p>
      </section>

      <section v-if="showPlayground" class="playground">
        <h2>即时测试 — v{{ playgroundVersion?.version_number }}</h2>
        <div class="playground-form">
          <textarea v-model="playgroundInput" placeholder="输入测试内容..." rows="4"></textarea>
          <select v-model="playgroundModel">
            <optgroup label="OpenAI">
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
            </optgroup>
            <optgroup label="DeepSeek">
              <option value="deepseek-chat">DeepSeek Chat</option>
              <option value="deepseek-coder">DeepSeek Coder</option>
            </optgroup>
          </select>
          <button @click="runPlayground" :disabled="playing">
            {{ playing ? '运行中...' : '运行' }}
          </button>
          <button @click="showPlayground = false" class="cancel">关闭</button>
        </div>
        <div v-if="playgroundResult" class="playground-result">
          <h3>输出结果</h3>
          <pre>{{ playgroundResult.output }}</pre>
        </div>
      </section>
    </template>

    <div v-else class="error-state">提示词不存在</div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client.js'
import { useToast } from '../composables/useToast.js'

const route = useRoute()
const promptId = route.params.promptId
const toast = useToast()

const prompt = ref(null)
const versions = ref([])
const diffResult = ref(null)
const playgroundResult = ref(null)

const showCreate = ref(false)
const newContent = ref('')
const newChangelog = ref('')

const diffSelection = ref([])
const expandedVersions = reactive(new Set())
const showPlayground = ref(false)
const playgroundVersion = ref(null)
const playgroundInput = ref('')
const playgroundModel = ref('gpt-3.5-turbo')

const loading = reactive({ prompt: true, versions: true, suites: true })
const creating = ref(false)
const publishing = ref(null)
const submitting = ref(null)
const playing = ref(false)
const deleting = ref(null)

// Test suites
const testSuites = ref([])
const showCreateSuite = ref(false)
const newSuiteName = ref('')
const newSuiteCases = ref([{ input: '', expected: '' }])
const creatingSuite = ref(false)
const deletingSuite = ref(null)
const runVersionId = ref('')
const runModel = ref('deepseek-chat')
const runningSuite = ref(null)
const testRunResult = ref(null)

function statusLabel(status) {
  const map = { draft: '草稿', pending_review: '待审核', published: '已发布', archived: '已归档' }
  return map[status] || status
}

onMounted(async () => {
  try {
    prompt.value = await api.getPrompt(promptId)
  } catch (e) {
    toast.error('加载提示词失败')
  } finally {
    loading.prompt = false
  }

  try {
    const data = await api.listVersions(promptId)
    versions.value = data.items
  } catch (e) {
    toast.error('加载版本列表失败')
  } finally {
    loading.versions = false
  }

  loadTestSuites()
})

async function createVersion() {
  creating.value = true
  try {
    await api.createVersion(promptId, { content: newContent.value, variables: [], changelog: newChangelog.value || null })
    showCreate.value = false
    newContent.value = ''
    newChangelog.value = ''
    const data = await api.listVersions(promptId)
    versions.value = data.items
    toast.success('草稿创建成功')
  } catch (e) {
    toast.error(e.message)
  } finally {
    creating.value = false
  }
}

async function publish(versionId) {
  publishing.value = versionId
  try {
    await api.publishVersion(promptId, versionId)
    prompt.value = await api.getPrompt(promptId)
    const data = await api.listVersions(promptId)
    versions.value = data.items
    toast.success('版本已发布')
  } catch (e) {
    toast.error(e.message)
  } finally {
    publishing.value = null
  }
}

async function submitReview(versionId) {
  submitting.value = versionId
  try {
    await api.submitReview(promptId, versionId)
    const data = await api.listVersions(promptId)
    versions.value = data.items
    toast.success('已提交审核')
  } catch (e) {
    toast.error(e.message)
  } finally {
    submitting.value = null
  }
}

async function confirmDelete(versionId) {
  if (!confirm('确定要删除这个版本吗？此操作不可撤销。')) return
  deleting.value = versionId
  try {
    await api.deleteVersion(promptId, versionId)
    const data = await api.listVersions(promptId)
    versions.value = data.items
    toast.success('版本已删除')
  } catch (e) {
    toast.error(e.message)
  } finally {
    deleting.value = null
  }
}

function toggleDiffSelection(versionId) {
  const idx = diffSelection.value.indexOf(versionId)
  if (idx !== -1) {
    diffSelection.value.splice(idx, 1)
    return
  }
  diffSelection.value.push(versionId)
  if (diffSelection.value.length === 2) {
    loadDiff(diffSelection.value[0], diffSelection.value[1])
    diffSelection.value = []
  }
}

async function loadDiff(v1, v2) {
  try {
    diffResult.value = await api.diffVersions(promptId, v1, v2)
  } catch (e) {
    toast.error(e.message)
  }
}

function toggleExpand(versionId) {
  if (expandedVersions.has(versionId)) {
    expandedVersions.delete(versionId)
  } else {
    expandedVersions.add(versionId)
  }
}

function openPlayground(versionId) {
  const v = versions.value.find(x => x.id === versionId)
  playgroundVersion.value = v
  playgroundInput.value = ''
  playgroundResult.value = null
  showPlayground.value = true
}

async function runPlayground() {
  playing.value = true
  try {
    playgroundResult.value = await api.playground(promptId, {
      version_id: playgroundVersion.value.id,
      input: playgroundInput.value,
      model: playgroundModel.value,
    })
  } catch (e) {
    toast.error(e.message)
  } finally {
    playing.value = false
  }
}

// --- Test Suite functions ---

async function loadTestSuites() {
  loading.suites = true
  try {
    const data = await api.listTestSuites(promptId)
    testSuites.value = data.items
  } catch (e) {
    // Test suites are optional, don't toast on failure
  } finally {
    loading.suites = false
  }
}

async function createTestSuite() {
  if (!newSuiteName.value.trim() || newSuiteCases.value.some(c => !c.input.trim())) {
    toast.error('请填写套件名称和所有测试用例的输入')
    return
  }
  creatingSuite.value = true
  try {
    const body = {
      name: newSuiteName.value,
      test_cases: newSuiteCases.value.map(c => ({
        input: c.input,
        expected: c.expected || null,
      })),
    }
    await api.createTestSuite(promptId, body)
    showCreateSuite.value = false
    newSuiteName.value = ''
    newSuiteCases.value = [{ input: '', expected: '' }]
    await loadTestSuites()
    toast.success('测试套件创建成功')
  } catch (e) {
    toast.error(e.message)
  } finally {
    creatingSuite.value = false
  }
}

async function confirmDeleteSuite(suiteId) {
  if (!confirm('确定要删除这个测试套件吗？')) return
  deletingSuite.value = suiteId
  try {
    await api.deleteTestSuite(promptId, suiteId)
    await loadTestSuites()
    toast.success('测试套件已删除')
  } catch (e) {
    toast.error(e.message)
  } finally {
    deletingSuite.value = null
  }
}

async function runTestSuite(suiteId) {
  if (!runVersionId.value) return
  runningSuite.value = suiteId
  testRunResult.value = { suiteId, loading: true }
  try {
    // Enqueue the test run
    const run = await api.runTest(promptId, suiteId, runVersionId.value, runModel.value)
    // Poll for results (worker processes in background)
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000))
      const result = await api.getTestRun(run.id)
      if (result.status === 'completed' || result.status === 'failed') {
        testRunResult.value = {
          suiteId,
          loading: false,
          pass_rate: result.pass_rate,
          passed: result.results?.filter(r => r.passed).length || 0,
          total: result.results?.length || 0,
          results: result.results || [],
        }
        return
      }
    }
    testRunResult.value = { suiteId, loading: false, error: '测试超时，请稍后刷新查看结果' }
  } catch (e) {
    toast.error(e.message)
    testRunResult.value = null
  } finally {
    runningSuite.value = null
  }
}
</script>

<style scoped>
.prompt-detail { max-width: 900px; }
.back { background: none; border: none; color: #3498db; cursor: pointer; font-size: 14px; margin-bottom: 16px; }
h1 { color: #1a1a2e; margin-bottom: 8px; }
.desc { color: #666; margin-bottom: 24px; }
.loading { text-align: center; color: #999; padding: 24px; }
.empty { color: #999; text-align: center; padding: 24px; }
.new-btn { padding: 8px 16px; background: #2ecc71; color: white; border: none; border-radius: 4px; cursor: pointer; }
.form { background: white; padding: 16px; border-radius: 8px; margin: 16px 0; }
.form textarea, .form input { display: block; width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; font-family: inherit; }
.form button { padding: 8px 16px; background: #2ecc71; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 8px; }
.form button:disabled { opacity: 0.6; cursor: not-allowed; }
.form button.cancel { background: #999; }
.diff-hint {
  background: #eef6ff; border: 1px solid #3498db; border-radius: 6px;
  padding: 10px 16px; margin: 12px 0; color: #2c3e50; font-size: 14px;
  display: flex; align-items: center; justify-content: space-between;
}
.cancel-hint { background: none; border: 1px solid #999; border-radius: 4px; padding: 4px 10px; cursor: pointer; font-size: 12px; color: #666; }
.version-list { display: grid; gap: 12px; margin-top: 16px; }
.version-card { background: white; padding: 16px; border-radius: 8px; border: 1px solid #e0e0e0; transition: border-color 0.15s; }
.version-card.current { border-color: #2ecc71; border-width: 2px; }
.version-card.diff-selected { border-color: #3498db; border-width: 2px; background: #f0f7ff; }
.v-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.v-number { font-weight: bold; font-size: 18px; color: #1a1a2e; }
.v-status { padding: 2px 8px; border-radius: 12px; font-size: 12px; }
.v-status.draft { background: #f0f0f0; color: #666; }
.v-status.pending_review { background: #fef3cd; color: #856404; }
.v-status.published { background: #d4edda; color: #155724; }
.v-status.archived { background: #e2e3e5; color: #383d41; }
.current-badge { padding: 2px 8px; background: #2ecc71; color: white; border-radius: 12px; font-size: 12px; }
.changelog-badge { padding: 2px 8px; background: #e8f4fd; color: #2980b9; border-radius: 12px; font-size: 12px; cursor: help; }
.v-content-wrapper { position: relative; }
.v-content { background: #f8f9fa; padding: 12px; border-radius: 4px; font-size: 13px; white-space: pre-wrap; }
.v-content.collapsed { max-height: 200px; overflow: hidden; }
.expand-btn { background: none; border: none; color: #3498db; font-size: 12px; cursor: pointer; padding: 4px 0; display: block; width: 100%; text-align: center; }
.v-actions { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
.v-actions button { padding: 4px 12px; border: 1px solid #ddd; border-radius: 4px; background: white; cursor: pointer; font-size: 13px; transition: all 0.15s; }
.v-actions button:hover { background: #f0f0f0; }
.v-actions button:disabled { opacity: 0.6; cursor: not-allowed; }
.v-actions button.active { background: #3498db; color: white; border-color: #3498db; }
.v-actions button.delete-btn { color: #e74c3c; border-color: #e74c3c; }
.v-actions button.delete-btn:hover { background: #fde8e8; }
.diff-section { margin-top: 32px; background: white; padding: 16px; border-radius: 8px; }
.diff-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.diff-header h2 { margin: 0; }
.close-diff { background: none; border: 1px solid #ddd; border-radius: 4px; color: #666; cursor: pointer; font-size: 13px; padding: 4px 12px; }
.diff-change { padding: 12px; border-radius: 6px; margin: 8px 0; }
.diff-change.replaced { background: #fff3cd; }
.diff-change.added { background: #d4edda; }
.diff-change.removed { background: #f8d7da; }
.diff-type { font-weight: bold; font-size: 12px; text-transform: uppercase; }
.diff-old { color: #c0392b; font-family: monospace; }
.diff-new { color: #27ae60; font-family: monospace; }
.diff-summary { color: #666; font-size: 14px; margin-top: 12px; }
.playground { margin-top: 32px; background: white; padding: 16px; border-radius: 8px; }
.playground-form { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; }
.playground-form textarea, .playground-form select { padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: inherit; font-size: 14px; }
.playground-form button { padding: 8px 16px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; }
.playground-form button:disabled { opacity: 0.6; }
.playground-form button.cancel { background: #999; }
.playground-result { margin-top: 16px; }
.playground-result h3 { font-size: 14px; color: #666; margin-bottom: 8px; }
.playground-result pre { background: #f8f9fa; padding: 16px; border-radius: 8px; white-space: pre-wrap; }
.error-state { text-align: center; color: #e74c3c; padding: 48px; }

/* Test Suites */
.test-suites-section { margin-top: 40px; }
.test-suites-section h2 { margin-bottom: 12px; }
.test-cases-editor { margin: 12px 0; }
.test-case-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: center; }
.test-case-row input { flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-family: inherit; font-size: 13px; }
.remove-case-btn { background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; padding: 4px 10px; font-size: 16px; line-height: 1; }
.add-case-btn { background: none; border: 1px dashed #3498db; color: #3498db; border-radius: 4px; cursor: pointer; padding: 6px 12px; font-size: 13px; margin-bottom: 8px; }
.suite-list { display: grid; gap: 12px; margin-top: 16px; }
.suite-card { background: white; padding: 16px; border-radius: 8px; border: 1px solid #e0e0e0; }
.suite-header { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.suite-name { font-weight: bold; font-size: 16px; color: #1a1a2e; }
.suite-count { color: #999; font-size: 13px; }
.suite-cases { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.suite-case { font-size: 13px; color: #555; padding: 6px 10px; background: #f8f9fa; border-radius: 4px; display: flex; gap: 12px; flex-wrap: wrap; }
.case-idx { color: #999; font-weight: bold; }
.case-expected { color: #27ae60; }
.suite-actions { display: flex; gap: 8px; align-items: center; }
.run-version-select, .run-model-select { padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; }
.suite-actions button { padding: 6px 14px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
.suite-actions button:disabled { opacity: 0.6; cursor: not-allowed; }
.test-run-result { margin-top: 16px; padding: 16px; background: #f8f9fa; border-radius: 8px; }
.test-run-result h4 { font-size: 14px; margin-bottom: 8px; color: #1a1a2e; }
.result-summary { font-size: 16px; font-weight: bold; margin-bottom: 12px; color: #2c3e50; }
.result-case { padding: 8px 12px; border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.result-case.passed { background: #d4edda; color: #155724; }
.result-case.failed { background: #f8d7da; color: #721c24; }
.result-output { margin-top: 4px; font-family: monospace; font-size: 12px; color: #555; }
.result-error { margin-top: 4px; color: #e74c3c; font-size: 12px; }
.delete-btn.small { padding: 2px 8px; font-size: 11px; }
</style>
