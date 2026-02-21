# Deep Research

一个以“会话驱动”为核心的深度研究系统：

- 左侧会话管理（可多轮、多会话）
- 中间聊天时间线（方案、进度、报告）
- 右侧 Markdown 研究方案编辑器（可手改可执行）
- 后端异步执行引擎（规划 DAG -> 检索证据 -> 冲突检测 -> 生成报告）

---

## 1. 当前能力（基于当前代码）

- FastAPI + SQLite 后端，支持任务与会话两套 API。
- 会话主流程：
  1. 创建会话自动生成首版方案（`PLAN_DRAFT`）
  2. 用户在聊天里继续“改方案 / 改报告 / 触发重跑”
  3. 执行完成后在时间线返回 `FINAL_REPORT`
- 执行引擎支持：暂停、恢复、终止、快照恢复。
- 检索支持 Tavily / arXiv / Semantic Scholar（按配置与可用 Key 启用）。
- 分析支持：证据打分、数值冲突检测、冲突投票接口。
- 写作支持：报告模板化生成、可选 LLM 润色、`.md + .bib` 产物落盘。
- 前端支持：移动端抽屉、进度分组折叠、历史轮次显示/隐藏、报告下载。

---

## 2. 技术栈

### 后端

- Python `>=3.11`（脚本默认 `3.12`）
- FastAPI / Pydantic v2 / Uvicorn
- SQLite（WAL）

### 前端

- React 18 + TypeScript + Vite
- 纯前端状态管理（`useState/useMemo/useEffect`）

### 测试

- pytest（unit + integration）
- ruff

---

## 3. 快速启动

### 3.1 环境要求

- `uv`
- Node.js `20+`
- npm `10+`

### 3.2 后端

```bash
./scripts/run_backend.sh
```

该脚本会执行：

1. 创建 `.venv`（Python 3.12）
2. 安装 `backend[dev]`
3. 启动 `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

启动后可访问：

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- 健康检查: `GET /healthz`

### 3.3 前端

```bash
./scripts/run_frontend.sh
```

默认地址（见 `frontend/vite.config.ts`）：

- `http://127.0.0.1:5174`

> 如果端口被占用，Vite 会提示并可能切换端口。

---

## 4. `.env` 配置

后端配置读取规则：

- 文件：项目根目录 `.env`
- 前缀：`DR_`
- 定义位置：`backend/app/core/config.py`

关键项：

- 执行模式：`DR_USE_MOCK_SOURCES`
  - `true`：完全走 mock 数据（测试/离线验证）
  - `false`：调用真实检索/模型接口
- 默认模型路由：
  - `DR_DEFAULT_LLM_PROVIDER`（`openrouter | deepseek | openai`）
  - `DR_DEFAULT_LLM_MODEL`
- 检索 Key：`DR_TAVILY_API_KEY` 等

安全建议：

- 不要把真实 API Key 提交到仓库。
- 如果曾提交过，立即轮换（rotate）并改为本地私有配置。

---

## 5. 最短使用流程（UI）

1. 打开前端页面，点“新建研究”。
2. 第一条消息输入研究主题（最多 500 字）。
3. 等待 Agent 返回第一版研究方案（自动写入右侧草稿）。
4. 可直接编辑草稿并“保存草稿”。
5. 点击“开始研究”。
6. 中间时间线查看进度分组（SEARCHING / WRITING_SECTION 等阶段）。
7. 完成后出现“当前报告”，可继续发送“改写报告/补检索/重跑”指令。
8. 点击“下载 Markdown”导出报告。

---

## 6. 常用 API（按实现）

### 任务

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `PUT /api/v1/tasks/{task_id}`
- `DELETE /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/dag`
- `POST /api/v1/tasks/{task_id}/start|pause|resume|abort|recover`
- `GET /api/v1/tasks/{task_id}/snapshot`
- `GET /api/v1/tasks/{task_id}/report`
- `GET /api/v1/tasks/{task_id}/report/download`
- `WS /api/v1/ws/task/{task_id}/progress`

### 会话

- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `PATCH /api/v1/conversations/{conversation_id}`（重命名）
- `DELETE /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations`（全部删除）
- `POST /api/v1/conversations/{conversation_id}/plan/revise`
- `PUT /api/v1/conversations/{conversation_id}/plan`
- `POST /api/v1/conversations/{conversation_id}/run`
- `GET /api/v1/conversations/{conversation_id}/report/download`

### 证据与冲突

- `GET /api/v1/evidence`
- `GET /api/v1/evidence/{evidence_id}`
- `POST /api/v1/evidence/{evidence_id}/vote`
- `GET /api/v1/tasks/{task_id}/conflicts`

### MCP

- `POST /api/v1/mcp/execute`
  - `mode=read` -> 直接执行
  - `mode=write|execute` -> `USER_CONFIRMATION_REQUIRED`

---

## 7. 目录结构（核心）

```text
backend/
  app/
    api/routes/              # REST + WS
    core/                    # config / sqlite schema
    models/schemas.py        # 全部 Pydantic 模型
    repositories/            # 持久化层
    services/                # 规划/检索/分析/写作/执行/会话编排
frontend/
  src/
    App.tsx                  # 三栏主状态机
    api.ts                   # 所有 HTTP 调用封装
    components/              # 时间线/侧栏/编辑器/对话框
scripts/
  run_backend.sh
  run_frontend.sh
  run_real_case.py
tests/
  unit/
  integration/
```

---

## 8. 测试与构建

```bash
uv venv --python 3.12 .venv --clear
source .venv/bin/activate
uv pip install -e 'backend[dev]'
ruff check backend tests
pytest tests/unit tests/integration
cd frontend && npm run build
```

---

## 9. 一键跑真实案例（脚本）

```bash
python scripts/run_real_case.py \
  --title "2026年AI Agent在软件工程中的应用现状与挑战" \
  --description "基于公开资料分析进展、风险与落地策略" \
  --sources "tavily" \
  --timeout 120
```

该脚本会：创建任务 -> 启动执行 -> 轮询终态 -> 打印证据数 -> 输出报告预览。

---

## 10. 已知边界

- 单用户本地模式；无鉴权/多租户。
- 执行引擎当前按节点顺序执行（非分布式并行调度）。
- `ConversationAgent` 的意图识别基于关键词规则，不是分类模型。
- `MCPExecutor` 目前是最小可用实现（read 模拟执行）。

---

## 11. 深入文档

- 详细实现说明：`doc.md`
- 端到端流程手册：`WORKFLOW.md`
- 本地发布说明：`docs/LOCAL_RELEASE.md`
- UI 回归清单：`docs/UI_REGRESSION_CHECKLIST.md`
