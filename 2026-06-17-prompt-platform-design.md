# Prompt 工程管理平台 — 设计文档

## 项目定位

**把 Prompt（提示词）当成代码一样管理。** 提供版本控制、回归测试、A/B 实验、审核发布、效果监控的完整工程化平台。

痛点：代码有 Git、有 CI/CD、有测试，但 LLM prompt 散落在飞书文档、Notion、硬编码里，改动不可追溯，效果好坏全凭感觉。

---

## 技术栈

| 组件 | 选择 | 原因 |
|------|------|------|
| Web 框架 | FastAPI | async 原生，OpenAPI 自动生成 |
| ORM | SQLAlchemy 2.0 | async session，生态最大 |
| 数据库驱动 | asyncpg | 最快的 PostgreSQL 异步驱动 |
| 数据库迁移 | Alembic | SQLAlchemy 官方搭档 |
| 任务队列 | ARQ | 轻量、async 原生、只依赖 Redis |
| SSE | sse-starlette | FastAPI 生态标准 |
| 配置管理 | Pydantic Settings | FastAPI 生态 |
| HTTP 客户端 | httpx | async 原生 |
| 重试库 | tenacity | Python 重试库事实标准 |
| 日志 | structlog | 结构化日志 |
| 缓存 | Redis | LRU + TTL |
| 前端 | Vue 3 + Vite | 轻量、响应式 |
| 反向代理 | Nginx | 静态资源 + 反向代理 + HTTPS |
| 容器 | Docker Compose | 单机部署 |

必须项：Python 3.12+, PostgreSQL 16+, Redis 7+, Node.js 22+。

---

## 不做的事情 (YAGNI)

- 不用微服务 — 单体 FastAPI 对面试项目足够
- 不用 Kubernetes — docker-compose 足够展示
- 不做 WebSocket — SSE + 轮询够用
- 不做 OAuth / 第三方登录 — 邮箱密码 + JWT 够用
- 不做 RBAC 细粒度权限 — 项目级 Owner / Editor / Viewer 够用

---

## 架构

```
┌─────────────────────────────────────────────────┐
│                   Nginx (:80/:443)              │
│             反向代理 + 静态资源                   │
└─────────────────────┬───────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────┴───────────┐     ┌────────┴──────────┐
│   FastAPI :8000   │     │   Vue 3 (前端)    │
│                    │     │   可由 Nginx 代理  │
│  api/              │     └───────────────────┘
│    ├── prompts.py  │
│    ├── tests.py    │
│    ├── experiments │
│    └── reports.py  │
│                    │
│  services/  ← 全部业务逻辑     │
│  repositories/  ← 数据库操作   │
│  providers/     ← LLM 抽象     │
│    ├── base.py       (重试/缓存/限流)  │
│    ├── openai.py                      │
│    └── claude.py                      │
│                    │
│  core/             │
│    ├── config.py   (Pydantic Settings)│
│    ├── deps.py     (DI 依赖)          │
│    └── exceptions.py                 │
└────────┬──────────┘
         │
         │  Redis ────┐
         │  (缓存+队列)│
         │            │
┌────────┴──────────┐ │
│   PostgreSQL      │ │
│   :5432           │ │
└───────────────────┘ │
                       │
              ┌────────┴──────────┐
              │   ARQ Worker      │
              │  • 回归测试执行    │
              │  • A/B 实验分流    │
              └───────────────────┘
```

### 分层职责

| 层 | 职责 | 依赖 |
|----|------|------|
| **Router** (`api/`) | 参数校验、路由分发 | Service |
| **Service** (`services/`) | 所有业务逻辑 | Repository + Provider |
| **Repository** (`repositories/`) | 数据库 CRUD | SQLAlchemy Session |
| **Provider** (`providers/`) | LLM 调用统一抽象 | 外部 LLM API |

Router 不调 Repository，Service 不碰 HTTP，Repository 不碰业务逻辑。

### Provider 层设计

```
BaseProvider (抽象基类)
  ├── chat(prompt, params) → ChatResult
  ├── chat_stream(prompt, params) → AsyncIterator[str]
  ├── 内置重试 (tenacity, 指数退避, 3次)
  ├── 内置缓存 (缓存键 = model + prompt + params 的 SHA256)
  └── 内置限流 (asyncio.Semaphore)

OpenAIProvider  ─┐
ClaudeProvider   ├── 实现 _call_api(), _call_stream_api()
OtherProvider   ─┘
```

---

## 数据模型

### ER 总览

