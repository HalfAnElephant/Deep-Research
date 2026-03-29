# AI-Scientist-v2 相对本项目的优势清单

本文目标不是做中性综述，而是尽量穷举当前公开可见实现下，`SakanaAI/AI-Scientist-v2` 相对本项目的优势点，尤其聚焦：

- prompt 设计
- 生成机制
- 路线探索

对比对象：

- 对方项目：[`SakanaAI/AI-Scientist-v2`](https://github.com/SakanaAI/AI-Scientist-v2)
- 本项目：当前仓库 `Deep-Research`

说明：

- “明确优势”表示可以从公开 README / 公开代码 / 论文摘要直接确认。
- “推断性优势”表示结合公开配置和实现入口，可以较高置信度推断，但细节未在当前对比中完全展开。
- 由于 GitHub 网页抓取对部分长文件有折叠，以下结论以公开 README、公开原始文件入口、论文摘要，以及本项目现有代码实现为依据。

## 1. 总体判断

如果把本项目定义为“对话驱动的深度研究与报告生成系统”，那么 `AI-Scientist-v2` 的核心优势不是 UI 或通用信息整理，而是它更像一个面向机器学习科研产出的“自主实验型研究系统”。

它的强项集中在三件事：

1. 它把“研究”定义为可执行实验搜索，而不是主要定义为文献检索加报告写作。
2. 它把“生成”做成了多阶段、可回退、可并行、可 debug 的搜索过程，而不是单次规划后顺序执行。
3. 它把“路线探索”做成了显式的 tree search 和 manager-driven exploration，而不是当前本项目这种受 `maxDepth/maxNodes` 约束的启发式 DAG 展开。

因此，如果用户目标是“产出一篇有实验、有图表、有消融、有论文格式的科研稿件”，`AI-Scientist-v2` 的方法论明显更强；如果用户目标是“围绕任意主题做资料研究、证据整理和中文报告生成”，本项目的交互性和产品形态更友好，但研究内核的开放式探索能力不如对方。

## 2. Prompt 设计方面的优势

### 2.1 Prompt 目标定义更高阶，不只是格式约束

`AI-Scientist-v2` 的 ideation prompt 不是简单要求“输出一个方案”，而是把模型角色直接设定为：

- 提出高影响力研究想法
- 类 grant proposal
- 必须新颖
- 要与现有文献清楚区分
- 资源约束必须落在学术实验室可承受范围
- 目标是顶会可发表

这比本项目当前的方案生成 prompt 更强。

本项目的初始规划 prompt 在 [`backend/app/services/conversation_agent.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/conversation_agent.py#L1022) 附近，本质上是：

- 生成一个可执行研究方案
- 必须是 Markdown
- 必须带 front matter
- 正文包含固定章节

这个 prompt 的优势是稳定、可控、易解析，但问题是它主要在约束“输出格式”，而不是约束“研究质量上限”。对比之下，`AI-Scientist-v2` 的 prompt 从一开始就在约束：

- novelty
- feasibility
- publishability
- distinction from prior work

这使得它更像“科研提案生成 prompt”，而本项目更像“研究计划文档生成 prompt”。

### 2.2 Prompt 内建工具使用要求，形成“先检索再定稿”的硬约束

`perform_ideation_temp_free.py` 中的系统 prompt 明确要求至少做一次文献搜索后才能 finalize idea，并且暴露了 `SemanticScholarSearchTool` 与 `FinalizeIdea` 两类动作。

这比本项目当前的规划阶段强在：

- 对方不是“先写计划，再进检索”
- 而是“在想法形成阶段就把检索与 novelty check 绑定”

本项目当前的初始计划生成并没有把“先做 novelty / related work 检查再确认计划”做成 prompt 级硬约束，而是先产出计划，再由执行阶段去检索。这会导致计划更容易出现：

- 选题重复
- 问题过宽
- 方法设定先验不足
- 与现有工作区分度不够

### 2.3 Prompt 采用动作协议，而不是纯自然语言大段输出

`AI-Scientist-v2` 的 ideation prompt 要求模型按 `ACTION:` / `ARGUMENTS:` 格式输出，并在 finalize 时输出结构化 IDEA JSON。

这个设计的优点：

- 更接近 agent protocol
- 更利于中间轮调用工具
- 便于做反思轮次中的状态延续
- 便于失败时定位是“动作错”还是“内容错”

本项目当前的计划生成和计划修订仍然是标准 chat completion：

- system prompt
- user prompt
- 返回整段 Markdown

这种方式更轻，但在复杂研究任务上更脆弱，因为：

- 中间思考过程不可见
- 工具调用不是 prompt 原生协议的一部分
- 失败恢复只能靠 fallback 或重试整段文本

### 2.4 Prompt 自带 reflection loop，研究想法不是一次性吐出

`AI-Scientist-v2` 的 ideation 有 `num_reflections` 参数，且反思 prompt 明确要求模型评估：

- quality
- novelty
- feasibility
- clarity
- concise
- JSON correctness

这个机制比本项目当前的方案修订强很多。本项目虽支持用户继续“改方案”，但默认系统不会主动在内部进行多轮自我批判和 refinement。也就是说：

- 本项目的修订是“用户驱动”
- 对方的修订是“系统内生”

在开放式科研任务里，后者对质量上限更有帮助。

### 2.5 Prompt 对实验细节的要求更具体

`FinalizeIdea` 要求输出内容包含：

- `Short Hypothesis`
- `Related Work`
- `Abstract`
- `Experiments`
- `Risk Factors and Limitations`

且实验部分要求：

- simple and feasible
- specific
- exactly how to test the hypothesis
- precise algorithmic changes
- evaluation metrics

相比之下，本项目当前方案 prompt 更偏“研究任务拆解”，不是“科研实验设计”。因此在科研场景下，对方 prompt 在以下方面更强：

- 假设表达更明确
- 实验可证伪性更强
- 评价指标前置
- 风险和局限是原生字段而不是补充段落

### 2.6 写作 prompt 与研究 prompt 分工更清晰

`AI-Scientist-v2` 把 ideation、experimentation、writeup、review 分开配置，且 README 中明确不同阶段允许使用不同模型：

- experiment/code
- writeup
- citation
- review
- plot aggregation

本项目虽然也有 planning / retrieval / writing / checking 等模块，但 prompt 层面的职责隔离没有对方那么强。比如本项目 [`backend/app/services/writer.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/writer.py#L519) 的 system prompt 主要聚焦中文学术写作质量，而不是把“写作”“引文收集”“审稿”“图表审美检查”拆成多个独立 prompt 闭环。

对方的好处是：

- 每个 prompt 只解决一种问题
- 每种模型调用的目标函数更单一
- 更容易做阶段性替换和针对性调参

## 3. 生成机制方面的优势

### 3.1 从“生成文档”升级为“生成研究过程”

本项目的主链路更接近：

1. 生成方案
2. 构建 DAG
3. 检索证据
4. 分析冲突
5. 写报告

`AI-Scientist-v2` 更接近：

1. 生成研究 idea
2. 将 idea 转成实验工作区
3. 运行 agentic tree search 做实验
4. 汇总图表和结果
5. 自动写 paper
6. 自动 review

它的核心优势是：生成对象不是“报告文本”，而是“从假设到实验再到论文的完整科研过程”。这让它天然更适合：

- 实证型研究
- 模型改进研究
- 需要代码试验和结果反馈的任务

### 3.2 真正把代码执行纳入生成闭环

README 明确写了：

- 会执行 LLM-written code
- 有 experiment manager agent
- 有 debug depth
- 有 tree visualization

这比本项目强在：生成内容不是停留在语言层，而是进入“代码生成 -> 执行 -> 结果反馈 -> 再生成”的闭环。

本项目虽然有执行引擎 [`backend/app/services/execution_engine.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/execution_engine.py)，但当前主要执行的是：

- 检索
- 证据分析
- 报告生成

不是广义的实验代码探索。换句话说，本项目是“知识工作流执行器”，对方是“科研实验工作流执行器”。

### 3.3 多模型分工更成熟

`launch_scientist_bfts.py` 公开暴露了独立模型参数：

- `model_writeup`
- `model_citation`
- `model_review`
- `model_agg_plots`
- 配置文件中的 `code` / `feedback` / `vlm_feedback`

这说明对方把生成机制拆成了多目标优化：

- 代码生成模型
- 文本写作模型
- 审稿模型
- 图像/图表反馈模型

本项目虽支持不同 provider，但主链路上仍更接近“单一 LLM 路由 + 少量 specialized prompt”。对方的优点是：

- 能针对阶段选最适合模型
- 降低单模型包打天下的失配
- 成本和质量更容易阶段化权衡

### 3.4 原生支持失败恢复，而不是主要依赖 fallback 文本

本项目在 plan 生成和 section 生成里都有 fallback 逻辑，这是实用的，但说明主机制在失败时常回退到“启发式保底文本”。

对方的生成机制更偏：

- 多 draft
- 多 worker
- 多 stage
- debug 重试
- writeup retries

这类设计的优势是：失败恢复仍然尝试保持在“真实搜索空间”内部，而不是快速退化成模板化结果。

### 3.5 中间产物更科研化

对方的公开输出包括：

- idea JSON
- timestamped experiment folder
- tree visualization HTML
- experiment_results
- plots aggregation
- PDF paper
- text review
- image/caption/reference review
- token tracking

本项目输出更偏：

- Markdown 报告
- references / bib
- DAG
- evidence / conflicts

对方优势在于，它的中间产物更适合科研过程审计与复现实验，而不仅是阅读最终结论。

### 3.6 写作不是直接拼章节，而是建立在实验结果之后

本项目写作阶段虽然有章节规划、章节证据选择、审校与重写，但整体仍然是“围绕检索证据写一篇文章”。

`AI-Scientist-v2` 的写作建立在以下更强的基础上：

- 已执行实验
- 已产出图表
- 已进行 citation gathering
- 已有 review / VLM review

所以它的 writeup 不是单纯叙述型生成，而是实验结果驱动的 manuscript generation。这一点在科研场景中是本质优势。

### 3.7 将图表质量纳入生成链路

从 README 和论文摘要可见，对方引入了 VLM feedback loop，用于改进 figures 的内容与美观性。

这比本项目强很多。本项目当前没有真正把：

- 图表审美
- 图表和正文一致性
- caption-ref 对齐

作为原生生成闭环的一部分。对方在论文式交付上明显更完整。

## 4. 路线探索方面的优势

这是 `AI-Scientist-v2` 相对本项目最核心、最明显的优势。

### 4.1 显式 tree search，探索结构比本项目 DAG 扩展更强

本项目的 [`MasterPlanner.build_dag()`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/planner.py#L12) 是一个有界 DAG 生成器，本质特征是：

- BFS + DFS 混合扩展
- 基于 `_seed_topics` / `_expand_topic`
- 用启发式 `infoGainScore` 做简单剪枝
- 受 `maxDepth` / `maxNodes` 强约束

这套机制足够做“研究任务拆解”，但还不是“探索算法”。

对方则明确采用：

- progressive agentic tree search
- best-first tree search 配置
- `num_workers`
- `num_drafts`
- `max_debug_depth`
- `debug_prob`

它的优势在于：

- 搜索空间是实验路线，而不仅是话题子节点
- 节点扩展质量由执行反馈决定，而不只是启发式标题展开
- 可以并行探索多个候选研究方向
- 可以在失败节点上继续 debug，而不是单纯 prune

### 4.2 路线探索依赖真实反馈，不只依赖先验启发式

本项目的路线扩展更多依赖：

- 标题与描述分解
- 关键词 seed
- 预设优先级
- 启发式信息增益

对方的路线探索依赖：

- 代码执行结果
- 实验成败
- debug 可修复性
- 阶段性目标

这意味着它做的是“闭环搜索”，而本项目做的是“静态规划后执行”。

闭环搜索的优势非常明显：

- 能及时放弃无效方向
- 能把资源集中到有效分支
- 能从失败里获得局部改进
- 更适合 open-ended research

### 4.3 原生并行探索多个分支

`bfts_config.yaml` 中有 `num_workers` 和 `num_drafts`。这意味着对方不是只生成一个方案再局部修补，而是天然支持：

- 多个起始草稿
- 多条并行探索路径
- 多个 worker 同时推进

本项目当前虽然也能执行多节点 DAG，但其节点多来自单一计划展开，不是“多候选研究路线并行竞争”。对方的优势是：

- 起始多样性更强
- 更不容易被第一版计划锁死
- 有更大机会发现意外但有效的方向

### 4.4 将 debug 视为搜索动作的一部分

对方配置里有 `max_debug_depth` 和 `debug_prob`。这背后的设计非常重要：

- 失败节点不是立即丢弃
- 系统允许为一个失败分支投入调试预算
- debug 本身被纳入 tree expansion 策略

本项目没有把 debug 作为研究路线探索的一等公民。当前系统更像：

- 规划
- 检索
- 生成
- 失败则 fallback 或结束

而不是：

- 失败
- 诊断
- 局部修改
- 再试
- 选择是否继续保留该分支

对于真正复杂的科研探索，这是一项关键能力差异。

### 4.5 阶段化探索比单层规划更成熟

公开资料显示对方 tree search 是 progressive / staged 的，并带有 experiment manager agent。

这意味着它不是一口气把所有自由度同时打开，而是分阶段推进，例如：

- 初步调查
- 调参
- 研究议程推进
- 消融

即使不展开每个内部实现，单从设计哲学上也明显优于本项目当前的统一式 DAG。

本项目 DAG 更像“一次性把任务拆好”；对方更像“研究管理器根据阶段切换搜索策略”。其优势是：

- 早期广搜，后期精搜更自然
- 不同阶段可使用不同节点类型和评估标准
- 研究路线不容易在初期就过度承诺

### 4.6 可视化树结构提升可审计性

对方公开产物里有 `unified_tree_viz.html`。这说明其路线探索不是黑箱串行日志，而是可视化的搜索树。

这比本项目当前 DAG 可视化更有价值的地方在于：

- 用户能看到被探索过哪些假设和实验分支
- 能看到哪些路径被放弃、为何放弃
- 能看到最终论文是从哪条搜索路径收敛出来的

本项目虽然有 DAG editor / plan editor，但更多是“计划视图”，不是“实验探索历史视图”。

## 5. 研究质量控制方面的优势

### 5.1 novelty checking 更前置

从 README 可见，Semantic Scholar 在 ideation 阶段就用于 novelty 相关检查。

本项目当前检索强在资料获取，但“与既有工作是否重复”没有前置成强机制。对方的优势是：

- 更少走重复路线
- 更少出现已有论文已经覆盖的问题
- 能在想法形成前就做 literature-grounded filtering

### 5.2 review 是原生阶段，不是附属检查

对方写完后还有：

- text review
- image/caption/reference review

本项目虽然也有 review / checking，但当前重心仍然是清洗输出、避免 prompt 泄漏、保证章节质量。对方的 review 更接近“模拟论文审稿场景”，并且交付目标是 workshop-level paper，因此标准更接近论文投稿而不是普通研究报告。

### 5.3 引文收集是单独阶段

`launch_scientist_bfts.py` 暴露了：

- `model_citation`
- `num_cite_rounds`

说明 citation gathering 是独立预算、独立模型、独立回合数的任务。

本项目当前引用生成主要来自证据集合和文章末尾参考文献组织，缺少独立的“引文检索迭代阶段”。对方优势是：

- 引文链更可能完整
- citation 质量不被正文写作阶段吞掉
- 参考文献可以持续补全

### 5.4 结果优先于叙事

对方整个系统的收敛目标是“实验结果能否支撑论文”，而不是“能否生成一篇像样的报告”。

这会带来一个很重要的优势：

- 写作受结果约束，而不是受文风约束

本项目当前在中文写作质量、结构完整性、去污染方面做得不错，但从研究质量控制的角度，对方更强调“结果是否成立”。

## 6. 工程与运行机制方面的优势

### 6.1 工作区隔离更适合高自治实验

对方明确：

- 用独立 workspace
- 会复制数据到 workspace
- 会执行代码
- 强烈建议在受控沙箱运行

这表明它在工程上默认面对的是高风险、高自治执行。相比之下，本项目执行引擎更偏应用内任务编排，风险面较窄。对方在自治实验系统工程上更成熟。

### 6.2 成本、阶段、重试参数暴露得更完整

公开 CLI 和配置可直接调：

- generation 数
- reflection 数
- writeup retries
- cite rounds
- workers
- stage iters
- debug depth

这说明系统的搜索预算、生成预算、审查预算都是显式参数，而不是隐藏在代码内部。其优点是：

- 更易做 ablation
- 更易做成本控制
- 更易做大规模批量实验

### 6.3 token tracking 更系统

`launch_scientist_bfts.py` 里会把 token tracker summary 和 interactions 存盘。

本项目当前没有形成同等粒度的跨阶段 token 审计。对方的优势是：

- 成本归因更容易
- 能分析哪一阶段最贵
- 方便后续优化策略

### 6.4 交付物天然适合论文工作流

对方的最终交付直接面向：

- PDF manuscript
- review outputs
- figures
- citations

本项目当前更偏：

- Markdown 报告
- 对话与计划编辑

对于科研产线，对方交付形态更接近真实学术工作流。

## 7. 逐项列出对方相对本项目的优势

下面给出尽量穷举的扁平列表，便于后续转成 roadmap。

- 更强的目标函数：不是“写一个研究方案”，而是“生成可发表的研究产出”。
- 更强的 novelty 导向：在 ideation 阶段就要求至少一次文献搜索。
- 更强的相关工作约束：prompt 显式要求与现有文献区分。
- 更强的实验可执行性约束：要求给出具体实验、具体算法变化、评估指标。
- 更强的 reflection 机制：一个 idea 会经历多轮自评和 refinement。
- 更强的动作协议：`ACTION/ARGUMENTS` 比单段 Markdown 输出更 agentic。
- 更强的结构化中间产物：idea JSON 比自由文本方案更利于后续自动处理。
- 更强的多模型分工：code / feedback / writeup / citation / review / VLM review 分离。
- 更强的失败恢复：debug、retry、multi-draft，而不是主要依赖 fallback 文本。
- 更强的路线探索：真正做 tree search，不是启发式 DAG 扩展。
- 更强的并行性：多个 workers 和多个 drafts 并行探索。
- 更强的分阶段研究管理：progressive stages 明显优于单层统一规划。
- 更强的分支保留策略：失败分支可继续 debug，而不是直接终止。
- 更强的反馈闭环：实验结果反过来影响后续路线。
- 更强的科研真实性：代码执行、实验结果、图表和论文连成闭环。
- 更强的图表治理：VLM 参与 figure quality 改进。
- 更强的论文式 review：不仅评正文，还评图像、caption、reference。
- 更强的 citation 流水线：引文收集是独立阶段并有独立轮数。
- 更强的实验审计：tree visualization、experiment folder、token tracker 更完整。
- 更强的 reproducibility 倾向：工作区、日志、结果目录分层更适合复现。
- 更强的预算控制：很多关键探索超参数在配置中显式暴露。
- 更强的开放式研究能力：更适合发现新方向，而不只是整理已有资料。
- 更强的 domain generalization 目标：明确强调移除 human-authored templates。
- 更强的结果导向：系统以“论文能否成立”为目标，而不是“文本是否顺畅”为目标。

## 8. 对本项目最值得优先借鉴的点

如果只挑最值得抄的 10 个点，优先级如下：

1. 把“novelty / related work check”前移到计划生成前。
2. 把当前 plan prompt 从“格式约束”升级为“研究质量约束 + 结构化输出”。
3. 引入 `reflection rounds`，让方案在系统内部先做 2 到 5 轮自我修订。
4. 把计划输出改成结构化 schema，而不是 Markdown 为唯一主载体。
5. 把 DAG 扩展升级成“多 draft + 多 worker + 明确评分”的探索机制。
6. 把失败处理从 fallback 文本改成“局部 debug / regenerate / branch repair”。
7. 增加显式 novelty score / differentiation score / feasibility score。
8. 将 citation gathering 独立成单独阶段。
9. 将 figure / table / appendix 生成纳入原生交付链路。
10. 为研究过程增加搜索树或分支历史可视化，而不是只展示静态计划。

## 9. 结论

一句话概括：

`AI-Scientist-v2` 的优势不在于“文案更好”，而在于它把 prompt、生成机制和路线探索都建立在“科研搜索系统”而不是“报告生成系统”的范式上。

相对本项目，它最强的三个优势分别是：

- prompt 更像科研提案与实验设计器，而不是格式化计划生成器；
- 生成机制更像多阶段实验闭环，而不是检索后写作；
- 路线探索更像真实 tree search + debug 搜索，而不是启发式 DAG 拆分。

如果本项目后续要向“更强研究 agent”演化，最应该补的不是 UI，而是：

- 前置 novelty/related-work 检查
- reflection + structured proposal generation
- branch-based exploration and repair

## 10. 依据来源

- `AI-Scientist-v2` README: [GitHub README](https://github.com/SakanaAI/AI-Scientist-v2)
- `AI-Scientist-v2` ideation 入口: [perform_ideation_temp_free.py](https://raw.githubusercontent.com/SakanaAI/AI-Scientist-v2/main/ai_scientist/perform_ideation_temp_free.py)
- `AI-Scientist-v2` 启动入口: [launch_scientist_bfts.py](https://raw.githubusercontent.com/SakanaAI/AI-Scientist-v2/main/launch_scientist_bfts.py)
- `AI-Scientist-v2` 搜索配置: [bfts_config.yaml](https://raw.githubusercontent.com/SakanaAI/AI-Scientist-v2/main/bfts_config.yaml)
- `AI-Scientist-v2` 论文摘要页: [Hugging Face Papers](https://huggingface.co/papers/2504.08066)
- 本项目计划生成: [`backend/app/services/conversation_agent.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/conversation_agent.py)
- 本项目 DAG 规划: [`backend/app/services/planner.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/planner.py)
- 本项目执行引擎: [`backend/app/services/execution_engine.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/execution_engine.py)
- 本项目写作服务: [`backend/app/services/writer.py`](/Users/xcy/Program/SH-Program/Deep-Research/backend/app/services/writer.py)

