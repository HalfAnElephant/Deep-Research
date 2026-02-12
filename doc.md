# **Deep Research 深度科研辅助系统总体设计规格说明书**

## **1. 系统综述与核心架构**

### **1.1 设计主旨**

本系统之构建，旨在矫正传统科研检索工具所固有之"黑箱化"运作模式及"浅层化"信息处理弊端。其核心技术差异性体现于以下三点：

* **白盒推理机制 (White-box Reasoning)**：系统推理逻辑需完全透明化，允许操作端实时监视并干预任务规划思维链（CoT）。
* **实验生态闭环 (Experimental Loop)**：藉由 MCP 协议突破纯文本处理之局限，实现本地数据与计算工具的连接与调用。
* **语义对齐校验 (Semantic Alignment)**：引入严谨的数值冲突检测算法与语义数值对齐（SNA）机制，以确保数据的一致性。

### **1.2 总体架构图 (System Architecture)**

本系统架构采行分层设计原则，以确立推理逻辑、信息检索与任务执行之解耦。

```
┌─────────────────────────────────────────────────────────────────┐
│                        交互层 (Interaction Layer)                │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────────┐  │
│  │ CoT 编辑器   │ │ 实时证据看板  │ │ Markdown 分屏预览        │  │
│  └─────────────┘ └──────────────┘ └──────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                       编排层 (Orchestration Layer)               │
│  ┌─────────────────────────┐ ┌──────────────────────────────┐   │
│  │  主规划器 (Master Planner)│ │   状态管理器 (State Manager) │   │
│  │  - DAG 任务图谱管理       │ │   - FSM 状态机              │   │
│  │  - 动态任务调度           │ │   - 上下文快照              │   │
│  └─────────────────────────┘ └──────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                         代理层 (Agent Layer)                     │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐   │
│  │ 检索代理   │ │ 分析代理   │ │MCP执行代理 │ │  写作代理     │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                      基础设施层 (Infrastructure)                  │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────────┐   │
│  │ 向量数据库   │ │ MCP 服务器集群 │ │   本地文件系统接口       │   │
│  │ (L2 缓存)   │ │             │ │                          │   │
│  └─────────────┘ └─────────────┘ └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

* **交互层 (Interaction Layer)**：涵盖思维链（CoT）编辑器、实时证据流监控看板及 Markdown 分屏预览界面。
* **编排层 (Orchestration Layer)**：
  * **主规划器 (Master Planner)**：负责动态有向无环图（DAG）任务图谱的管理与调度。
  * **状态管理器 (State Manager)**：维护全局有限状态机与上下文快照。
* **代理层 (Agent Layer)**：
  * 检索代理 (Retrieval Agent)：执行全域信息的捕获。
  * 分析代理 (Analyst Agent)：执行数据质量控制与审查。
  * MCP 执行代理 (MCP Executor)：执行外部工具调用。
  * 写作代理 (Writer Agent)：执行知识的结构化合成。
* **基础设施层 (Infrastructure)**：集成向量数据库（L2 缓存）、MCP 服务器集群及本地文件系统接口。

---

## **2. 技术选型与依赖**

### **2.1 核心技术栈**

| 模块 | 技术选型 | 版本要求 | 说明 |
|------|----------|----------|------|
| 后端框架 | Python / FastAPI | ≥3.11, ≥0.104 | 异步支持，自动 API 文档 |
| LLM 接口 | OpenAI API / Anthropic API | - | GPT-4 / Claude Opus |
| 向量数据库 | Qdrant | ≥1.7 | 支持本地部署，高性能相似度搜索 |
| 文档解析 | Readability /trafilatura | ≥1.12 | 网页正文提取 |
| 状态管理 | Redis | ≥7.0 | FSM 状态持久化 |
| 任务队列 | Celery + Redis | ≥5.3 | DAG 任务调度 |
| 前端框架 | React + TypeScript | ≥18 | 交互界面开发 |
| 构建工具 | Vite | ≥5.0 | 快速开发构建 |

### **2.2 外部依赖服务**

| 服务 | 用途 | API 文档 |
|------|------|----------|
| Serper / Google Search | 网页检索 | https://serper.dev/api |
| arXiv API | 学术论文检索 | https://arxiv.org/help/api |
| Semantic Scholar | 论文元数据增强 | https://api.semanticscholar.org |
| CrossRef | DOI 解析 | https://www.crossref.org/services/api |

## **3. 核心代理（Agent）技术规范**

### **3.1 首席任务规划代理 (Master Planner Agent)**

该模组之职能在于将抽象的科研目标转化为可执行的有向无环图 (DAG)。

* **任务拆解策略**：
  * **广度优先搜索 (BFS)**：于初始阶段展开首级子课题（涵盖背景、现状及挑战等维度）。
  * **深度优先搜索 (DFS)**：依据检索反馈结果进行垂直领域的深度挖掘。
  * **动态剪枝算法**：实时计算 infoGainScore（信息增益），若连续两个子任务之增益值低于预设阈值（0.2），系统将自动合并或舍弃后续分支。

* **循环检测机制**：利用 DFS 遍历算法维护 VisitedStack，以防止任务执行陷入无限循环。

* **调度算法逻辑**：
  1. 使用优先队列管理待执行任务，维护已访问节点集合防止重复处理
  2. 执行前检查所有依赖任务是否已完成，未完成则跳过
  3. 任务执行时标记状态为 RUNNING，调用对应 Agent 处理
  4. 执行完成后计算信息增益分数，低于阈值（0.2）则标记为 PRUNED
  5. 剪枝通过后标记为 COMPLETED，保存输出结果
  6. 递归激活并处理所有子任务节点

### **3.2 检索代理 (Research & Retrieval Agent)**

该模组负责执行全域信息的捕获，并配置三级缓存机制。

* **检索管线流程**：
  1. **查询扩展 (Query Expansion)**：生成符合 `(Term OR Abbreviation) AND (Year) AND (Action Verb)` 格式之结构化检索式。
  2. **L1/L2 缓存校验**：优先检索本地内存与向量数据库，若相似度阈值 > 0.9，则跳过外部 API 调用。
  3. **API 调用**：执行 Serper 或 arXiv 接口调用。
  4. **网页解析 (WebParse)**：提取正文内容；若检测到 `<table>` 或 `<img>` 标签，需提取其题注（Caption）并分配独立 evidenceId。

* **缓存策略配置**：
  * **L1 内存缓存**：采用 LRU 淘汰策略，最大容量 1000 条，过期时间 1 小时
  * **L2 向量数据库缓存**：使用 Qdrant 存储，集合名称为 evidence_cache，相似度阈值设为 0.9，过期时间 24 小时

### **3.3 分析代理 (Analyst & Critic Agent)**

该模组作为质量控制核心，执行语义数值对齐 (SNA)。

* **冲突检测机制**：
  * **单位标准化**：将异构计量单位统一转换为国际单位制 (SI)。
  * **阈值判定**：当 `(ValueA - ValueB) / Max > 15%` 且环境条件相似时，生成冲突记录 ConflictRecord。

* **信誉评分计算逻辑**：
  * **基础权重**：论文 1.0、专利 0.8、网页 0.5、MCP 数据 0.9
  * **影响因子加成**：以 IF/10 计算，最高加成 1.5 倍
  * **同行评议加成**：经同行评议的来源乘以 1.2 倍
  * **时效性衰减**：发布超过 5 年开始衰减，10 年后降至 0.5 倍
  * **最终评分**：基础权重 × 影响因子加成 × 同行评议加成 × 时效性 × 相关性分数

### **3.4 MCP 执行代理 (MCP Executor Agent)**

该模组用于安全地连接外部工具与数据源。

* **协议实现**：基于 JSON-RPC 2.0 标准。

* **安全沙盒机制**：
  * **只读模式 (Read-Only)**：允许直接执行。
  * **写/执行模式 (Write/Execute)**：强制挂起任务，返回 `USER_CONFIRMATION_REQUIRED` 状态，待 UI 授权后方可执行。

* **异步轮询机制**：针对长耗时任务，返回 `JOB_ID` 并进入轮询模式，每隔 5 秒同步一次状态。

### **3.5 写作代理 (Writer Agent)**

该模组执行增量式文档生成作业。

* **分段加锁机制**：
  * 每个 `# Section` 绑定至特定的 TaskNode。
  * 节点任务完成时，触发局部内容生成。
  * 经人工编辑之段落将被标记为 `LOCKED`，禁止 AI 覆盖。

