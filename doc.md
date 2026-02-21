# Deep Research 实现级技术说明

> 更新时间：2026-02-21（按仓库当前实现整理）

---

## 1. 项目定位

本项目是一个本地单用户的“研究会话 + 任务执行引擎”系统，核心目标是：
- 用会话驱动研究任务；
- 让用户可编辑计划、可查看进度、可改写最终报告；
- 把检索、分析、写作串成可复跑的流水线。

当前实现重点是端到端闭环，非生产多租户平台。

### 1.1 这个项目能做什么

从用户视角看，Deep Research 不是单次问答工具，而是一个“可持续推进的研究工作台”。它可以完成以下工作：

1. 把一个研究主题转成可执行计划。  
用户给出主题后，系统会自动生成第一版研究方案（Markdown + front matter），并允许用户继续细化范围、深度、数据源和优先级。

2. 把计划转成实际执行。  
系统会基于计划参数创建任务，自动拆解为节点 DAG，并逐节点检索证据、记录过程、生成快照。

3. 把执行过程透明化。  
研究中的阶段、节点、检索查询、进度百分比、证据条目会实时回流到会话时间线，用户可以看到“现在进行到哪一步、做了什么”。

4. 把证据转成结构化报告。  
系统会汇总证据、做冲突检测、完成报告写作，并落盘为 `.md + .bib`，可直接下载。

5. 把“后续需求”纳入同一会话闭环。  
研究完成后，用户可以继续发指令：改方案、重跑研究、改写报告（如改成演讲稿）。系统会根据意图自动路由到相应流程。

### 1.2 它是怎么做的（高层机制）

项目核心是“会话编排层 + 执行引擎层”的双层结构：

- 会话编排层（`ConversationAgent`）负责“理解用户当前要什么”。  
同样是“请调整一下”这种输入，系统会根据上下文与关键词判断你是在改方案、要重跑，还是只改报告，并选择不同处理路径。

- 执行引擎层（`ExecutionEngine`）负责“把研究做完”。  
引擎按状态机推进任务，从规划、检索、分析到写作逐步执行，并通过事件把过程同步回前端与会话消息。

这意味着系统既有“聊天交互能力”，也有“工程化流水线能力”，两者通过统一数据模型（Task/Conversation/Evidence/Conflict）连接起来。

### 1.3 这个实现的优势

1. 过程可追踪，而不是黑盒回答。  
用户可以看到计划版本、运行轮次、进度分组、证据清单、冲突记录，便于复盘和迭代。

2. 支持多轮研究，而不是一次性输出。  
会话与任务解耦：同一个 `conversation_id` 可以对应多次 `task_id` 运行，适合“先做一版，再补证据再重跑”的真实研究节奏。

3. 结果可交付，而不仅是聊天记录。  
最终产物是本地文件（Markdown + BibTeX），可进入论文草稿、内部报告、知识库或二次编辑流程。

4. 对外部依赖有降级策略。  
在模型或网络不可用时，系统仍可用 fallback 计划/报告逻辑保持主流程可运行；测试场景可用 mock 模式保证稳定复现。

5. 结构清晰，便于二次开发。  
路由、仓储、服务、代理职责分明；前后端接口边界明确，适合继续扩展 provider、MCP 工具、并发调度和权限体系。

### 1.4 核心特性清单

- 会话驱动研究：会话状态与消息历史完整保存。  
- 计划版本化：每次修订产生 `PlanRevision`，可追溯。  
- 任务可控：支持 `start/pause/resume/abort/recover`。  
- 实时进度：WebSocket + 会话内进度分组聚合。  
- 检索可配置：支持 `searchSources`，按 provider 并发采集。  
- 证据治理：证据清洗、去重、打分、冲突检测与投票。  
- 报告多形态：研究报告/论文/演讲稿等体裁蓝图。  
- 质量闸门：报告审查与修订循环，降低占位内容与过程噪音。  
- 本地优先：SQLite 持久化 + 本地文件产物，部署成本低。  

### 1.5 典型使用场景