```
users ──────────────────────────────┐
    │                               │
    │ (created_by)                  │
    ▼                               │
projects ──── members ──── users ───┘
    │
    ├─── prompts
    │        │
    │        ├─── prompt_versions (核心)
    │        │        │
    │        │        ├─── deployments
    │        │        ├─── test_runs
    │        │        └─── experiments
    │        │                   │
    │        │            experiment_results
    │        │
    │        └─── test_suites
    │
    └─── (project 级操作日志)
```

### 核心表定义

**users**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| hashed_password | VARCHAR(255) | NOT NULL (bcrypt) |
| display_name | VARCHAR(100) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**projects**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| name | VARCHAR(200) | NOT NULL |
| description | TEXT | |
| owner_id | FK → users.id | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

**project_members**

| 列 | 类型 | 约束 |
|----|------|------|
| project_id | FK → projects.id | PK (复合) |
| user_id | FK → users.id | PK (复合) |
| role | ENUM('owner','editor','viewer') | NOT NULL |

**prompts**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| project_id | FK → projects.id | NOT NULL, INDEX |
| name | VARCHAR(200) | NOT NULL |
| description | TEXT | |
| current_version_id | FK → prompt_versions | NULLABLE (首次创建为空) |
| created_by | FK → users.id | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

**prompt_versions** (核心)

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| prompt_id | FK → prompts.id | NOT NULL, INDEX |
| version_number | INTEGER | NOT NULL, (prompt_id, version_number) UNIQUE |
| content | TEXT | NOT NULL |
| variables | JSONB | `["var1", "var2"]` |
| status | ENUM | `draft`, `pending_review`, `published`, `archived` |
| created_by | FK → users.id | NOT NULL |
| parent_version_id | FK → prompt_versions | NULLABLE |
| changelog | TEXT | 变更说明 |
| created_at | TIMESTAMPTZ | NOT NULL |

版本号在 prompt 级别自增。status 状态机：`draft → pending_review → published → archived`，pending_review 可回退到 draft。

**test_suites**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| prompt_id | FK → prompts.id | NOT NULL |
| name | VARCHAR(200) | NOT NULL |
| test_cases | JSONB | `[{input:..., expected:...}, ...]` |
| created_at | TIMESTAMPTZ | NOT NULL |

**test_runs**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| test_suite_id | FK → test_suites.id | NOT NULL |
| version_id | FK → prompt_versions.id | NOT NULL |
| status | ENUM('running','completed','failed') | NOT NULL |
| results | JSONB | `[{case_index, passed, output, expected}, ...]` |
| pass_rate | FLOAT | NULLABLE |
| started_at | TIMESTAMPTZ | NOT NULL |
| finished_at | TIMESTAMPTZ | NULLABLE |

**experiments**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| prompt_id | FK → prompts.id | NOT NULL |
| version_a_id | FK → prompt_versions.id | NOT NULL |
| version_b_id | FK → prompt_versions.id | NOT NULL |
| traffic_split | JSONB | `{"a": 0.5, "b": 0.5}` |
| status | ENUM('running','completed','stopped') | NOT NULL |
| started_at | TIMESTAMPTZ | NOT NULL |
| ended_at | TIMESTAMPTZ | NULLABLE |

**experiment_results**

| 列 | 类型 | 约束 |
|----|------|------|
| id | UUID | PK |
| experiment_id | FK → experiments.id | NOT NULL, INDEX |
| version | ENUM('a','b') | NOT NULL |
| input | TEXT | NOT NULL |
| output | TEXT | NOT NULL |
| latency_ms | INTEGER | NOT NULL |
| cost | NUMERIC(10,6) | NOT NULL |
| quality_score | INTEGER | NULLABLE (人工评分) |

---

## API 设计

### 约定

- 前缀：`/api/v1`
- 响应格式：`{"success": bool, "data": T, "error": null | string}`
- 分页：`?page=1&page_size=20`，返回 `{"items": [...], "total": N, "page": 1, "page_size": 20}`
- 认证：`Authorization: Bearer <access_token>`