* **溯源索引**：维护 `UUID -> Citation` 映射表，以自动生成符合规范的参考文献列表。

---

## **4. API 接口规范**

### **4.1 RESTful API 端点**

#### **4.1.1 任务管理**

| 方法 | 端点 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/tasks` | 创建新研究任务 | CreateTaskRequest | TaskNode |
| GET | `/api/v1/tasks/{task_id}` | 获取任务详情 | - | TaskNode |
| PUT | `/api/v1/tasks/{task_id}` | 更新任务配置 | UpdateTaskRequest | TaskNode |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务 | - | DeleteResponse |
| GET | `/api/v1/tasks/{task_id}/dag` | 获取任务 DAG 结构 | - | DAGGraph |

#### **4.1.2 证据管理**

| 方法 | 端点 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/v1/evidence` | 获取证据列表 | QueryParams | Evidence[] |
| GET | `/api/v1/evidence/{evidence_id}` | 获取证据详情 | - | Evidence |
| POST | `/api/v1/evidence/{evidence_id}/vote` | 证据投票（冲突解决） | VoteRequest | VoteResponse |

#### **4.1.3 状态控制**

| 方法 | 端点 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/tasks/{task_id}/start` | 启动任务执行 | - | StateResponse |
| POST | `/api/v1/tasks/{task_id}/pause` | 暂停任务 | - | StateResponse |
| POST | `/api/v1/tasks/{task_id}/resume` | 恢复任务 | - | StateResponse |
| POST | `/api/v1/tasks/{task_id}/abort` | 终止任务 | - | StateResponse |

### **4.2 WebSocket 事件流**

客户端通过订阅 `task/{task_id}/progress` 频道接收实时推送。

服务端推送的事件类型包括：
* **TASK_STARTED**：任务开始执行
* **TASK_PROGRESS**：任务进度更新（包含进度百分比 0-100）
* **EVIDENCE_FOUND**：发现新证据
* **TASK_COMPLETED**：任务完成
* **ERROR**：执行错误

事件数据结构包含时间戳、任务 ID、当前节点、进度值、证据对象或错误信息。

### **4.3 请求/响应示例**

#### **创建任务**

**请求**（POST /api/v1/tasks）：
* title：研究标题
* description：研究描述
* config.maxDepth：最大搜索深度（默认 3）
* config.maxNodes：最大节点数（默认 50）
* config.searchSources：数据源列表（arXiv、Google Scholar、IEEE 等）
* config.priority：优先级（1-5）

**响应**（201 Created）：
* taskId：任务唯一标识符（UUID 格式）
* status：任务状态（READY）
* createdAt：创建时间（ISO8601 格式）
* dag：任务 DAG 结构（包含 nodes 和 edges）

---

## **5. 全流程交互逻辑设计**

交互子系统之运作逻辑，系由 **State-Trigger-Action** 有限状态机驱动。

| 状态 | UI 表现 | 可执行操作 | 系统后端响应 |
| :---- | :---- | :---- | :---- |
| **就绪 (Ready)** | 初始化界面，含多模态输入模块 | 录入议题、上传种子文件、配置偏好 | 预加载常用 MCP 服务列表 |
| **规划 (Planning)** | 展示任务图谱节点 | **[暂停]** 修改节点，**[拖拽]** 调整依赖，**[删除]** 冗余路径 | 规划器拆解任务，生成依赖关系图 |
| **执行 (Executing)** | 进度条显示，实时证据流看板 | **[干预]** 调整检索词，**[优先级]** 提权，**[授权]** 批准 MCP 调用 | 检索/执行代理并行运作，推送 Evidence[] |
| **审查 (Reviewing)** | 冲突节点高亮显示，对比弹窗 | 选择采信源、指令深挖争议点 | 分析代理检测一致性，聚合冲突数据 |
| **合成 (Synthesizing)** | 文档分屏预览，实时高亮 | 查看引用源，指令重写，锁定段落 | 写作代理整合证据，执行增量润色 |
| **归档 (Finalizing)** | 最终报告生成，参考文献列表 | 导出文档，同步 Zotero，启动后续研究 | 生成 .bib 文件，清理临时上下文 |

### **5.1 深度交互细节说明**

* **白盒化编辑**：操作端对任务树之增删改操作，需直接映射为后端图结构的 `UpdateNode` 指令。
* **实时锚定**：点击证据卡片时，需高亮任务树中的对应来源节点及报告中的引用段落。
* **搜索真空处理**：当公网检索无结果时，UI 需提示连接私有数据库或启用 AI 模拟推演。
* **负载预警**：实时显示"认知负荷指数"，建议操作端精简任务分支。

---

## **6. 全局数据结构定义 (Data Schemas)**

本节规定系统核心数据通信标准。

### **6.1 任务节点 (TaskNode)**

* **taskId**：任务唯一标识符（UUID 格式）
* **parentTaskId**：父任务 ID（根节点为 null）
* **title**：任务标题
* **description**：任务描述
* **status**：任务状态（PENDING、RUNNING、COMPLETED、FAILED、SUSPENDED、PRUNED）
* **priority**：优先级（1-5 的整数）
* **dependencies**：依赖任务 ID 列表
* **children**：子任务 ID 列表
* **metadata**：元数据
  * estimatedTokenCost：预计 Token 消耗
  * searchDepth：搜索深度
  * infoGainScore：信息增益分数
  * createdAt/updatedAt：创建/更新时间
* **conflicts**：冲突记录列表
* **output**：输出证据数组

### **6.2 证据片段 (Evidence)**

* **id**：证据唯一标识符（UUID）
* **sourceType**：来源类型（PAPER、WEB、PATENT、MCP）
* **url**：原始链接
* **content**：正文内容（Markdown 格式）
* **metadata**：元数据
  * authors：作者列表
  * publishDate：发布日期（ISO8601）
  * title：标题
  * abstract：摘要
  * impactFactor：影响因子
  * isPeerReviewed：是否经同行评议
  * relevanceScore：相关性评分（0-1）
  * citationCount：引用次数
* **score**：综合信誉评分（0-1）
* **extractedData**：提取数据
  * tables：表格列表（含 caption 和 data）
  * images：图片列表（含 caption 和 url）
  * numericalValues：数值列表（含 value、unit、context）

### **6.3 冲突记录 (ConflictRecord)**

* **conflictId**：冲突记录唯一标识符（UUID）
* **parameter**：发生冲突的参数名称
* **disputedValues**：争议值列表（包含 value、unit、evidenceId、source）
* **variance**：差异程度（百分比）
* **context**：冲突上下文说明
* **resolutionStatus**：解决状态（OPEN、RESOLVED、IGNORED）
* **resolution**：解决方案
  * selectedEvidenceId：采信的证据 ID
  * reason：解决原因
  * resolvedAt：解决时间（ISO8601）

---

## **7. 错误处理与容错机制**

### **7.1 错误分类与处理策略**

| 错误类型 | 示例 | 处理策略 |
|---------|------|----------|
| 网络超时 | API 请求超时 (>30s) | 重试 3 次，指数退避 |
| API 失败 | 429/5xx 响应 | 切换备用 API，记录日志 |
| 解析失败 | 网页内容提取异常 | 标记为低质量，继续处理 |
| DAG 冲突 | 循环依赖检测 | 拒绝提交，返回错误路径 |
| 资源耗尽 | Token 限额超出 | 暂停任务，用户确认后续 |
| MCP 失败 | 外部工具调用失败 | 沙盒隔离，返回部分结果 |

### **7.2 重试机制**

**重试配置参数**：
* 最大重试次数：3 次
* 指数退避基数：2
* 初始延迟：1 秒
* 可重试错误类型：TIMEOUT、CONNECTION_ERROR、RATE_LIMIT_EXCEEDED、SERVICE_UNAVAILABLE

**重试逻辑**：
1. 执行目标函数
2. 若发生可重试错误，按指数退避计算等待时间（1 秒、2 秒、4 秒）
3. 达到最大重试次数后仍未成功则抛出异常
4. 非可重试错误直接抛出

### **7.3 状态恢复机制**

**状态快照包含字段**：
* task_id：任务唯一标识符
* timestamp：快照时间戳
* fsm_state：当前 FSM 状态
* completed_nodes：已完成节点 ID 列表
* pending_nodes：待处理节点 ID 列表
* evidence_cache：证据缓存映射
* conflict_records：冲突记录列表

**恢复逻辑**：
1. 保存检查点：将快照序列化为 JSON 存入 Redis，设置 24 小时过期
2. 加载检查点：从 Redis 读取数据并反序列化为 StateSnapshot 对象
3. 若无检查点数据则返回 null，需从头开始执行

---

## **8. 部署架构**

### **8.1 部署模式**

```
┌─────────────────────────────────────────────────────────────────┐
│                           Nginx / Caddy                         │
│                        (反向代理 + SSL)                          │
├─────────────────────────────────────────────────────────────────┤
│                        Docker Compose 部署                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   FastAPI       │  │   Celery        │  │   Qdrant        │ │
│  │   (API Server)  │  │   (Worker)      │  │   (Vector DB)   │ │
│  │   Port: 8000    │  │   N workers     │  │   Port: 6333    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Redis         │  │   React App     │  │   File Store    │ │
│  │   (State/Queue) │  │   (Frontend)    │  │   (MinIO/NFS)   │ │
│  │   Port: 6379    │  │   Port: 3000    │  │   Port: 9000    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### **8.2 Docker Compose 配置**