- 研发团队做技术路线调研：先快速跑一版，再补充新证据重跑。  
- 产品/战略团队做专题分析：输出结构化报告并保留可追溯证据链。  
- 内容团队做格式改写：研究完成后直接改成演讲稿、摘要版或简报文稿。  
- 教学/实验环境：通过 mock 模式稳定演示完整流程与系统行为。

---

## 2. 总体架构

```text
Frontend (React/Vite)
  ├─ ConversationSidebar      会话列表/新建/重命名/删除
  ├─ ChatTimeline             消息流/进度组/报告预览
  ├─ Composer                 指令输入
  └─ PlanEditorPane           方案编辑与启动

Backend (FastAPI)
  ├─ API Routes               /tasks /conversations /evidence /mcp
  ├─ ConversationAgent        会话编排与指令路由
  ├─ ExecutionEngine          任务执行主循环
  ├─ Services                 planner/retrieval/analyst/writer/agents
  ├─ Repositories             SQLite 持久化读写
  └─ ProgressHub              WebSocket 进度推送

Storage
  ├─ SQLite (backend/.data/deep_research.db)
  └─ Reports (.md/.bib, backend/.data/reports)
```

---

## 3. 后端实现细节

## 3.1 应用入口与配置

### `backend/app/main.py`
- FastAPI 生命周期里调用 `init_db()` 初始化数据库 schema。
- CORS 允许 `localhost/127.0.0.1` 任意端口。
- 注册统一路由 `api_router`。
- 健康检查接口：`GET /healthz`。

### `backend/app/core/config.py`
配置由 `pydantic-settings` 驱动：
- `.env` + 前缀 `DR_`
- 关键项：
  - `use_mock_sources`
  - `default_llm_provider` / `default_llm_model`
  - `db_path`
  - 各模型和检索服务 key/base_url/model

### `backend/app/core/utils.py`
- `now_iso()`：UTC，去微秒 ISO 时间。
- `new_id()`：UUID4 字符串。

---

## 3.2 数据模型（Pydantic）

定义文件：`backend/app/models/schemas.py`。

### 任务相关
- `TaskStatus`: `READY -> ... -> COMPLETED/FAILED/ABORTED`
- `NodeStatus`: `PENDING/RUNNING/COMPLETED/FAILED/SUSPENDED/PRUNED`
- `TaskConfig`: `maxDepth/maxNodes/searchSources/priority`
- `TaskNode`, `DAGGraph`, `DAGEdge`
- `TaskResponse`, `StateResponse`

### 会话相关
- `ConversationStatus`: `DRAFTING_PLAN/PLAN_READY/RUNNING/COMPLETED/FAILED`
- `MessageRole`, `MessageKind`
- `PlanRevision`, `ConversationMessage`
- `ConversationSummary`, `ConversationDetail`

### 证据与冲突
- `Evidence`, `EvidenceMetadata`, `ExtractedData`
- `ConflictRecord`, `DisputedValue`, `ResolutionStatus`
- `VoteRequest`, `VoteResponse`

### MCP
- `MCPExecutionRequest` (`mode`: read/write/execute)
- `MCPExecutionResult`

---

## 3.3 数据库层

### `backend/app/core/database.py`
SQLite schema（WAL）包含表：
- `tasks`
- `task_nodes`
- `snapshots`
- `evidences`
- `conflicts`
- `conversations`
- `plan_revisions`
- `conversation_messages`

索引：
- `idx_conversations_task_id`
- `idx_conversation_messages_created_at`

### Repository 职责

#### `TaskRepository`
- CRUD：任务主表
- DAG 持久化：`save_dag/get_dag`
- 节点状态更新：`update_node_status`
- 快照：`save_snapshot/load_snapshot`
- 报告路径：`set_report_path`

#### `EvidenceRepository`
- `save_many/get/list`
- 过滤参数：`taskId/nodeId/limit`

#### `ConflictRepository`
- `save_many/get/list_by_task/resolve`
- `resolve` 将状态置为 `RESOLVED` 并记录 `resolution_json`