### 认证

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
```

JWT 策略：access_token 30 分钟过期（内存），refresh_token 7 天过期（httpOnly cookie）。密码 bcrypt 加密。

### 项目管理

```
POST   /api/v1/projects                           # 创建项目
GET    /api/v1/projects                           # 我的项目列表
GET    /api/v1/projects/{id}                      # 项目详情
PATCH  /api/v1/projects/{id}                      # 更新
DELETE /api/v1/projects/{id}                      # 软删除
POST   /api/v1/projects/{id}/members               # 邀请成员
GET    /api/v1/projects/{id}/members               # 成员列表
DELETE /api/v1/projects/{id}/members/{user_id}      # 移除成员
```

### Prompt 管理

```
POST   /api/v1/projects/{project_id}/prompts       # 创建
GET    /api/v1/projects/{project_id}/prompts       # 列表（分页、搜索）
GET    /api/v1/prompts/{prompt_id}                 # 详情（含 current_version）
PATCH  /api/v1/prompts/{prompt_id}                 # 更新基本信息
DELETE /api/v1/prompts/{prompt_id}                 # 软删除
```

### 版本管理（核心）

```
GET    /api/v1/prompts/{prompt_id}/versions                   # 版本列表
GET    /api/v1/prompts/{prompt_id}/versions/{version_id}      # 版本详情
POST   /api/v1/prompts/{prompt_id}/versions                   # 新建 draft 版本
POST   /api/v1/prompts/{prompt_id}/versions/{id}/submit       # 提交审核 → pending_review
POST   /api/v1/prompts/{prompt_id}/versions/{id}/publish     # 发布 → published
POST   /api/v1/prompts/{prompt_id}/rollback                   # 回滚到指定版本
GET    /api/v1/prompts/{prompt_id}/versions/{v1}/diff/{v2}    # 两版本逐行 diff
```

#### Diff 响应格式

```json
{
  "version_a": {"number": 3, "created_at": "2026-06-10"},
  "version_b": {"number": 4, "created_at": "2026-06-17"},
  "changes": [
    {
      "type": "replaced",
      "position": 3,
      "old": "你是一个资深后端代码审查员。",
      "new": "你是一个资深全栈代码审查员，尤其擅长安全漏洞分析。",
      "context_before": "角色：",
      "context_after": "请审查以下代码。"
    },
    {
      "type": "added",
      "position": 8,
      "old": null,
      "new": "如果发现问题，请同时给出修复建议的代码示例。",
      "context_before": "请审查以下代码。",
      "context_after": "输出格式：表格。"
    },
    {
      "type": "removed",
      "position": 12,
      "old": "注意：不需要给出修改建议。",
      "new": null,
      "context_before": "输出格式：表格。",
      "context_after": null
    }
  ],
  "summary": "3 处变更：1 处修改、1 处新增、1 处删除"
}
```

### 回归测试

```
POST   /api/v1/prompts/{prompt_id}/test-suites               # 创建测试集
GET    /api/v1/prompts/{prompt_id}/test-suites               # 测试集列表
PUT    /api/v1/prompts/{prompt_id}/test-suites/{id}          # 更新测试集
DELETE /api/v1/prompts/{prompt_id}/test-suites/{id}          # 删除
POST   /api/v1/prompts/{prompt_id}/test-suites/{id}/run      # 执行测试 → 返回 task_id
GET    /api/v1/test-runs/{run_id}                            # 查询结果
GET    /api/v1/test-runs/{run_id}/stream                     # SSE 实时推送每个用例结果
```

SSE 推送消息格式：

```
event: case_result
data: {"case_index": 3, "total": 20, "passed": true, "input": "...", "output": "..."}

