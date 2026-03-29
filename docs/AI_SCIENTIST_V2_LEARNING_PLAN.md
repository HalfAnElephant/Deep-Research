# 全面向 AI-Scientist-v2 学习的改进方案列表

本文不是“可以考虑”的建议集合，而是一份按落地顺序组织的系统改造清单。目标只有一个：

- 把本项目从“会话驱动的研究报告系统”，升级为“具备自主探索、路线竞争、实验反馈和论文级交付能力的研究 Agent 平台”。

配套背景文档：

- [`docs/AI_SCIENTIST_V2_ADVANTAGES.md`](/Users/xcy/Program/SH-Program/Deep-Research/docs/AI_SCIENTIST_V2_ADVANTAGES.md)

---

## 1. 北极星目标

我们要学的不是某几个 prompt，而是整套范式。

目标架构要从当前模式：

- 用户给题目
- 系统生成 Markdown 方案
- DAG 检索资料
- 写一篇中文报告

升级为目标模式：

- 用户给研究方向
- 系统先做 novelty / related-work / feasibility 检查
- 系统生成多个候选研究路线
- 系统在分支上并行探索、执行、debug、淘汰
- 系统沉淀结构化研究资产
- 系统产出报告 / 论文 / 图表 / 审稿意见 / 过程树

一句话：

- 从“生成答案”升级为“搜索研究空间并收敛到答案”。

---

## 2. 先定三条总原则

### 2.1 先改数据结构，再改 prompt

现在本项目很多能力做不出来，不是 prompt 不够长，而是中间对象太弱。只要核心对象还是：

- plan markdown
- dag node
- evidence
- report

那么再怎么调 prompt，也很难做出 `AI-Scientist-v2` 那种多轮探索和分支竞争。

所以第一优先级不是“换一个更猛的 prompt”，而是补齐：

- idea schema
- branch schema
- experiment schema
- review schema
- search tree schema
- run artifact schema

### 2.2 让系统围绕“分支”工作，而不是围绕“单方案”工作

当前系统有一个明显短板：

- 起点通常只有一个方案
- 后续多是围绕这一个方案修修补补

要全面向对方学习，就必须把“多个候选研究路线并行竞争”变成一等公民。

### 2.3 失败不能直接 fallback 成模板文本，必须先进入 repair loop

现在本项目很多失败路径最终会退化成：

- fallback plan
- fallback section
- fallback wording

这个对 demo 友好，但对研究系统伤害很大。后续要改成：

- failed -> diagnose -> repair -> retry -> score -> decide prune

而不是：

- failed -> 生成保底文本 -> 继续往下走

---

## 3. 总体改造路线图

建议拆成 4 个阶段。

### Phase 1: 把“研究计划系统”升级成“结构化研究提案系统”

目标：

- 不再以 Markdown 方案为唯一核心对象
- 引入 idea / novelty / feasibility / experiment 等结构化 schema

### Phase 2: 把“静态 DAG 执行”升级成“多分支探索引擎”

目标：

- 不只展开节点
- 开始展开候选路线、候选实验和候选修复

### Phase 3: 把“文献报告生成”升级成“实验反馈驱动的研究生成”

目标：

- 支持 workspace、代码执行、实验结果回流、debug loop

### Phase 4: 把“最终报告”升级成“论文级科研交付物”

目标：

- 引文、图表、审稿、过程树、token 统计、论文式导出全部补齐

---

## 4. 全面改进方案列表

下面按工作流拆解，每一项都给出：

- 要学什么
- 为什么必须做
- 具体怎么改
- 验收标准

---

## 5. 工作流一：目标函数重写

### 5.1 把系统目标从“写报告”改成“完成研究任务”

要学什么：

- `AI-Scientist-v2` 的目标不是生成顺滑文本，而是收敛到可成立的研究产出。

怎么改：

- 在产品定义和后端状态机层面新增 `research objective` 概念。
- `TaskConfig` 增加 `researchMode`，至少支持：
  - `survey`
  - `evidence_report`
  - `experimental_research`
  - `paper_writeup`
- 会话创建时先判断研究类型，再决定后续链路。

建议新增字段：