#### `ConversationRepository`
- 会话摘要：创建、查询、更新 topic/status/task_id、删除
- 方案版本：`add_plan_revision/get_current_plan`
- 消息历史：`add_message/list_messages`
- 进度聚合：`append_progress_entry`
  - 同会话、同 `taskId`、同 `phase` 会复用已有 `PROGRESS_GROUP` 消息
  - 每组最多保留最近 50 条 entry

---

## 3.4 API 路由

### 路由聚合
`backend/app/api/router.py` 包含四个路由文件：
- `tasks.py`
- `evidence.py`
- `mcp.py`
- `conversations.py`

### 任务路由（`tasks.py`）
- 任务管理：创建/查询/更新/删除/取 DAG
- 状态控制：`start/pause/resume/abort/recover`
- 辅助读取：`/conflicts` `/report` `/report/download` `/snapshot`
- WebSocket：`/ws/task/{task_id}/progress`

### 会话路由（`conversations.py`）
- 创建、查询、重命名、删除（单个/全部）
- 计划修订：`/plan/revise`、`/plan`（PUT）
- 执行：`/run`
- 报告下载：`/report/download`

### 证据路由（`evidence.py`）
- 列表与详情
- 冲突投票：`/evidence/{evidence_id}/vote`

### MCP 路由（`mcp.py`）
- 统一执行入口：`/mcp/execute`

---

## 3.5 服务层（核心行为）

## 3.5.1 状态机
`backend/app/services/state_machine.py`
- 定义 `ALLOWED_TRANSITIONS`
- `transition_or_raise(current, target)` 非法迁移直接抛错

## 3.5.2 规划器
`backend/app/services/planner.py` `MasterPlanner.build_dag(...)`
- 生成根节点 + BFS 扩展
- depth=0 固定首层主题：`背景研究/现状分析/挑战识别`
- 后续层主题：`{父标题} - 深入方向`
- 基于 `_estimate_info_gain` 做简化剪枝（低增益可标 `PRUNED`）
- 受 `maxDepth/maxNodes` 硬约束

## 3.5.3 检索服务
`backend/app/services/retrieval.py`

### L1 缓存
- `L1EvidenceCache`：
  - LRU（`OrderedDict`）
  - 默认大小 1000
  - TTL 3600s

### 查询扩展
- `expand_query(query)` -> `(<term...>) AND (year OR year-1 OR year-2)`

### 模式分支
- `DR_USE_MOCK_SOURCES=true`：`_mock_retrieve` 返回合成证据
- 否则：`_real_retrieve`

### 真实检索源
- Tavily（有 key 才调用）
- arXiv（可直接调用）
- Semantic Scholar（可直接调用）

并行策略：
- 为 provider 建立 `asyncio.create_task` 并聚合结果
- 单个 provider 错误不会中断总流程（`_safe_provider_call`）

### 清洗与过滤
- `_validate_evidences` 过滤：
  - URL 为空/协议非 http(s)
  - placeholder host（如 `example.org`）
  - 内容过短（<30 字符）
- `_dedupe_by_url` URL 去重

## 3.5.4 分析服务
`backend/app/services/analyst.py`
- `score(evidence)`：
  - source 权重（PAPER 1.0 / PATENT 0.8 / WEB 0.5 / MCP 0.9）
  - 影响因子增益
  - peer-review 增益
  - 时间衰减（<=2016 降到 0.5，<=2021 为 0.8）
- `detect_conflicts(...)`：
  - 从 `extractedData.numericalValues` 建桶
  - 单位归一化（km/cm/gb/mb）
  - 方差阈值默认 0.15，超过即生成 `ConflictRecord`

## 3.5.5 写作服务
`backend/app/services/writer.py`

`WriterService.write_report(...)` 输出：
- Markdown：`backend/.data/reports/{task_id}.md`
- BibTeX：`backend/.data/reports/{task_id}.bib`
- 引文映射：`dict[evidence_id, Citation]`

内容生成路径：
1. 通过 `ReportBlueprint` 确定结构。
2. `_generate_body`：
   - mock 模式：直接模板体
   - real 模式：先尝试 LLM，再拼接证据模板