event: complete
data: {"pass_rate": 0.85, "total_cases": 20, "passed": 17, "failed": 3}
```

### A/B 实验

```
POST   /api/v1/prompts/{prompt_id}/experiments       # 创建实验
GET    /api/v1/prompts/{prompt_id}/experiments       # 实验列表
GET    /api/v1/experiments/{id}                      # 实验详情 + 统计摘要
POST   /api/v1/experiments/{id}/stop                 # 停止实验
DELETE /api/v1/prompts/{prompt_id}/experiments/{id}  # 删除实验
GET    /api/v1/experiments/{id}/results              # 结果列表（分页）
```

实验详情包含统计摘要：

```json
{
  "status": "running",
  "version_a": "v2", "version_b": "v3",
  "traffic_split": {"a": 0.5, "b": 0.5},
  "summary": {
    "version_a": {"avg_latency_ms": 1200, "avg_quality": 3.8, "call_count": 145},
    "version_b": {"avg_latency_ms": 900,  "avg_quality": 4.2, "call_count": 152}
  }
}
```

### 效果看板

```
GET    /api/v1/prompts/{prompt_id}/metrics            # 核心指标
GET    /api/v1/prompts/{prompt_id}/metrics/history     # 历史趋势
GET    /api/v1/projects/{project_id}/dashboard         # 项目全局看板
```

### 在线调试

```
POST   /api/v1/prompts/{prompt_id}/playground          # 单版本调试
POST   /api/v1/prompts/{prompt_id}/playground/stream   # 流式调试 (SSE)
POST   /api/v1/prompts/{prompt_id}/compare             # 两版本同输入对比
```

对比响应带 output_diff：

```json
{
  "input": "...",
  "results": [
    {"version": "v3", "output": "发现 2 个问题：...", "latency_ms": 1500, "cost": 0.003},
    {"version": "v4", "output": "发现 3 个问题：...", "latency_ms": 1200, "cost": 0.002}
  ],
  "output_diff": [
    {"type": "same", "text": "发现 "},
    {"type": "changed", "a": "2", "b": "3"},
    {"type": "same", "text": " 个问题：\n..."}
  ]
}
```

---

## 测试策略

| 层 | 测什么 | 工具 | 目标覆盖率 |
|----|------|------|------|
| Repository | 数据库操作正确性 | 真实本地 PG, pytest-asyncio | 90%+ |
| Service | 业务逻辑 | mock Repository | 85%+ |
| Provider | LLM 调用行为 | mock httpx | 80%+ |
| API | 端到端流程 | httpx AsyncClient, 真实 DB | 80%+ |
| E2E | 关键用户路径 | pytest + httpx, docker-compose 独立 service | 核心流程 |

### 关键测试用例

**PromptService**

- 创建 prompt 后 current_version 为空
- 发布版本后 status 变为 published 且 current_version 更新
- 同一 prompt 内版本号自动递增
- 回滚到 v3 后 current_version 指向 v3
- 已经是 published 的同 prompt 版本不受影响

**TestService**

- 全部用例通过时 pass_rate = 1.0
- 空测试集运行报错
- 正在运行中的测试不能重复启动
- SSE 流正确推送每个用例结果

**Provider 层**

- 相同请求第二次命中缓存
- 限流错误自动重试 3 次后失败
- 超时错误指数退避
- 不同 model 生成不同缓存键

**API 层**

- 未登录返回 401
- 访问他人项目返回 403
- 分页参数负数返回 422
- JSON body 格式错误返回 422 带错误定位

---

## 部署

### Docker Compose 拓扑

```
┌────────────────────────────────────────┐
│          Docker Compose                │
│                                        │
│  ┌────────────┐ ┌──────────────┐      │
│  │  FastAPI   │ │  ARQ Worker  │      │
│  │  :8000     │ │  (后台任务)   │      │
│  └─────┬──────┘ └──────┬───────┘      │
│        │               │              │
│  ┌─────┴───────────────┴──────┐       │
│  │  PostgreSQL :5432         │       │
│  │  Redis      :6379         │       │
│  │  (data 均挂 volume 持久化) │       │
│  └────────────────────────────┘       │
│                                        │
│  ┌────────────┐  ┌──────────────┐     │
│  │  前端       │  │    Nginx     │     │
│  │  Vue 3     │  │   :80/:443   │     │
│  └────────────┘  └──────────────┘     │
└────────────────────────────────────────┘
```

### 启动

```bash
docker compose up -d  # 一键启动全部 6 个服务
```

启动顺序：PostgreSQL / Redis → Alembic 迁移 → FastAPI / ARQ Worker / 前端 / Nginx。

### 健康检查

| 服务 | 检查方式 |
|------|---------|
| FastAPI | `GET /api/v1/health` |
| PostgreSQL | `pg_isready` |
| Redis | `redis-cli ping` |

### 日志

structlog 结构化日志，本地控制台彩色输出，生产 JSON 格式。每个请求自动注入 request_id 用于链路追踪。

---

## 面试叙事要点

1. **解决真实痛点**：「现在每个公司用 LLM，但 prompt 散落在各处，没人管版本和效果」
2. **工程化思维**：「把 prompt 当成代码来管理——版本控制、测试、实验、审核」
3. **架构分层**：「Router → Service → Repository → Provider，每层独立可测」
4. **LLM 抽象层设计**：「BaseProvider 封装了重试、缓存、限流，换模型只加一个子类」
5. **异步全链路**：「从 FastAPI async 路由到 asyncpg 驱动到 ARQ 任务队列，全链路不阻塞」
6. **技术选型有思考**：「选 ARQ 而非 Celery，因为 ARQ 原生 async，和 FastAPI 技术栈一致」
7. **安全基础**：「JWT + bcrypt + 参数校验 + 防注入，Pydantic 做输入边界」
8. **可扩展**：「下一步就是把 prompt template + 工具绑定，形成 Agent 系统」
