# Deep Research 运行流程手册（代码对齐版）

> 文档目的：把“系统实际如何运行”写成可操作流程，覆盖主流程、分支、异常和恢复。

---

## 1. 角色与核心对象

- 用户：在前端发起主题、修订计划、触发执行、改写报告。
- 前端：三栏工作台（会话、时间线、计划编辑器）。
- 会话编排器：`ConversationAgent`。
- 执行引擎：`ExecutionEngine`。
- 数据层：SQLite + 报告文件。

核心 ID：
- `conversation_id`：会话维度。
- `task_id`：每次运行生成的新任务维度。
- `message_id`：时间线消息维度。
- `evidence_id`：证据维度。

---

## 2. 状态机

## 2.1 会话状态（ConversationStatus）

- `DRAFTING_PLAN`
- `PLAN_READY`
- `RUNNING`
- `COMPLETED`
- `FAILED`

## 2.2 任务状态（TaskStatus）

- `READY`
- `PLANNING`
- `EXECUTING`
- `REVIEWING`
- `SYNTHESIZING`
- `FINALIZING`
- `COMPLETED`
- `FAILED`
- `SUSPENDED`
- `ABORTED`

迁移规则由 `state_machine.py` 的 `ALLOWED_TRANSITIONS` 严格控制。

---

## 3. 主流程 A：新建会话并完成研究

## 3.1 创建会话

### 用户动作
在“新建研究”后发送第一条主题消息。

### 前端调用
`POST /api/v1/conversations`

### 后端行为（`ConversationAgent.create_conversation`）
1. 新建会话，状态 `DRAFTING_PLAN`。
2. 写入首条用户消息 `USER_TEXT`。
3. 生成首版计划（LLM 或 fallback）。
4. 写入 `PLAN_DRAFT` 消息。
5. 状态切到 `PLAN_READY`。

### 前端表现
- 中间时间线出现首版计划。
- 右侧计划编辑器自动填充 Markdown。

---

## 3.2 用户修订计划（可选）

### 方式 1：右侧编辑器直接改
- 前端调用：`PUT /api/v1/conversations/{id}/plan`
- 后端写入新 `PlanRevision` + `PLAN_EDITED` 消息。

### 方式 2：聊天输入自然语言“改方案”
- 前端调用：`POST /api/v1/conversations/{id}/plan/revise`
- 后端按指令生成新版本并追加 `PLAN_REVISION` 消息。

---

## 3.3 启动研究

### 用户动作
点击“开始研究”或在时间线点“继续执行”。

### 前端调用
`POST /api/v1/conversations/{id}/run`

### 后端行为（`ConversationAgent.start_research`）
1. 读取当前计划，解析 front matter：
   - `title`
   - `max_depth`
   - `max_nodes`
   - `priority`
   - `search_sources`
2. 使用解析结果创建**新任务**（每次 run 都是新 task_id）。
3. 会话绑定 task_id，状态置 `RUNNING`。
4. 写一条系统消息“研究任务已启动”。
5. 调 `execution_engine.start(task_id)`。

---

## 3.4 执行引擎流水线

`ExecutionEngine._run_task` 时序如下：

1. 推送 `TASK_STARTED`。
2. 若 DAG 为空：
   - `READY -> PLANNING`
   - `MasterPlanner.build_dag`
   - `save_dag`
   - 推送 `TASK_PROGRESS(phase=BUILDING_PLAN, progress=20)`
3. 迁移到 `EXECUTING`。
4. 遍历可执行节点（非 root 且非 PRUNED）：
   - 节点置 `RUNNING`
   - 生成 query（`task.title + node.title`）
   - 推送 `TASK_PROGRESS(SEARCHING)`
   - `ResearchAgent.collect_evidence`
   - `EvidenceRepository.save_many`
   - 对每条证据推送 `EVIDENCE_FOUND`
   - 节点置 `COMPLETED`
   - 推送 `TASK_PROGRESS(NODE_COMPLETED)`
   - 保存 snapshot