3. 去除正文内 URL（URL 放文末证据附录）。
4. 追加 `## 证据说明与来源链接` 与 `## References`。

标题处理：
- 过滤 placeholder 标题（如 `[MOCK]` / `result for`）并回退到内容摘要。

## 3.5.6 Agent 组合层
`backend/app/services/agents.py`

### `ResearchAgent`
- 封装检索
- 可挂 MCP read 工具（目前为占位调用）

### `ReportAgent`
报告生成管线：
1. `ReportFormatAgent.design_blueprint` 推断体裁与章节。
2. `WriterService.generate_body` 生成初稿。
3. `ReportReviewAgent.review` 质量审查：
   - 检测 trace 泄漏
   - 检测 placeholder 文本
   - 检查章节完整性/段落深度/证据引用
4. 若不通过，`ReportRevisionAgent.revise` 清洗或模板重写。
5. 最终 `WriterService.write_report` 落盘。

### `ReportFormatAgent`
- 关键词识别：演讲稿/论文/研究报告/自定义格式
- 输出对应 `section_titles`

### `ReportReviewAgent`
- 审核规则包括：
  - 章节缺失
  - 内容过短
  - 段落层次不足
  - 证据 ID 引用不足

### `ReportRevisionAgent`
- 清理 trace/噪音行
- 必要时回退模板全文重写

## 3.5.7 MCP 执行器
`backend/app/services/mcp_executor.py`
- `mode in {write, execute}` -> 返回 `USER_CONFIRMATION_REQUIRED`
- `mode=read` -> 模拟 JSON-RPC 成功返回

## 3.5.8 进度中心
`backend/app/services/progress_hub.py`
- task_id 维度保存 WebSocket 连接集合
- `emit` 广播 `ProgressEvent`
- 发送失败连接自动剔除

## 3.5.9 重试工具
`backend/app/services/retry.py`
- `retry_async(fn, max_attempts, base_delay_seconds)`
- 指数退避（`2**attempt`）
- 最终抛 `RetryableError`

---

## 3.6 执行引擎（关键主链路）

文件：`backend/app/services/execution_engine.py`

### 核心对象
- `TaskControlState`：`paused/aborted/running_task/completed_nodes`
- `ExecutionEngine`：系统执行主协调器

### `_run_task` 阶段

1. **TASK_STARTED**
   - 发出 `TASK_STARTED` 事件

2. **规划**
   - 若任务无 DAG，状态迁移 `READY->PLANNING`
   - 调 `MasterPlanner.build_dag`
   - 落库后推送 `TASK_PROGRESS (BUILDING_PLAN, 20%)`

3. **执行节点**
   - 状态迁移到 `EXECUTING`
   - 跳过 root 与 `PRUNED` 节点
   - 对每个节点：
     - 可暂停轮询 (`paused`)
     - 可终止 (`aborted`)
     - 节点置 `RUNNING`
     - `ResearchAgent.collect_evidence`
     - 证据入库
     - 推送 `EVIDENCE_FOUND`
     - 节点置 `COMPLETED`
     - 写快照（包含已完成节点与缓存摘要）

4. **审查冲突**
   - 对所有证据重算 score
   - `AnalystService.detect_conflicts`
   - 有冲突：`EXECUTING->REVIEWING`，存冲突后继续 `REVIEWING->SYNTHESIZING`
   - 无冲突：`EXECUTING->SYNTHESIZING`

5. **写作与落盘**
   - 推送 `OUTLINING/WRITING_SECTION`
   - `ReportAgent.generate_report` 生成 `.md/.bib`
   - `SYNTHESIZING->FINALIZING->COMPLETED`
   - 发 `TASK_COMPLETED`（含 reportPath/bibPath）

6. **异常处理**
   - 状态置 `FAILED`
   - 推送 `ERROR`

---

## 3.7 会话编排（ConversationAgent）

文件：`backend/app/services/conversation_agent.py`

这是后端“对话行为”的核心。