**服务定义**：
* **api**：FastAPI 服务（端口 8000），依赖 redis 和 qdrant
* **worker**：Celery 异步任务处理器，使用 celery worker 启动
* **redis**：Redis 7 Alpine 镜像（端口 6379），数据持久化到 redis_data 卷
* **qdrant**：Qdrant v1.7.0 镜像（端口 6333），数据持久化到 qdrant_data 卷
* **frontend**：React 前端构建（端口 3000），依赖 api 服务

**数据卷**：
* redis_data：Redis 持久化存储
* qdrant_data：Qdrant 向量数据存储

### **8.3 环境变量配置**

创建 `.env` 文件，包含以下配置项：

**API 密钥**：
* OPENAI_API_KEY：OpenAI API 密钥
* ANTHROPIC_API_KEY：Anthropic API 密钥
* SERPER_API_KEY：Serper 搜索 API 密钥

**数据库连接**：
* REDIS_URL：Redis 连接地址
* QDRANT_URL：Qdrant 连接地址

**应用配置**：
* LOG_LEVEL：日志级别（INFO/DEBUG/ERROR）
* MAX_CONCURRENT_TASKS：最大并发任务数（默认 5）
* DEFAULT_SEARCH_DEPTH：默认搜索深度（默认 3）
* CACHE_TTL：缓存过期时间（秒）