5. 节点完成后进行分析：
   - 对证据计算 score
   - 检测冲突（阈值默认 0.15）
   - 有冲突：`EXECUTING -> REVIEWING -> SYNTHESIZING`
   - 无冲突：`EXECUTING -> SYNTHESIZING`
6. 写作阶段：
   - 推送 `OUTLINING`
   - 逐 section 推送 `WRITING_SECTION`
   - `ReportAgent.generate_report` 输出 `.md/.bib`
7. 收尾：
   - `SYNTHESIZING -> FINALIZING -> COMPLETED`
   - 写 `report_path`
   - 推送 `TASK_COMPLETED(progress=100)`

---

## 3.5 事件回流会话

执行引擎事件通过 listener 回到 `ConversationAgent.on_task_event`：

- `TASK_PROGRESS`
  - 进入 `ConversationRepository.append_progress_entry`
  - 聚合为 `PROGRESS_GROUP` 消息
- `TASK_COMPLETED`
  - 会话状态置 `COMPLETED`
  - 读取报告文件，追加 `FINAL_REPORT` 消息
- `ERROR/TASK_FAILED/TASK_ABORTED`
  - 会话状态置 `FAILED`
  - 追加 `ERROR` 消息

前端时间线会自动显示这些消息。

---

## 4. 主流程 B：已完成后继续提要求

`POST /plan/revise` 在“已有报告”场景会做意图分流。

## 4.1 PLAN 模式（继续改计划）
触发词示例：`研究方案 / max_depth / 任务树 / 执行步骤`。

行为：
- 新增 `PlanRevision`
- 状态保持/回到 `PLAN_READY`

## 4.2 RESEARCH 模式（补检索并重跑）
触发词示例：`重跑 / 补充检索 / 再搜索 / 查询最新`。

行为：
1. 先修订计划。
2. 立即调用 `start_research`。
3. 新建 task_id 并进入 RUNNING。

## 4.3 REPORT 模式（只改报告，不重检索）
触发词示例：`改写报告 / 演讲稿 / 改风格 / rewrite`。

行为：
1. 会话状态置 `RUNNING`。
2. 写一条“正在修改中”系统消息。
3. 异步执行报告改写任务：
   - 优先基于现有报告做 LLM 改写
   - 若指令包含“从证据重写/全量重写”等标记，可触发证据重建
4. 追加新的 `FINAL_REPORT`。
5. 会话回 `COMPLETED`。

---

## 5. 前端视角流程

## 5.1 页面启动
- `listConversations()` 拉侧栏。
- 若有会话自动选第一条。

## 5.2 轮询策略
当 active 会话状态为：
- `RUNNING`
- `DRAFTING_PLAN`

前端按 `VITE_CONVERSATION_REFRESH_MS`（默认 2500ms）轮询：
- `GET /conversations/{id}`
- `GET /conversations`

## 5.3 时间线渲染规则
- `PLAN_*` 消息：代码块 + “打开草稿抽屉”。
- `PROGRESS_GROUP`：可折叠，显示 phase/state/progress 明细。
- `FINAL_REPORT`：支持全宽、收起、下载。
- `ERROR`：红色文本。

## 5.4 历史轮次
同一会话多次运行会产生多个 task_id。
时间线支持：
- 展示全部历史轮次
- 仅显示当前轮次（按消息中的 taskId 过滤）

---

## 6. 检索与证据流

## 6.1 查询生成
`RetrievalService.expand_query` 统一附加近 3 年窗口。

## 6.2 Provider 选择
输入 `searchSources` 会做归一化：
- `arxiv` / `arxivorg` -> `arxiv`
- `semanticscholar` / `s2` -> `semanticscholar`
- `tavily` -> `tavily`

## 6.3 并发调用
每个 provider 独立 task，失败只影响自己，不影响总流程。