### `create_conversation`
- 新建会话（`DRAFTING_PLAN`）
- 写入首条用户消息
- 调 `_generate_initial_plan`（LLM 或 fallback）
- 存 `PLAN_DRAFT` 消息
- 状态转 `PLAN_READY`

### `revise_plan`
会先根据“是否已有报告 + 指令关键词”判定模式：
- `PLAN`：修订研究方案
- `RESEARCH`：先修订方案，再立即触发新一轮研究
- `REPORT`：进入报告改写异步任务

关键关键词集合：
- 方案意图：`研究方案/任务树/max_depth/...`
- 重跑意图：`重跑/补充检索/更新最新/...`
- 报告意图：`改写报告/演讲稿/rewrite/style/...`

### 报告改写链路
- `_start_report_revision` 先写“正在修改中”消息并置 `RUNNING`
- 后台 `asyncio.create_task(_run_report_revision_job)`
- 进度通过 `append_progress_entry` 写入 `PROGRESS_GROUP`
- 优先路径：
  1. 读取当前报告
  2. LLM 改写 `_rewrite_report_with_llm`
  3. 需要时触发“基于既有证据重建报告”
  4. 回写报告文件
  5. 追加 `FINAL_REPORT` 消息

### `start_research`
- 检查当前计划存在
- 解析 front matter（`title/max_depth/max_nodes/priority/search_sources`）
- 总是新建 `task_id`
- 会话绑定新 task，状态置 `RUNNING`
- 调 `execution_engine.start(task_id)`

### `on_task_event`
监听执行引擎事件并投递到会话消息：
- `TASK_PROGRESS` -> 聚合为 `PROGRESS_GROUP`
- `TASK_COMPLETED` -> 会话置 `COMPLETED`，注入 `FINAL_REPORT`
- `ERROR/TASK_FAILED/TASK_ABORTED` -> 会话置 `FAILED`，注入错误消息

### 计划 front matter 解析
- `_parse_plan`：从 YAML 头读取配置
- 解析失败会产生 warning，并回退默认配置
- `_ensure_front_matter`：保证计划文本总有 front matter

---

## 3.8 依赖装配

文件：`backend/app/deps.py`

在模块加载时单例化：
- repositories
- services
- agents
- execution_engine
- conversation_agent

并调用：
- `execution_engine.set_event_listener(conversation_agent.on_task_event)`

即执行事件天然回流到会话时间线。

---

## 4. 前端实现细节

## 4.1 启动与构建

- 入口：`frontend/src/main.tsx`
- Vite 端口：`5174`（`frontend/vite.config.ts`）

---

## 4.2 API 客户端

文件：`frontend/src/api.ts`

特点：
- 统一 `json()` 包装，带超时和错误提取。
- 支持普通超时和计划接口长超时（`PLAN_API_TIMEOUT_MS` 默认 120s）。
- 统一下载方法（Blob + `<a download>`）。
- WebSocket 连接带 15s 心跳 ping。

---

## 4.3 `App.tsx` 主状态机

核心状态：
- 会话：`summaries/activeConversationId/activeDetail`
- 草稿：`planDraft/planVersion/draftDirty/editorMode`
- 发送控制：`sending/saving/starting/downloading`
- UI 控制：左右侧栏显示、移动端抽屉、确认弹窗、重命名弹窗

关键行为：
- 首次加载自动拉会话列表。
- 活跃会话在 `RUNNING/DRAFTING_PLAN` 时轮询刷新（默认 2.5s）。
- 创建草稿模式后，第一条消息作为“研究主题”。
- 发送指令后做 optimistic UI（先插入临时 user 消息）。
- 删除/重命名/全部删除都通过自定义 `Dialog`。

---

## 4.4 组件职责

### `ConversationSidebar`
- 展示会话列表与状态 chip
- 单会话菜单：重命名 / 删除
- 全局菜单：全部删除

### `ChatTimeline`
- 渲染用户/Agent/System 消息
- 方案消息可一键应用到右侧编辑器
- `PROGRESS_GROUP` 聚合展示并可折叠
- 报告消息使用 `ReportViewer`
- 支持隐藏历史轮次（只看当前 task）