**安全配置**：
* SECRET_KEY：应用密钥
* ALLOWED_ORIGINS：允许的跨域来源

**MCP 配置**：
* MCP_SERVER_CONFIG_PATH：MCP 服务器配置文件路径

---

## **9. 测试策略**

### **9.1 测试分层**

| 测试类型 | 覆盖范围 | 工具 | 目标覆盖率 |
|---------|----------|------|-----------|
| 单元测试 | Agent 模块、工具函数 | pytest | ≥80% |
| 集成测试 | API 端点、数据库交互 | pytest-httpx | ≥70% |
| 契约测试 | Agent 间通信协议 | pact | 关键路径 100% |
| 端到端测试 | 完整研究流程 | Playwright | 核心场景 |

### **9.2 测试用例示例**

**DAG 生成测试**：
* 创建测试研究任务
* 调用 Master Planner 生成 DAG
* 验证图中无循环依赖
* 验证根节点标题正确
* 验证层级深度不超过配置的最大深度

**剪枝机制测试**：
* 创建模拟的低信息增益节点（info_gain < 0.2）
* 连续创建多个低增益节点
* 调用 should_prune 判断是否应剪枝
* 验证返回结果为 True

---

## **10. 开发实施路线图**

### **10.1 阶段规划**

| 阶段 | 目标 | 交付物 | 验收标准 | 预估工时 |
|------|------|--------|----------|----------|
| **Phase 1** | 核心引擎构建 | - Master Planner<br>- DAG 调度器<br>- 基础 API | - 可生成任务 DAG<br>- 支持任务启动/暂停<br>- 单元测试通过 | 2 周 |
| **Phase 2** | 检索能力实现 | - Retrieval Agent<br>- 网页解析器<br>- L1/L2 缓存 | - 支持 3+ 数据源<br>- 缓存命中率 >30%<br>- 解析成功率 >85% | 2 周 |
| **Phase 3** | MCP 集成 | - MCP Executor<br>- 沙盒环境<br>- 权限确认流程 | - 连接 2+ MCP 服务<br>- 安全确认机制可用 | 1.5 周 |
| **Phase 4** | 质量控制 | - Analyst Agent<br>- SNA 算法<br>- 冲突检测 | - 数值冲突检出率 >90%<br>- 评分机制可用 | 1.5 周 |
| **Phase 5** | 文档生成 | - Writer Agent<br>- 增量生成<br>- 引用管理 | - 可生成 Markdown 报告<br>- 支持段落锁定 | 1 周 |
| **Phase 6** | 前端开发 | - 任务树组件<br>- 证据看板<br>- 状态控制 | - 完整交互流程可用<br>- WebSocket 实时更新 | 2 周 |
| **Phase 7** | 集成测试 | - E2E 测试<br>- 性能测试<br>- 安全测试 | - 核心场景覆盖<br>- 无 P0/P1 缺陷 | 1 周 |