## 6.4 质量过滤
证据写库前会过滤掉：
- 非 http(s)
- placeholder host
- 内容太短

---

## 7. 冲突与投票流程

1. 引擎进入分析阶段，生成 `ConflictRecord[]`（可为空）。
2. 前端可调用：
   - `GET /api/v1/tasks/{task_id}/conflicts`
3. 用户投票：
   - `POST /api/v1/evidence/{evidence_id}/vote`
   - body: `conflictId + selectedEvidenceId + reason`
4. `ConflictRepository.resolve` 更新为 `RESOLVED`。

---

## 8. 暂停/恢复/终止/恢复快照

## 8.1 暂停
`POST /tasks/{id}/pause`
- `control.paused = true`
- 任务状态置 `SUSPENDED`

## 8.2 恢复
`POST /tasks/{id}/resume`
- 清 `paused`
- 重新调用 `start()`

## 8.3 终止
`POST /tasks/{id}/abort`
- `control.aborted = true`
- 状态置 `ABORTED`

## 8.4 快照恢复
`POST /tasks/{id}/recover`
- 读取 snapshot 的 `completed_nodes`
- 从剩余节点继续执行

---

## 9. 报告生成与下载

## 9.1 报告文件
输出目录：`backend/.data/reports/`
- `{task_id}.md`
- `{task_id}.bib`

## 9.2 下载接口
- 任务下载：`GET /tasks/{task_id}/report/download`
- 会话下载：`GET /conversations/{conversation_id}/report/download`

前端通过 Blob 触发浏览器下载。

---

## 10. API 调用顺序示例

## 10.1 从 0 到 1 完整跑通

1. `POST /conversations`
2. `GET /conversations/{id}`（前端轮询）
3. `PUT /conversations/{id}/plan`（可选）
4. `POST /conversations/{id}/run`
5. `GET /conversations/{id}`（轮询直到 COMPLETED）
6. `GET /conversations/{id}/report/download`

## 10.2 已完成后补检索重跑

1. `POST /conversations/{id}/plan/revise`（指令含“补充检索/重跑”）
2. 后端自动触发新任务运行
3. 前端轮询 `GET /conversations/{id}` 直到完成

## 10.3 已完成后改写报告

1. `POST /conversations/{id}/plan/revise`（指令含“改写报告/演讲稿”）
2. 后端异步报告改写
3. 时间线出现报告改写进度组
4. 完成后追加新 `FINAL_REPORT`

---

## 11. 错误分支与降级策略

- LLM 不可用：
  - 计划生成回退 `_fallback_plan`
  - 报告改写回退 `_fallback_revised_report`
- 检索 provider 失败：
  - 单 provider 警告，其他 provider 继续
- 状态迁移非法：
  - 抛 `InvalidStateTransition`
  - 任务置 `FAILED`
- 前端请求超时：
  - API 层给出统一中文超时提示

---

## 12. 调试建议

1. 后端日志看 `ExecutionEngine` 阶段事件是否完整。
2. 查 `conversation_messages` 中 `PROGRESS_GROUP` 的 `metadata.entries` 是否连续。
3. 报告异常优先检查：
   - `tasks.report_path`
   - `backend/.data/reports/*.md`
4. 若计划解析不符合预期，检查 front matter 字段名是否严格使用：
   - `title/topic/max_depth/max_nodes/priority/search_sources`

---

## 13. 回归检查最小清单

1. 创建会话 -> 生成计划 -> 启动研究 -> 完成 -> 下载报告。
2. 完成后发送“改成演讲稿”，确认追加新 `FINAL_REPORT`。
3. 完成后发送“补充检索并重跑”，确认 task_id 变化。
4. 删除单会话和删除全部会话均可用，运行中任务会被中断。
5. 移动端抽屉开关、对话框 Esc/遮罩关闭、Enter 发送均正常。

---

如需继续扩展，请先读 `doc.md` 的模块说明，再根据本手册挑选插点。