### `PlanEditorPane`
- Markdown 编辑/预览
- 保存草稿
- 启动研究（状态允许时）
- 下载报告（`COMPLETED` 时）

### `Composer`
- Enter 发送，Shift+Enter 换行
- 根据会话状态动态禁用

### `Dialog`
- Esc、遮罩点击关闭（可禁用）
- 聚焦管理

### `ReportViewer`
- 报告展开/收起/下载

---

## 4.5 样式系统

文件：`frontend/src/styles.css`

实现特征：
- 三栏布局 + 渐变背景 + 玻璃拟态卡片。
- 桌面端侧栏可折叠（left/right hidden）。
- 移动端（<=1120px）左右抽屉 + 遮罩，且防背景滚动。
- 进度/打字动画提供 `prefers-reduced-motion` 降级。

---

## 5. 运行脚本

### `scripts/run_backend.sh`
- 创建/激活虚拟环境
- 安装后端依赖
- 启动 uvicorn

### `scripts/run_frontend.sh`
- `npm install`
- `npm run dev`

### `scripts/run_real_case.py`
- 使用 `TestClient` 在进程内跑真实案例
- 创建任务 -> 启动 -> 轮询 -> 输出 evidence 总数和报告前 30 行

---

## 6. 测试覆盖（按当前用例）

## 集成测试
- `test_task_lifecycle.py`
  - 任务创建/启动/完成/快照恢复
  - evidence/conflict/mcp 接口可用性
- `test_conversation_lifecycle.py`
  - 会话创建、重命名、改计划、运行、下载、重跑、批量删除

## 单元测试
- `test_planner.py`：DAG 边界与无反向环
- `test_state_machine.py`：状态迁移合法性
- `test_retrieval.py`：查询扩展形状
- `test_analyst.py`：冲突检测
- `test_writer.py`：报告与 Bib 生成、标题清洗
- `test_report_format_agent.py`：体裁识别
- `test_report_review_agent.py`：审稿规则、修订循环
- `test_conversation_repository.py`：进度分组复用/隔离
- `test_conversation_agent.py`：front matter、报告改写、重跑、事件聚合、删除中断

`tests/conftest.py` 默认设置：`DR_USE_MOCK_SOURCES=true`，保证测试可重复。

---

## 7. 配置与环境变量总表

后端主要读取（`DR_` 前缀）：
- 应用：`APP_NAME/API_PREFIX/DB_PATH/LOG_LEVEL`
- 模式：`USE_MOCK_SOURCES`
- 模型路由：`DEFAULT_LLM_PROVIDER/DEFAULT_LLM_MODEL`
- Provider：`OPENROUTER_* / DEEPSEEK_* / OPENAI_* / ANTHROPIC_*`
- Search：`SERPER_API_KEY / SERPAPI_API_KEY / TAVILY_API_KEY / ...`

前端主要读取：
- `VITE_API_BASE`（默认 `http://127.0.0.1:8000`）
- `VITE_API_TIMEOUT_MS`
- `VITE_PLAN_API_TIMEOUT_MS`
- `VITE_CONVERSATION_REFRESH_MS`

---

## 8. 当前已知边界与后续扩展位

- 无鉴权、无租户隔离、无权限体系。
- `MCPExecutor` 仅最小占位，未对接真实 tool registry。
- 执行引擎当前单任务内部串行节点处理。
- 检索源可扩展，但目前只实现 Tavily/arXiv/S2。
- 意图路由依赖关键词规则，可替换为分类模型。

---

## 9. 建议阅读顺序（源码）

1. `backend/app/services/conversation_agent.py`
2. `backend/app/services/execution_engine.py`
3. `backend/app/services/agents.py`
4. `backend/app/services/retrieval.py`
5. `backend/app/services/writer.py`
6. `backend/app/repositories/*.py`
7. `frontend/src/App.tsx`
8. `frontend/src/components/ChatTimeline.tsx`
9. `tests/integration/*.py`

---

如果你要继续扩展，请先看 `WORKFLOW.md`（端到端时序）再改代码。
