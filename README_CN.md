# Prompt Platform — Prompt 工程管理平台

一个将 LLM Prompt 视为工程资产进行全生命周期管理的全栈平台，提供版本控制、回归测试、A/B 实验、多模型调试和审核发布功能。

---

## 功能

- **版本管理** — 创建、对比、回滚、删除提示词版本。逐词级 diff 可视化，高亮增/删/改。
- **回归测试** — 创建测试套件（输入 + 期望关键词），选择版本和模型通过后台 worker 异步执行，轮询展示通过率和每个用例的输出结果。
- **即时调试与对比** — 单版本 Playground 直接调用 LLM 查看效果；双版本对比同时执行两个版本，展示延迟和逐词差异。
- **A/B 实验** — 创建和管理两个版本间的对比实验，可配置流量分配比例。
- **多模型支持** — 工厂模式按模型名前缀自动路由到 OpenAI / DeepSeek / Claude Provider。
- **用户认证** — 邮箱注册 + 登录，双 Token 机制（access token + httpOnly refresh token），前端路由守卫。

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端框架 | Python FastAPI 0.138 + Uvicorn (异步) |
| ORM | SQLAlchemy 2.0 (异步) + asyncpg |
| 数据库 | PostgreSQL 16 |
| 消息队列 | Redis 7 + ARQ (后台任务 worker) |
| 前端 | Vue 3 (Composition API) + Vite |
| 反向代理 | Nginx (静态资源 + API 代理) |
| 部署 | Docker Compose (6 个服务) |

---

## 架构

```
nginx (:80)
  ├── /           → Vue 3 SPA
  └── /api/v1/*   → FastAPI (:8000)
                       ├── api/          — 7 个路由模块
                       ├── services/     — 7 个业务服务
                       ├── repositories/  — 9 个数据访问层
                       ├── models/        — 9 个 ORM 模型
                       ├── schemas/       — Pydantic 请求/响应校验
                       ├── providers/     — OpenAI / DeepSeek / Claude (工厂模式)
                       └── worker/        — ARQ 后台回归测试任务

Router → Service → Repository → Model
              ↘ Provider (LLM 调用)
```

所有 API 响应统一封装为 `{ success, data, error }` 格式。

---

## 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/xdc325/prompt-platform.git
cd prompt-platform

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填写一个 API Key（DEEPSEEK_API_KEY、OPENAI_API_KEY 或 ANTHROPIC_API_KEY）

# 3. 启动所有服务
docker compose up -d

