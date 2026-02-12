# Deep Research 深度科研辅助系统 - 运行流程详解

## 目录

1. [系统架构概述](#1-系统架构概述)
2. [全流程交互逻辑](#2-全流程交互逻辑)
3. [核心代理详解](#3-核心代理详解)
4. [数据流转关系](#4-数据流转关系)
5. [API接口规范](#5-api接口规范)
6. [错误处理与容错](#6-错误处理与容错)

---

## 1. 系统架构概述

### 1.1 分层架构图

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

### 1.2 核心组件说明

| 层级 | 组件 | 职责 |
|------|------|------|
| **交互层** | CoT 编辑器 | 展示和编辑思维链，允许用户干预任务规划 |
| **交互层** | 实时证据看板 | 展示收集到的证据流，支持点击锚定 |
| **交互层** | Markdown 分屏预览 | 实时预览生成的报告，支持段落锁定 |
| **编排层** | Master Planner | 任务拆解、DAG 生成、动态调度 |
| **编排层** | State Manager | FSM 状态管理、上下文快照与恢复 |
| **代理层** | Retrieval Agent | 信息检索、网页解析、缓存管理 |
| **代理层** | Analyst Agent | 数值冲突检测、信誉评分、语义对齐 |
| **代理层** | MCP Executor | 外部工具调用、沙盒执行 |
| **代理层** | Writer Agent | 增量文档生成、引用管理 |
| **基础设施层** | Vector DB | L2 向量缓存 |
| **基础设施层** | MCP Servers | 外部工具和数据源连接 |
| **基础设施层** | File System | 本地文件访问 |

---

## 2. 全流程交互逻辑

### 2.1 状态机 (FSM) 流程图

```
                    ┌─────────────┐
                    │   Ready     │  ← 录入议题、上传种子文件、配置偏好
                    └──────┬──────┘
                           │  [启动研究]
                           ▼
                    ┌─────────────┐
                    │  Planning   │  ← 生成 DAG、用户可调整节点/依赖
                    └──────┬──────┘
                           │  [执行计划]
                           ▼
                    ┌─────────────┐
                    │  Executing  │  ← 检索/分析并行、实时推送证据
                    └──────┬──────┘
                           │  [发现冲突]
                    ┌──────▼──────┐
                    │  Reviewing  │  ← 冲突高亮、用户选择采信源
                    └──────┬──────┘
                           │  [冲突解决]
                    ┌──────▼──────┐
                    │ Synthesizing│  ← 整合证据、生成报告、锁定段落
                    └──────┬──────┘
                           │  [完成确认]
                           ▼
                    ┌─────────────┐
                    │  Finalizing │  ← 导出文档、生成参考文献、归档
                    └─────────────┘
```

### 2.2 各状态详解

#### **状态 1: Ready (就绪)**

| 属性 | 说明 |
|------|------|
| **UI 表现** | 初始化界面，含多模态输入模块 |
| **用户操作** | 录入研究议题、上传种子文件、配置偏好 |
| **系统响应** | 预加载常用 MCP 服务列表 |

**输入数据:**
```json
{
  "title": "研究标题",
  "description": "研究描述",
  "config": {
    "maxDepth": 3,
    "maxNodes": 50,
    "searchSources": ["arXiv", "Google Scholar", "IEEE"],
    "priority": 5
  }
}
```

**输出数据:**
```json
{
  "taskId": "uuid-xxxx",
  "status": "READY",
  "createdAt": "2024-01-01T00:00:00Z"
}
```

---

#### **状态 2: Planning (规划)**

| 属性 | 说明 |
|------|------|
| **UI 表现** | 展示任务图谱节点 (DAG) |
| **用户操作** | 暂停修改节点、拖拽调整依赖、删除冗余路径 |
| **系统响应** | 规划器拆解任务，生成依赖关系图 |

**Master Planner 处理流程:**

```
输入: CreateTaskRequest
  │
  ├─> [BFS 展开] 生成首级子课题
  │   ├─> 背景研究
  │   ├─> 现状分析
  │   └─> 挑战识别
  │
  ├─> [DFS 深挖] 根据反馈垂直展开
  │
  ├─> [循环检测] 维护 VisitedStack 防止无限循环
  │
  ├─> [动态剪枝] 计算 infoGainScore
  │   └─> 若连续 < 0.2，合并/舍弃分支
  │
  └─> 输出: DAGGraph
```

**输出数据 (DAG):**
```json
{
  "nodes": [
    {
      "taskId": "node-1",
      "title": "背景研究",
      "status": "PENDING",
      "priority": 5,
      "depth": 1
    }
  ],
  "edges": [
    {
      "from": "node-1",
      "to": "node-2",
      "type": "DEPENDS_ON"
    }
  ]
}
```

---

#### **状态 3: Executing (执行)**

| 属性 | 说明 |
|------|------|
| **UI 表现** | 进度条显示、实时证据流看板 |
| **用户操作** | 干预调整检索词、调整优先级、授权 MCP 调用 |
| **系统响应** | 检索/执行代理并行运作，推送 Evidence[] |

**WebSocket 实时推送:**
```json
{
  "event": "EVIDENCE_FOUND",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "taskId": "node-1",
    "evidence": { ... }
  }
}
```

---

#### **状态 4: Reviewing (审查)**

| 属性 | 说明 |
|------|------|
| **UI 表现** | 冲突节点高亮显示、对比弹窗 |
| **用户操作** | 选择采信源、指令深挖争议点 |
| **系统响应** | 分析代理检测一致性，聚合冲突数据 |

**冲突检测流程:**
```
输入: Evidence[]
  │
  ├─> [单位标准化] 统一转换为 SI 单位
  │
  ├─> [阈值判定]
  │   └─> 若 (ValueA - ValueB) / Max > 15% 且环境相似
  │       └─> 生成 ConflictRecord
  │
  └─> 输出: ConflictRecord[]
```

---

#### **状态 5: Synthesizing (合成)**

| 属性 | 说明 |
|------|------|
| **UI 表现** | 文档分屏预览、实时高亮 |
| **用户操作** | 查看引用源、指令重写、锁定段落 |
| **系统响应** | 写作代理整合证据，执行增量润色 |

**写作流程:**
```
输入: Evidence[] + TaskNode[]
  │
  ├─> [分段绑定] 每个 # Section 绑定 TaskNode
  │
  ├─> [局部生成] 节点完成时触发对应段落生成
  │
  ├─> [段落锁定] 人工编辑段落标记为 LOCKED
  │
  ├─> [溯源索引] 维护 UUID -> Citation 映射
  │
  └─> 输出: Markdown 文档
```

---

#### **状态 6: Finalizing (归档)**

| 属性 | 说明 |
|------|------|
| **UI 表现** | 最终报告生成、参考文献列表 |
| **用户操作** | 导出文档、同步 Zotero、启动后续研究 |
| **系统响应** | 生成 .bib 文件、清理临时上下文 |

---

## 3. 核心代理详解

### 3.1 Master Planner Agent (首席任务规划代理)

#### 职能
将抽象的科研目标转化为可执行的有向无环图 (DAG)。

#### 输入

```typescript
interface CreateTaskRequest {
  title: string;           // 研究标题
  description: string;     // 研究描述
  config: {
    maxDepth: number;      // 最大搜索深度 (默认 3)
    maxNodes: number;      // 最大节点数 (默认 50)
    searchSources: string[]; // 数据源列表
    priority: number;      // 优先级 (1-5)
  };
}
```

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      Master Planner 处理流程                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [初始化] 创建根节点                                          │
│     └─> taskId = uuid(), parentTaskId = null                    │
│                                                                 │
│  2. [BFS 展开] 首级子课题                                        │
│     ├─> 背景研究 (Background Research)                          │
│     ├─> 现状分析 (State of the Art)                            │
│     └─> 挑战识别 (Challenge Identification)                     │
│                                                                 │
│  3. [DFS 深挖] 根据检索反馈垂直展开                              │
│     └─> 递归展开子任务，直至达到 maxDepth                        │
│                                                                 │
│  4. [循环检测] 防止无限循环                                      │
│     └─> 维护 VisitedStack，检测重复访问                         │
│                                                                 │
│  5. [动态剪枝] 信息增益判定                                      │
│     ├─> 计算 infoGainScore = newInfo / existingInfo            │
│     └─> 若连续 < 0.2，标记为 PRUNED                             │
│                                                                 │
│  6. [依赖解析] 构建任务依赖关系                                  │
│     └─> 生成 edges: [{from, to, type}]                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 调度算法

```
PRIORITY_QUEUE ← 所有 PENDING 节点
VISITED_SET    ← ∅

while PRIORITY_QUEUE 非空:
    task ← PRIORITY_QUEUE.pop()

    if task.id ∈ VISITED_SET:
        continue

    if task.dependencies 未全部完成:
        continue

    task.status ← RUNNING
    VISITED_SET.add(task.id)

    // 调用对应 Agent 处理
    result ← execute_task(task)

    // 计算信息增益
    infoGain ← calculate_info_gain(result)
    if infoGain < 0.2:
        task.status ← PRUNED
    else:
        task.status ← COMPLETED
        task.output ← result

    // 激活子任务
    for child in task.children:
        PRIORITY_QUEUE.push(child)
```

#### 输出

```typescript
interface DAGGraph {
  nodes: TaskNode[];
  edges: Edge[];
}

interface TaskNode {
  taskId: string;
  parentTaskId: string | null;
  title: string;
  description: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SUSPENDED' | 'PRUNED';
  priority: number;
  dependencies: string[];
  children: string[];
  metadata: {
    estimatedTokenCost: number;
    searchDepth: number;
    infoGainScore: number;
    createdAt: string;
    updatedAt: string;
  };
}
```

---

### 3.2 Retrieval Agent (检索代理)

#### 职能
执行全域信息捕获，配置三级缓存机制。

#### 输入

```typescript
interface RetrievalRequest {
  taskNode: TaskNode;
  query: string;
  sources: string[];  // ['arXiv', 'Google Scholar', 'IEEE', ...]
}
```

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      Retrieval Agent 处理流程                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [查询扩展] 生成结构化检索式                                   │
│     格式: (Term OR Abbreviation) AND (Year) AND (Action Verb)   │
│                                                                 │
│  2. [L1 缓存校验] 内存缓存 (LRU, 最大 1000 条, TTL 1h)          │
│     └─> 若相似度 > 0.9，直接返回                                 │
│                                                                 │
│  3. [L2 缓存校验] 向量数据库 (Qdrant, TTL 24h)                  │
│     ├─> 向量化查询                                              │
│     └─> 若相似度 > 0.9，直接返回                                 │
│                                                                 │
│  4. [API 调用] 执行外部检索                                      │
│     ├─> Serper / Google Search (网页)                           │
│     ├─> arXiv API (学术论文)                                    │
│     ├─> Semantic Scholar (元数据增强)                           │
│     └─> CrossRef (DOI 解析)                                     │
│                                                                 │
│  5. [网页解析] 提取正文内容                                      │
│     ├─> 使用 Readability/trafilatura                            │
│     ├─> 检测 <table> 标签 → 提取题注 + 独立 evidenceId          │
│     └─> 检测 <img> 标签 → 提取题注 + 独立 evidenceId            │
│                                                                 │
│  6. [缓存写入] 更新 L1 和 L2 缓存                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 查询扩展示例

```
输入: "transformer architecture"

扩展后:
  ("transformer" OR "attention mechanism") AND
  (2024 OR 2023 OR 2022) AND
  ("improve" OR "optimize" OR "analyze" OR "review")
```

#### 输出

```typescript
interface Evidence {
  id: string;
  sourceType: 'PAPER' | 'WEB' | 'PATENT' | 'MCP';
  url: string;
  content: string;  // Markdown 格式
  metadata: {
    authors: string[];
    publishDate: string;
    title: string;
    abstract: string;
    impactFactor: number;
    isPeerReviewed: boolean;
    relevanceScore: number;  // 0-1
    citationCount: number;
  };
  score: number;  // 综合信誉评分 0-1
  extractedData: {
    tables: Array<{caption: string, data: any}>;
    images: Array<{caption: string, url: string}>;
    numericalValues: Array<{value: number, unit: string, context: string}>;
  };
}
```

---

### 3.3 Analyst Agent (分析代理)

#### 职能
作为质量控制核心，执行语义数值对齐 (SNA) 和冲突检测。

#### 输入

```typescript
interface AnalysisRequest {
  evidences: Evidence[];
}
```

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       Analyst Agent 处理流程                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [信誉评分计算]                                               │
│     │                                                           │
│     ├─> 基础权重:                                               │
│     │   • 论文 = 1.0                                            │
│     │   • 专利 = 0.8                                            │
│     │   • 网页 = 0.5                                            │
│     │   • MCP 数据 = 0.9                                        │
│     │                                                           │
│     ├─> 影响因子加成 = IF / 10 (最高 1.5)                       │
│     │                                                           │
│     ├─> 同行评议加成 = 1.2x (若已评议)                          │
│     │                                                           │
│     ├─> 时效性衰减:                                             │
│     │   • < 5 年: 1.0x                                          │
│     │   • 5-10 年: 线性衰减                                     │
│     │   • > 10 年: 0.5x                                         │
│     │                                                           │
│     └─> 最终评分 = 基础 × 影响因子 × 同行评议 × 时效性 × 相关性  │
│                                                                 │
│  2. [单位标准化] 统一转换为 SI 单位                              │
│     • 1 km → 1000 m                                            │
│     • 1 GB → 1e9 bytes                                         │
│     • 等                                                       │
│                                                                 │
│  3. [冲突检测]                                                   │
│     │                                                           │
│     ├─> 提取所有数值                                            │
│     │   └─> {value, unit, context, evidenceId}                 │
│     │                                                           │
│     ├─> 按 (parameter + context) 分组                           │
│     │                                                           │
│     ├─> 计算差异: variance = (ValueA - ValueB) / Max           │
│     │                                                           │
│     └─> 若 variance > 15% 且环境相似                            │
│         └─> 生成 ConflictRecord                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 输出

```typescript
interface ConflictRecord {
  conflictId: string;
  parameter: string;  // 发生冲突的参数名称
  disputedValues: Array<{
    value: number;
    unit: string;
    evidenceId: string;
    source: string;
  }>;
  variance: number;  // 差异程度 (百分比)
  context: string;   // 冲突上下文
  resolutionStatus: 'OPEN' | 'RESOLVED' | 'IGNORED';
  resolution?: {
    selectedEvidenceId: string;
    reason: string;
    resolvedAt: string;
  };
}
```

---

### 3.4 MCP Executor Agent (MCP 执行代理)

#### 职能
安全地连接外部工具与数据源。

#### 输入

```typescript
interface MCPExecutionRequest {
  toolName: string;
  method: string;
  params: Record<string, any>;
  mode: 'read' | 'write' | 'execute';
}
```

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Executor 处理流程                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [协议处理] 基于 JSON-RPC 2.0                                 │
│     └─> 构建 JSON-RPC 请求体                                    │
│                                                                 │
│  2. [权限检查]                                                   │
│     │                                                           │
│     ├─> Read-Only 模式                                          │
│     │   └─> 允许直接执行                                        │
│     │                                                           │
│     └─> Write/Execute 模式                                      │
│         ├─> 挂起任务                                            │
│         ├─> 返回 USER_CONFIRMATION_REQUIRED                     │
│         └─> 等待 UI 授权后执行                                   │
│                                                                 │
│  3. [执行调用]                                                   │
│     │                                                           │
│     ├─> 短耗时任务                                              │
│     │   └─> 同步等待结果                                        │
│     │                                                           │
│     └─> 长耗时任务                                              │
│         ├─> 返回 JOB_ID                                         │
│         └─> 每 5 秒轮询一次状态                                  │
│                                                                 │
│  4. [沙盒隔离]                                                   │
│     └─> 若执行失败，隔离错误，返回部分结果                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### JSON-RPC 请求示例

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "python-executor",
    "arguments": {
      "code": "print('Hello World')",
      "timeout": 30
    }
  },
  "id": 1
}
```

#### 输出

```typescript
interface MCPExecutionResult {
  status: 'SUCCESS' | 'USER_CONFIRMATION_REQUIRED' | 'FAILED';
  result?: any;
  jobId?: string;  // 长耗时任务
  error?: string;
}
```

---

### 3.5 Writer Agent (写作代理)

#### 职能
执行增量式文档生成作业。

#### 输入

```typescript
interface WritingRequest {
  taskNode: TaskNode;
  evidences: Evidence[];
  existingContent: string;  // 已存在的内容
  lockedSections: string[];  // 已锁定的段落 ID
}
```

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                       Writer Agent 处理流程                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. [分段绑定]                                                   │
│     └─> 每个 # Section 绑定至特定 TaskNode                      │
│                                                                 │
│  2. [锁定检查]                                                   │
│     └─> 检查 lockedSections，跳过已锁定段落                      │
│                                                                 │
│  3. [局部生成]                                                   │
│     │                                                           │
│     ├─> 节点完成时触发                                          │
│     ├─> 仅生成对应段落                                          │
│     └─> 使用 LLM (GPT-4 / Claude Opus)                         │
│                                                                 │
│  4. [溯源索引]                                                   │
│     │                                                           │
│     ├─> 维护 UUID -> Citation 映射                              │
│     └─> 自动生成 [1][2] 引用标记                                │
│                                                                 │
│  5. [增量润色]                                                   │
│     │                                                           │
│     ├─> 合并新段落到现有内容                                    │
│     └─> 检测并修复格式问题                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 输出

```typescript
interface WritingResult {
  content: string;  // Markdown 格式
  citations: Record<string, Citation>;  // UUID -> 映射
  lockedSections: string[];  // 更新后的锁定列表
}

interface Citation {
  id: string;
  authors: string[];
  title: string;
  year: number;
  source: string;
  url: string;
}
```

---

## 4. 数据流转关系

### 4.1 全局数据流图

```
┌──────────────┐
│  User Input  │
│  (研究议题)   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Master Planner                            │
│  输入: CreateTaskRequest                                         │
│  输出: DAGGraph (nodes + edges)                                  │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Retrieval Agent                             │
│  输入: TaskNode + Query                                          │
│  输出: Evidence[]                                                │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Analyst Agent                              │
│  输入: Evidence[]                                                │
│  输出: Evidence[] (带评分) + ConflictRecord[]                    │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ├──────────────┐
       │              ▼
       │     ┌─────────────────┐
       │     │  Conflict?      │──Yes──> Reviewing 状态
       │     └────────┬────────┘
       │              │ No
       │              ▼
       │     ┌─────────────────┐
       │     │ MCP Required?   │──Yes──> MCP Executor
       │     └────────┬────────┘
       │              │ No
       ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Writer Agent                              │
│  输入: Evidence[] + TaskNode[] + existingContent                 │
│  输出: Markdown Document + Bibliography                          │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│ Final Report │
│  (导出)       │
└──────────────┘
```

### 4.2 数据结构关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                         数据结构关系                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TaskNode (1) ────────────────┬────────> (N) Evidence           │
│    ├─ taskId: UUID            │           ├─ id: UUID           │
│    ├─ status: enum            │           ├─ sourceType: enum   │
│    ├─ dependencies: UUID[]    │           ├─ content: string    │
│    ├─ children: UUID[]        │           ├─ score: number      │
│    └─ output: Evidence[]  ────┘           └─ extractedData      │
│                                         │                        │
│                                         ▼                        │
│                                ConflictRecord                   │
│                                  ├─ conflictId: UUID            │
│                                  ├─ disputedValues[]            │
│                                  └─ resolutionStatus            │
│                                                                 │
│  TaskNode (N) ──> DAGGraph                                     │
│    ├─ nodes: TaskNode[]                                         │
│    └─ edges: Edge[]                                             │
│        ├─ from: UUID                                            │
│        └─ to: UUID                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. API 接口规范

### 5.1 RESTful API 端点

#### 任务管理

| 方法 | 端点 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/tasks` | 创建新研究任务 | CreateTaskRequest | TaskNode |
| GET | `/api/v1/tasks/{task_id}` | 获取任务详情 | - | TaskNode |
| PUT | `/api/v1/tasks/{task_id}` | 更新任务配置 | UpdateTaskRequest | TaskNode |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务 | - | DeleteResponse |
| GET | `/api/v1/tasks/{task_id}/dag` | 获取任务 DAG 结构 | - | DAGGraph |

#### 证据管理

| 方法 | 端点 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/api/v1/evidence` | 获取证据列表 | QueryParams | Evidence[] |
| GET | `/api/v1/evidence/{evidence_id}` | 获取证据详情 | - | Evidence |
| POST | `/api/v1/evidence/{evidence_id}/vote` | 证据投票 | VoteRequest | VoteResponse |

#### 状态控制

| 方法 | 端点 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| POST | `/api/v1/tasks/{task_id}/start` | 启动任务执行 | - | StateResponse |
| POST | `/api/v1/tasks/{task_id}/pause` | 暂停任务 | - | StateResponse |
| POST | `/api/v1/tasks/{task_id}/resume` | 恢复任务 | - | StateResponse |
| POST | `/api/v1/tasks/{task_id}/abort` | 终止任务 | - | StateResponse |

### 5.2 WebSocket 事件流

**订阅频道:** `task/{task_id}/progress`

**推送事件类型:**

| 事件类型 | 说明 | 数据结构 |
|---------|------|----------|
| TASK_STARTED | 任务开始执行 | `{taskId, timestamp, node}` |
| TASK_PROGRESS | 进度更新 | `{taskId, timestamp, progress: 0-100}` |
| EVIDENCE_FOUND | 发现新证据 | `{taskId, timestamp, evidence}` |
| TASK_COMPLETED | 任务完成 | `{taskId, timestamp, result}` |
| ERROR | 执行错误 | `{taskId, timestamp, error}` |

### 5.3 请求/响应示例

#### 创建任务

**请求** (POST /api/v1/tasks):
```json
{
  "title": "大语言模型的幻觉问题研究",
  "description": "调研 LLM 幻觉问题的成因、检测方法和缓解策略",
  "config": {
    "maxDepth": 3,
    "maxNodes": 50,
    "searchSources": ["arXiv", "Google Scholar"],
    "priority": 5
  }
}
```

**响应** (201 Created):
```json
{
  "taskId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "READY",
  "createdAt": "2024-01-01T00:00:00Z",
  "dag": {
    "nodes": [...],
    "edges": [...]
  }
}
```

---

## 6. 错误处理与容错

### 6.1 错误分类与处理策略

| 错误类型 | 示例 | 处理策略 |
|---------|------|----------|
| 网络超时 | API 请求超时 (>30s) | 重试 3 次，指数退避 (1s, 2s, 4s) |
| API 失败 | 429/5xx 响应 | 切换备用 API，记录日志 |
| 解析失败 | 网页内容提取异常 | 标记为低质量，继续处理 |
| DAG 冲突 | 循环依赖检测 | 拒绝提交，返回错误路径 |
| 资源耗尽 | Token 限额超出 | 暂停任务，用户确认后续 |
| MCP 失败 | 外部工具调用失败 | 沙盒隔离，返回部分结果 |

### 6.2 状态恢复机制

**快照保存:**
- 触发时机: 每个任务节点完成时
- 存储位置: Redis
- 过期时间: 24 小时

**快照结构:**
```typescript
interface StateSnapshot {
  task_id: string;
  timestamp: string;
  fsm_state: 'READY' | 'PLANNING' | 'EXECUTING' | 'REVIEWING' | 'SYNTHESIZING' | 'FINALIZING';
  completed_nodes: string[];
  pending_nodes: string[];
  evidence_cache: Record<string, Evidence>;
  conflict_records: ConflictRecord[];
}
```

**恢复逻辑:**
1. 检查 Redis 中是否存在快照
2. 若存在，反序列化并恢复状态
3. 从断点处继续执行

---

## 附录

### A. 状态转换表

| 当前状态 | 触发事件 | 目标状态 |
|---------|---------|----------|
| READY | start() | PLANNING |
| PLANNING | dag_generated | EXECUTING |
| EXECUTING | conflict_detected | REVIEWING |
| EXECUTING | all_completed | SYNTHESIZING |
| REVIEWING | conflict_resolved | EXECUTING |
| REVIEWING | all_resolved | SYNTHESIZING |
| SYNTHESIZING | content_approved | FINALIZING |
| * | abort() | FINALIZING |
| * | pause() | SUSPENDED |
| SUSPENDED | resume() | 恢复原状态 |

### B. 配置参数汇总

| 参数 | 默认值 | 说明 |
|------|--------|------|
| maxDepth | 3 | 最大搜索深度 |
| maxNodes | 50 | 最大任务节点数 |
| L1_CACHE_SIZE | 1000 | L1 缓存容量 |
| L1_CACHE_TTL | 3600 | L1 缓存过期时间 (秒) |
| L2_SIMILARITY_THRESHOLD | 0.9 | L2 相似度阈值 |
| L2_CACHE_TTL | 86400 | L2 缓存过期时间 (秒) |
| INFO_GAIN_THRESHOLD | 0.2 | 信息增益剪枝阈值 |
| CONFLICT_VARIANCE_THRESHOLD | 0.15 | 冲突检测差异阈值 (15%) |
| MAX_CONCURRENT_TASKS | 5 | 最大并发任务数 |
| RETRY_MAX_ATTEMPTS | 3 | 最大重试次数 |
| RETRY_BASE_DELAY | 1 | 重试基础延迟 (秒) |

---

*文档版本: 1.0*
*更新日期: 2024*