- `researchMode`
- `deliverableTypes`
- `requiresNoveltyCheck`
- `requiresExperimentLoop`
- `requiresPeerReview`

验收标准：

- 新建任务时，系统能根据模式走不同执行链路。
- `experimental_research` 不再直接复用“检索 -> 写报告”的默认流水线。

### 5.2 把“成功”定义成多维评分，而不是是否生成了文件

怎么改：

- 增加统一的 `ResearchScoreCard`：
  - novelty_score
  - feasibility_score
  - evidence_strength_score
  - execution_success_score
  - writeup_score
  - review_score
- 每轮运行结束都生成 scorecard。

验收标准：

- 系统不再仅凭 `reportPath` 存在就视为完成。
- 任务详情页可看到多维得分。

---

## 6. 工作流二：核心数据结构升级

### 6.1 新增 `ResearchIdea` schema

要学什么：

- 对方把 ideation 输出成结构化 idea，而不是自由文本方案。

怎么改：

- 在 [`backend/app/models/schemas.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/models/schemas.py) 新增：
  - `ResearchIdea`
  - `NoveltyAssessment`
  - `FeasibilityAssessment`
  - `RelatedWorkItem`
  - `ExperimentProposal`
  - `RiskAssessment`

建议字段：

- `ideaId`
- `title`
- `problemStatement`
- `shortHypothesis`
- `abstract`
- `relatedWork`
- `differentiators`
- `noveltyAssessment`
- `feasibilityAssessment`
- `experimentProposals`
- `riskFactors`
- `limitations`
- `score`
- `sourceEvidenceIds`

验收标准：

- 首轮 ideation 结果能以 JSON 落库存储。
- UI 和 API 能读取结构化 idea，而不是只读 Markdown。

### 6.2 新增 `SearchBranch` / `SearchTree` schema

怎么改：

- 为路线探索引擎补结构：
  - `SearchTree`
  - `SearchBranch`
  - `BranchAction`
  - `BranchEvaluation`
  - `BranchFailure`
  - `BranchRepairAttempt`

关键字段：

- branch_id
- parent_branch_id
- branch_type
- branch_goal
- action_type
- action_input
- action_output
- score_before
- score_after
- status
- prune_reason
- debug_depth
- worker_id

验收标准：

- 系统能持久化“探索过哪些分支，为什么保留/剪掉”。
- 后端 API 可以返回 branch tree，而不仅是 DAG。

### 6.3 新增 `ExperimentRun` 和 `Artifact` schema

怎么改：

- 增加实验型对象：
  - `ExperimentWorkspace`
  - `ExperimentRun`
  - `ExperimentMetric`
  - `ExperimentArtifact`
  - `FigureArtifact`
  - `ReviewArtifact`

验收标准：

- 一次实验运行可以挂多个 artifact，而不是只产出 evidence 和 report。

---

## 7. 工作流三：Prompt 体系重构

### 7.1 彻底拆分 prompt 职责

当前问题：

- 计划 prompt、写作 prompt 比较强，但缺少真正的研究探索 prompt 体系。

改法：

- 新建独立 prompt 模块目录，例如：
  - `backend/app/prompts/ideation.py`
  - `backend/app/prompts/novelty.py`
  - `backend/app/prompts/branching.py`
  - `backend/app/prompts/repair.py`
  - `backend/app/prompts/experiment.py`
  - `backend/app/prompts/writeup.py`
  - `backend/app/prompts/review.py`
  - `backend/app/prompts/figure_review.py`

原则：

- 一个 prompt 只负责一个动作。
- 不再让一个 prompt 同时负责“想法、计划、写作、修订”。

验收标准：

- prompt 文件按职责拆分完成。
- 每个阶段可以独立替换模型和参数。

### 7.2 把计划生成从 Markdown 优先改成 JSON 优先

怎么改：

- 方案生成时先输出结构化 JSON：
  - idea
  - evaluation
  - branches
  - experiments
- Markdown 计划变成衍生视图，而不是源数据。

验收标准：

- `ConversationAgent._generate_initial_plan()` 不再直接依赖 Markdown 作为主事实来源。
- front matter 只用于显示和兼容，不再承担系统事实存储职责。

### 7.3 引入动作协议

要学什么：

- 对方 ideation 是 action-based，而不是一次吐全文。

怎么改：

- 定义内部动作协议：
  - `SEARCH_LITERATURE`
  - `ASSESS_NOVELTY`
  - `PROPOSE_IDEA`
  - `REFINE_IDEA`
  - `SPAWN_BRANCH`
  - `RUN_EXPERIMENT`
  - `REPAIR_BRANCH`
  - `FINALIZE_WRITEUP`
- 让 agent 输出结构化 action，而不是直接写长文。

验收标准：

- ideation / branching / repair 阶段都能以 action 协议驱动。

### 7.4 引入 reflection rounds

怎么改：

- 所有关键阶段支持 `num_reflections`。
- 至少覆盖：
  - idea 生成
  - 分支评分
  - 实验失败诊断
  - 写作审校

建议：

- 默认 2 轮
- 高质量模式 4 到 6 轮

验收标准：

- 每个关键输出都能看到初稿、反思、修正版。

---

## 8. 工作流四：Novelty 与 Related Work 前置

### 8.1 在生成研究路线前增加 novelty gate

怎么改：

- 新增 `NoveltyGateService`。
- 执行顺序改为：
  - 检索相关工作
  - 归纳已有方法
  - 识别空白点
  - 生成候选 idea
  - 给出区分点

验收标准：

- 没过 novelty gate 的 idea 不进入主搜索树。

### 8.2 新增“相似工作对照表”

怎么改：

- 每个 idea 自动生成 related-work diff：
  - prior_work
  - overlap
  - difference
  - expected_gain
  - uncertainty

验收标准：

- 每个候选 idea 都能说明“和已有工作相比到底新在哪”。

### 8.3 让 plan 里出现“反对理由”

怎么改：

- ideation 输出除了支持理由，还必须产出：
  - why_this_may_fail
  - why_this_may_not_be_novel
  - missing_evidence

验收标准：

- 每个 idea 至少有 3 条自我反驳。

---

## 9. 工作流五：从 DAG 扩展器升级为 Tree Search Engine

### 9.1 保留 DAG，但让 DAG 退居“执行图”

当前问题：

- [`MasterPlanner.build_dag()`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/planner.py) 现在既承担拆题，又承担路线探索，职责混在一起。

改法：

- DAG 继续用于“执行依赖关系”。
- 新增 Tree Search Engine 专门负责“候选路线探索”。

目标分工：

- Search Tree：找哪条路线值得做
- Execution DAG：把选中的路线执行出来

验收标准：

- 路线选择和任务执行分离成两个子系统。

### 9.2 引入 best-first / beam search / progressive widening

怎么改：

- 新增 `SearchStrategy` 抽象：
  - `best_first`
  - `beam_search`
  - `staged_search`
- 初期可以先做 best-first，后续再加 progressive widening。

新增配置：

- `searchStrategy`
- `numDrafts`
- `numWorkers`
- `beamWidth`
- `branchBudget`
- `maxDebugDepth`
- `debugProbability`

验收标准：

- 系统不再只按 BFS/启发式展开 topic。
- 可通过配置选择搜索策略。

### 9.3 明确 branch scoring 机制

怎么改：

- 每个 branch 用统一评分函数：
  - novelty
  - feasibility
  - expected_info_gain
  - execution_cost
  - evidence_availability
  - risk

示例公式：

- `branch_score = novelty*0.25 + feasibility*0.2 + info_gain*0.2 + evidence*0.15 - cost*0.1 - risk*0.1`

验收标准：

- 保留/剪枝有可解释打分，而不是低信息增益 streak 这类简单启发式。

### 9.4 支持多 draft 起点

怎么改：

- 初始 ideation 一次至少生成 3 到 5 个候选 idea。
- 每个 idea 进入独立 branch。

验收标准：

- 首轮运行默认不是一个方案，而是多个候选方案竞争。

### 9.5 支持 branch repair，而不是只 prune

怎么改：

- 当 branch 失败时先做：
  - diagnose
  - repair proposal
  - retry
  - rescore
- 失败若可修复则保留，不可修复再 prune。

验收标准：

- 分支失败后至少支持一次 repair 回合。

---

## 10. 工作流六：引入 Experiment Manager

### 10.1 增加实验管理层

要学什么：

- 对方有 manager agent，不只是任务节点。

怎么改：

- 新增 `ExperimentManagerService`，职责包括：
  - 选择要跑哪些实验
  - 分配 worker
  - 监控实验状态
  - 汇总失败原因
  - 决定是否继续 debug

验收标准：

- 实验执行有统一 manager，而不是直接从 planner 跳到 execution。

### 10.2 区分“研究分支”和“实验运行”

怎么改：

- 一个研究分支下可包含多个 experiment runs。
- experiment run 结果回写 branch score。

验收标准：

- 一个 branch 可以有 baseline、variant、ablation 多次运行记录。

### 10.3 增加实验预算控制

怎么改：

- 配置项增加：
  - `maxExperimentRuns`
  - `maxTokensPerBranch`
  - `maxRuntimePerBranch`
  - `maxFailedRunsBeforePrune`

验收标准：

- 系统能按 branch 控制预算，而不是全局粗放执行。

---

## 11. 工作流七：Workspace 和代码执行闭环

### 11.1 为实验型任务引入隔离 workspace

怎么改：

- 每个 experimental task 建立独立目录：
  - `runs/<task_id>/<branch_id>/`
- 存放：
  - generated code
  - configs
  - logs
  - metrics
  - plots
  - review notes

验收标准：

- 同一次任务的不同 branch 有独立工作区，互不污染。

### 11.2 引入 `CodeExecutionService`

怎么改：

- 新增代码执行服务：
  - 写入实验代码
  - 运行命令
  - 收集 stdout/stderr
  - 采集指标
  - 解析失败信号

验收标准：

- 实验型任务支持真正的运行反馈，不是只靠语言判断。

### 11.3 引入失败诊断器

怎么改：

- 新增 `ExecutionFailureAnalyzer`，提取：
  - syntax error
  - dependency error
  - runtime error
  - timeout
  - metric regression

验收标准：

- repair loop 能基于失败类型走不同策略。

---

## 12. 工作流八：多 Agent 体系重做

### 12.1 当前四 Agent 需要从“展示型”变成“实战型”

当前问题：

- `four_agents` 目录里已有 ideation / planning / writing / checking，但整体还偏简化实现，没真正成为主引擎。

改法：

- 重新定义 agent 职责：
  - `IdeationAgent`: 生成多候选 idea + novelty check
  - `PlanningAgent`: 将 idea 转成 branch plan 和 experiment plan
  - `ExecutionAgent`: 跑实验、收集反馈
  - `RepairAgent`: 对失败分支做诊断和修复
  - `WritingAgent`: 生成论文式写作草稿
  - `ReviewAgent`: 文本审稿
  - `FigureReviewAgent`: 图表审稿
  - `CitationAgent`: 引文补全

验收标准：

- 现有四 Agent 体系升级为真实工作流，而不是演示式流水线。

### 12.2 增加 Agent Manager

怎么改：

- 新增 `AgentManager` 统一调度各 agent。
- 支持：
  - round-based orchestration
  - branch assignment
  - retry policy
  - handoff payload

验收标准：

- agent 之间的协作由 manager 协调，不再靠执行引擎硬编码串接。

---

## 13. 工作流九：模型路由升级

### 13.1 不再默认一个模型包打天下

怎么改：

- `TaskConfig` 增加独立模型路由：
  - `modelIdeation`
  - `modelNovelty`
  - `modelPlanning`
  - `modelExecution`
  - `modelRepair`
  - `modelWriteup`
  - `modelCitation`
  - `modelReview`
  - `modelFigureReview`

验收标准：

- 每阶段模型可独立配置。

### 13.2 为不同阶段设不同 temperature / timeout / budget

怎么改：

- 配置项拆分：
  - `temperatureIdeation`
  - `temperatureRepair`
  - `timeoutExecution`
  - `timeoutReview`

验收标准：

- 阶段参数不再被一个通用 `_chat_complete()` 吃掉。

---

## 14. 工作流十：写作链路升级成论文式写作链路

### 14.1 从“章节生成”升级成“manuscript assembly”

怎么改：

- 写作阶段新增文稿对象：
  - abstract
  - introduction
  - related work
  - method
  - experiments
  - results
  - limitations
  - conclusion

验收标准：

- `paper_writeup` 模式下不再复用通用中文报告结构。

### 14.2 引文补全变成独立阶段

怎么改：

- 新增 `CitationAgent`：
  - 扫描正文 claim
  - 找缺失引用
  - 补足 citation candidates
  - 生成 citation confidence

验收标准：

- 写作完成后会单独跑 citation pass。

### 14.3 引入章节级 rewrite loop

怎么改：

- 每章都能经历：
  - draft
  - review
  - rewrite
  - accept

验收标准：

- 章节不是一次生成后直接拼装，而是通过小闭环迭代。

---

## 15. 工作流十一：图表与视觉资产纳入主链路

### 15.1 新增 Figure / Table Planner

怎么改：

- 系统根据实验结果自动规划：
  - 哪些表格该出现
  - 哪些图该出现
  - 每张图的目的是什么

验收标准：

- 报告或论文包含结构化 figure plan。

### 15.2 新增 Figure Review Agent

怎么改：

- 审核：
  - 信息量是否足够
  - 配色和标注是否清晰
  - caption 是否和正文一致

验收标准：

- 图表不是附件，而是有独立 review 分数。

---

## 16. 工作流十二：Review 体系升级

### 16.1 把 checking 从“污染检测”升级成“审稿系统”

当前问题：

- 现有 checking 更偏 prompt leakage、机械措辞、脏输出治理。

改法：

- 扩展 review 维度：
  - novelty
  - clarity
  - methodology soundness
  - evidence sufficiency
  - citation quality
  - figure quality
  - reproducibility

验收标准：

- review 输出是结构化审稿意见，不只是“需不需要重写”。

### 16.2 新增 reviewer personas

怎么改：

- 支持多个 reviewer 视角：
  - harsh reviewer
  - method reviewer
  - writing reviewer
  - reproducibility reviewer

验收标准：

- 一次 writeup 至少经过 2 个独立 reviewer 视角。

---

## 17. 工作流十三：可视化与产品层补强

### 17.1 除计划视图外新增搜索树视图

怎么改：

- 前端新增：
  - search tree explorer
  - branch detail panel
  - branch score diff
  - prune reason badge

验收标准：

- 用户能看到系统探索过哪些候选路线，而不是只看到最终计划。

### 17.2 新增实验资产视图

怎么改：

- 前端展示：
  - branch runs
  - logs
  - metrics
  - plots
  - review notes

验收标准：

- 用户能审查中间实验产物。

### 17.3 新增研究轨迹时间线

怎么改：

- 时间线不只显示 progress group，还显示：
  - idea accepted/rejected
  - branch spawned/pruned
  - experiment failed/repaired
  - review passed/failed

验收标准：

- 时间线真正体现研究收敛过程。

---

## 18. 工作流十四：观测、成本和评测体系

### 18.1 增加 token / latency / success-rate 追踪

怎么改：

- 每个阶段记录：
  - token_in
  - token_out
  - latency_ms
  - retry_count
  - success/failure

验收标准：

- 任务详情页可以看到成本和耗时分布。

### 18.2 建立研究任务评测集

怎么改：

- 建一个 benchmark 目录，覆盖：
  - 综述型任务
  - 证据冲突型任务
  - novelty-sensitive 任务
  - experimental_research 任务
  - paper_writeup 任务

验收标准：

- 每次重大改造后可批量回归。

### 18.3 建立 A/B 验证机制

怎么改：

- 对比：
  - 单方案 vs 多分支
  - 无 novelty gate vs 有 novelty gate
  - 无 reflection vs 3 轮 reflection

验收标准：

- 关键机制改造有量化证据支撑。

---

## 19. Phase-by-Phase 落地清单

下面是推荐实施顺序，不然会陷入到处改、处处半成品。

### P0：两周内必须做完的基础改造

- 新增 `ResearchIdea`、`NoveltyAssessment`、`ExperimentProposal` schema。
- 将当前 plan 生成改为“结构化 JSON 为主，Markdown 为视图”。
- 新增 `NoveltyGateService`。
- 初始 ideation 改为一次生成 3 个候选 idea。
- 增加 `num_reflections` 配置。
- 为每个候选 idea 生成 scorecard。

交付结果：

- 系统第一次具备“多候选研究路线”的能力。

### P1：一个月内完成的搜索引擎升级

- 新增 `SearchTree` / `SearchBranch` 模型。
- 新增 `SearchStrategy` 和 `BranchScorer`。
- 将 `MasterPlanner` 从路线探索中剥离，只负责执行 DAG。
- 支持 best-first + branch prune + repair。
- 前端新增 branch tree 基础视图。

交付结果：

- 系统第一次具备显式路线探索能力。

### P2：两个月内完成的实验闭环升级

- 新增 `ExperimentManagerService`。
- 引入 workspace 和 `CodeExecutionService`。
- 引入 `ExecutionFailureAnalyzer`。
- 支持 baseline / variant / ablation runs。
- experiment run 结果回写 branch score。

交付结果：

- 系统第一次具备“代码执行反馈驱动的研究收敛能力”。

### P3：论文级交付能力补齐

- 写作模式拆成 `report` 和 `paper_writeup`。
- 新增 citation pass。
- 新增 figure planner / figure review。
- 新增 multi-reviewer pass。
- 支持 PDF / appendix / review note 导出。

交付结果：

- 系统第一次具备“科研稿件交付能力”。

---

## 20. 优先级排序：什么最该先抄

如果资源有限，不要平均用力。最值钱的是下面 12 项。

### Top 1-4：先补研究核心

- 前置 novelty gate
- 多候选 idea 生成
- reflection loop
- SearchTree + branch scorer

### Top 5-8：再补探索闭环

- branch repair loop
- ExperimentManager
- workspace + code execution
- failure analyzer

### Top 9-12：最后补论文交付

- citation pass
- review personas
- figure review
- search tree visualization

---

## 21. 明确哪些不要抄偏

全面向对方学习，不等于机械照搬。下面三类不要先做。

### 21.1 不要先卷 UI 皮肤

真正差距在研究内核，不在界面样式。

### 21.2 不要先把 prompt 越写越长

如果 schema、状态机、分支结构没变，prompt 再长也只是高成本模板生成。

### 21.3 不要先把所有模式都变成实验型任务

本项目有自己的优势：

- 对话驱动
- 通用主题研究
- 中文报告体验

正确做法是双轨：

- `survey/evidence_report` 继续保留当前强项
- `experimental_research/paper_writeup` 走新链路

---

## 22. 建议直接开工的代码切入点

第一批建议改这些位置：

- [`backend/app/models/schemas.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/models/schemas.py)
- [`backend/app/services/conversation_agent.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/conversation_agent.py)
- [`backend/app/services/planner.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/planner.py)
- [`backend/app/services/execution_engine.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/execution_engine.py)
- [`backend/app/services/four_agents/ideation_agent.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/four_agents/ideation_agent.py)
- [`backend/app/services/four_agents/planning_agent.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/four_agents/planning_agent.py)
- [`backend/app/services/writer.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/writer.py)

建议新增目录：

- `backend/app/prompts/`
- `backend/app/services/search_tree/`
- `backend/app/services/experiments/`
- `backend/app/services/review/`
- `backend/app/services/citation/`

---

## 23. 最后的结论

真正全面向 `AI-Scientist-v2` 学习，不是“把 prompt 写得更像它”，而是做三次范式切换：

1. 从 Markdown 计划范式，切到结构化研究对象范式。
2. 从单方案执行范式，切到多分支搜索范式。
3. 从文献报告范式，切到实验反馈驱动的科研产出范式。

如果只允许我给一句最核心的执行建议，那就是：

- 先把 `novelty gate + multi-idea + search tree + repair loop` 做出来。

这是所有后续能力的底座。没有这四个，本项目很难真正追上 `AI-Scientist-v2` 的研究内核。