**总计：约 11 周**

### **10.2 里程碑**

| 里程碑 | 日期 | 标志性成果 |
|--------|------|-----------|
| M1 | W2 | MVP 可运行，单任务检索 |
| M2 | W4 | 完整检索链路 + 缓存 |
| M3 | W6 | MCP 集成完成 |
| M4 | W8 | 质量控制 + 文档生成 |
| M5 | W11 | Alpha 版本发布 |

---

## **附录 A：配置文件模板**

### **A.1 MCP 服务器配置**

**配置结构**：
* **mcpServers**：MCP 服务器集合，键名为服务器标识

**服务器类型**：
* **filesystem**：文件系统访问服务器
  * command：npx
  * args：指定允许访问的路径
  * disabled：是否禁用
* **brave-search**：Brave 搜索服务器
  * command：npx
  * args：启动 brave-search 包
  * env：BRAVE_API_KEY 环境变量
* **python-executor**：Python 代码执行器
  * command：uv
  * args：指定工作目录和启动命令

### **A.2 日志配置**

**配置结构**：

**格式化器 (Formatters)**：
* **default**：基础格式，包含时间、模块名、日志级别、消息
* **detailed**：详细格式，额外包含文件名和行号

**处理器 (Handlers)**：
* **console**：控制台输出，级别 INFO，使用 default 格式
* **file**：文件输出，级别 DEBUG，使用 detailed 格式
  * 文件路径：logs/app.log
  * 单文件最大 10MB
  * 保留 5 个备份文件

**日志记录器 (Loggers)**：
* **app**：应用主日志记录器，级别 DEBUG，同时输出到控制台和文件
