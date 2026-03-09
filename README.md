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

---

## 12. 项目进展情况与规划（2026-02-26）

### 12.1 当前进展（已完成）

1. 已完成会话驱动主链路：从“主题输入 -> 自动生成方案 -> 研究执行 -> 报告产出 -> 继续改写/重跑”全流程可用。
2. 已完成核心工程能力：任务生命周期管理、执行引擎暂停/恢复/终止/快照恢复、进度流式回传（WS）。
3. 已完成主要业务模块：检索（Tavily/arXiv/Semantic Scholar）、证据评分、冲突检测、模板化报告与下载。
4. 已完成基础前端交互：三栏布局、会话管理、方案编辑、阶段进度折叠、报告导出、移动端抽屉适配。
5. 已具备基础质量保障：`pytest`（单测+集成）和 `ruff` 静态检查已接入开发流程。

### 12.2 当前阶段判断

- 当前处于 **MVP 可验证阶段**：核心闭环已跑通，已具备内部试用与真实课题验证条件。
- 主要短板集中在：多用户与权限体系、调度并行能力、意图识别智能化、线上可观测性与稳定性治理。

### 12.3 后续规划（建议）

#### 近期（2-4 周）

1. 稳定性强化：补齐关键路径集成测试、失败重试与超时策略、异常可观测日志。
2. 执行质量优化：提升检索去重与证据筛选策略，降低无效引用与冲突噪声。
3. 交互体验优化：细化进度状态文案，增强报告改写与版本对比体验。

#### 中期（1-2 个月）

1. 平台化能力：引入用户鉴权与多租户隔离，完善项目/会话级权限模型。
2. 调度能力升级：从顺序执行演进到受控并行调度，提升长任务吞吐与时延表现。
3. 规划智能升级：将关键词规则逐步替换为可评估的意图分类/路由策略。

#### 远期（1 个季度）

1. 生产级可运维：完善指标体系（成功率、平均耗时、重跑率、引用有效率）与告警机制。
2. 生态扩展：标准化 MCP 工具接入流程，支持更多外部数据源与执行插件。
3. 交付标准化：形成可复用模板（行业研究、竞品分析、技术调研）与最佳实践手册。

### 12.4 里程碑与验收口径（建议）

1. M1（稳定可用）：连续 2 周无阻断级故障，关键流程成功率 >= 95%。
2. M2（小范围上线）：支持多用户协作，核心任务平均耗时下降 20% 以上。
3. M3（规模化推广）：形成可观测、可扩展、可治理的平台化交付能力。