# 4. 浏览器打开
# http://localhost
```

服务列表：`postgres`、`redis`、`backend` (:8000)、`frontend` (Vite dev)、`worker` (ARQ)、`nginx` (:80)。

---

## 项目规模

- **61** 个 Python 源文件，**约 3,400** 行（后端）
- **9** 个 Vue/JS 源文件，**约 1,100** 行（前端）
- **35** 个 REST API 端点
- **9** 张数据库表
- **47** 个端到端测试用例
- **6** 个 Docker Compose 服务

---

## 解决的实际问题

### 1. 外键约束级联删除（3 处修复）

**问题**：删除被外键引用的行时，PostgreSQL 报外键约束冲突。

**根因**：`prompt_versions` 有指向 `prompts` 的 `current_version_id` 外键，有自引用的 `parent_version_id` 外键；`test_runs` 有指向 `test_suites` 的外键；`experiments` 有指向 `versions` 的外键。直接 DELETE 会触发所有这些约束冲突。

**解决**：在 Service 层实现显式级联清理 ——
- 版本删除：先清除 prompt 的 `current_version_id` 和子版本的 `parent_version_id`，再执行 DELETE
- 项目删除：按完整级联顺序清理 —— prompts → versions → test_runs / experiments / experiment_results → suites → members
- 测试套件删除：先 DELETE 关联的 test_runs，再删除 suite

### 2. 后台任务队列从未生效（2 个 bug）

**问题**：测试套件点击"运行"后，创建了一条 status 为 "running" 的 test_run，但永远停留在这个状态，从未产生任何结果。

**根因**：
- `TestService.__init__` 接受 `arq` 参数，但 API 层从未传入 —— `self.arq` 始终为 `None`，`if self.arq:` 条件永远为假，`enqueue_job` 调用被静默跳过
- Worker 中使用 `async with async_session_factory() as session:` 上下文管理器并不会自动 commit（不同于 API 层的 `get_db` 依赖，后者在 finally 中调用 `session.commit()`）。更新 `test_run.results`、`test_run.status`、`test_run.finished_at` 后，所有修改全部丢失

**解决**：
- 在 `deps.py` 中添加 `get_arq()` 异步依赖，创建 ArqRedis 连接池
- 在 `run_test` API 路由中注入 arq 并传入 `TestService`
- 在 worker 中更新 test_run 后添加 `await session.commit()`

### 3. Worker 模型硬编码

**问题**：ARQ worker 中写死了 `get_provider("gpt-3.5-turbo")` 和 `provider.chat(model="gpt-3.5-turbo")`。只有 DeepSeek API Key 的用户永远无法运行回归测试。

**解决**：在 `TestRunRequest` schema 中添加 `model` 字段（默认 `deepseek-chat`），将 model 沿着 API → Service → ARQ job 参数 → worker 函数的链路传递。前端添加模型选择下拉框。

### 4. API Key 缺失时请求卡死（60 秒超时）

**问题**：没有有效的 API Key 时，Playground/Compare 功能仍然发起了 HTTP 请求（带着 `Authorization: Bearer None`），然后等待 httpx 的 60 秒超时才返回错误。用户感知为界面"卡住了"。

**解决**：在 `experiment_service.py` 的 playground 和 compare 方法中，创建 Provider 之前添加 API Key 存在性检查。根据模型前缀（`deepseek`、`claude`、`openai`）校验对应的配置项是否存在。如果缺失，立即抛出 `ConflictError` 并返回明确的中文错误信息——不发起任何 HTTP 请求。

### 5. Worker 输入模板渲染 Bug

**问题**：Worker 通过遍历 `case.get("input", {})` 的 `.items()` 来渲染模板变量。但 `input` 字段是字符串类型（如 `"我要退货"`），不是字典。对字符串调用 `.items()` 会得到字符对 `('我','我')`、`('要','要')`……导致逐字符级的乱码替换。

**解决**：改为 `version.content.replace("{input}", str(case_input))`，直接替换占位符，与 schema 定义保持一致。

### 6. 前端交互问题（3 处修复）

- **展开/收起阈值**：长提示词内容仅在 120px / 8 行处截断。调整为 200px / 12 行。
- **关闭对比按钮重叠**：`float` 布局导致关闭按钮与 diff 内容叠加。改为 flexbox header 布局。
- **缺少删除按钮**：项目和版本都没有删除入口。添加了红色删除按钮，带确认弹窗。

### 7. 多 Provider 路由设计

**问题**：不同 LLM Provider 有不同的 API 端点和认证方式。硬编码单一 Provider 限制了平台可用性。

**解决**：设计了 Provider 工厂模式：
- `BaseProvider` 抽象类，定义 `chat()` 和 `chat_stream()` 接口
- `OpenAIProvider`、`DeepSeekProvider`、`ClaudeProvider` —— 各自持有独立的 base URL 和 API Key
- `get_provider(model)` 工厂函数按模型名前缀路由（`deepseek-*` → DeepSeek、`claude-*` → Claude、其他 → OpenAI）
- `DeepSeekProvider` 继承 `OpenAIProvider`（DeepSeek API 与 OpenAI 兼容），仅重写 `__init__` 传入不同的 API Key 和 base URL

---

## 关键设计决策

- **Repository 模式**：所有数据访问通过继承 `BaseRepository` 的仓库层进行，Service 层仅在级联删除时写原生 SQL。
- **PromptAccessMixin**：权限校验逻辑在一个 Mixin 中实现，被 5 个 Service 复用，一次方法调用即可验证用户是否为项目成员。
- **不可变操作**：Service 层始终返回新对象，从不原地修改输入参数。
- **统一响应格式**：所有端点返回 `{ success, data, error }`。前端错误处理只需一个分支。

---

## License

MIT
