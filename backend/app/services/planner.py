from __future__ import annotations

from collections import deque
import re

from app.core.utils import new_id, now_iso
from app.models.schemas import DAGGraph, DAGEdge, NodeStatus, TaskConfig, TaskMetadata, TaskNode, WritingSectionPlan
from app.services.research_plan_generator import research_plan_generator


class MasterPlanner:
    """Builds a bounded DAG with LLM-generated structured research questions."""

    def build_dag(self, root_task_id: str, title: str, description: str, config: TaskConfig) -> DAGGraph:
        """Build DAG using LLM-generated structured research plan."""
        ts = now_iso()

        # Generate structured research plan using LLM
        try:
            plan = research_plan_generator.generate(
                topic=title,
                description=description,
                config=config,
            )
            return self._build_dag_from_plan(root_task_id, title, description, plan, config, ts)
        except Exception:
            # Fallback to template-based generation
            return self._build_dag_fallback(root_task_id, title, description, config, ts)

    def _build_dag_from_plan(
        self,
        root_task_id: str,
        title: str,
        description: str,
        plan,
        config: TaskConfig,
        ts: str,
    ) -> DAGGraph:
        """Convert structured research plan to DAG format."""
        nodes: list[TaskNode] = []
        edges: list[DAGEdge] = []
        question_to_task: dict[str, str] = {}

        # Map question IDs to task IDs
        for question_id in plan.all_questions:
            question_to_task[question_id] = new_id()

        # Root task ID mapping
        root_question = plan.root_question
        question_to_task[root_question.question_id] = root_task_id

        # Create TaskNode for each research question
        for question_id, question in plan.all_questions.items():
            task_id = question_to_task[question_id]

            # Calculate priority based on level (deeper = lower priority)
            priority = max(1, config.priority - question.level)

            # Determine status based on level
            status = NodeStatus.PENDING

            node = TaskNode(
                taskId=task_id,
                parentTaskId=question_to_task.get(
                    question.parent_id) if question.parent_id else None,
                title=question.title,
                description=question.description,
                status=status,
                priority=priority,
                dependencies=[question_to_task[question.parent_id]
                              ] if question.parent_id else [],
                children=[question_to_task[cid] for cid in question.children],
                metadata=TaskMetadata(
                    estimatedTokenCost=800 + question.level * 200,
                    searchDepth=question.level,
                    infoGainScore=1.0 - (question.level * 0.15),
                    branchId=question.parent_id or root_question.question_id,
                    branchScore=max(0.0, 1.0 - (question.level * 0.15)),
                    branchDepth=question.level,
                    createdAt=ts,
                    updatedAt=ts,
                ),
                output=[],
            )
            nodes.append(node)

        # Create edges based on parent-child relationships
        for question_id, question in plan.all_questions.items():
            source_id = question_to_task[question_id]
            for child_id in question.children:
                target_id = question_to_task.get(child_id)
                if target_id:
                    edges.append(DAGEdge.model_validate({
                        "from": source_id,
                        "to": target_id,
                    }))

        return DAGGraph(nodes=nodes, edges=edges)

    def _build_dag_fallback(
        self,
        root_task_id: str,
        title: str,
        description: str,
        config: TaskConfig,
        ts: str,
    ) -> DAGGraph:
        """Fallback DAG generation when LLM fails."""
        root = TaskNode(
            taskId=root_task_id,
            parentTaskId=None,
            title=title,
            description=description,
            status=NodeStatus.PENDING,
            priority=config.priority,
            dependencies=[],
            children=[],
            metadata=TaskMetadata(
                estimatedTokenCost=0,
                searchDepth=0,
                infoGainScore=1.0,
                branchId="root",
                branchScore=1.0,
                branchDepth=0,
                createdAt=ts,
                updatedAt=ts,
            ),
            output=[],
        )
        first_topics = self._seed_topics(title, description)
        nodes = [root]
        edges: list[DAGEdge] = []
        q: deque[tuple[TaskNode, int]] = deque([(root, 0)])
        total_nodes = 1

        while q and total_nodes < config.maxNodes:
            parent, depth = q.popleft()
            if depth >= config.maxDepth:
                continue
            candidates = first_topics if depth == 0 else self._expand_topic(
                parent.title, description, depth)
            for ctitle in candidates:
                if total_nodes >= config.maxNodes:
                    break
                node_id = new_id()
                node = TaskNode(
                    taskId=node_id,
                    parentTaskId=parent.taskId,
                    title=ctitle,
                    description=f"{ctitle}: {description}",
                    status=NodeStatus.PENDING,
                    priority=max(1, config.priority - depth),
                    dependencies=[parent.taskId],
                    children=[],
                    metadata=TaskMetadata(
                        estimatedTokenCost=800 + depth * 200,
                        searchDepth=depth + 1,
                        infoGainScore=0.5,
                        branchId=parent.taskId,
                        branchScore=max(0.0, 0.75 - ((depth + 1) * 0.1)),
                        branchDepth=depth + 1,
                        createdAt=ts,
                        updatedAt=ts,
                    ),
                    output=[],
                )
                nodes.append(node)
                parent.children.append(node_id)
                edges.append(DAGEdge.model_validate(
                    {"from": parent.taskId, "to": node_id}))
                total_nodes += 1
                q.append((node, depth + 1))

        return DAGGraph(nodes=nodes, edges=edges)

    def build_report_sections(
        self,
        *,
        title: str,
        description: str,
        research_sections: list[tuple[str, str]],
        max_sections: int = 5,
    ) -> list[tuple[str, str]]:
        writing_plan = self.build_writing_plan(
            title=title,
            description=description,
            research_sections=research_sections,
            max_sections=max_sections,
        )
        return [
            (section.sectionId, f"{section.heading}\n\n{section.brief}")
            for section in writing_plan
        ]

    def build_writing_plan(
        self,
        *,
        title: str,
        description: str,
        research_sections: list[tuple[str, str]],
        max_sections: int = 5,
    ) -> list[WritingSectionPlan]:
        """Convert research nodes into a writing-oriented section plan.

        The DAG is useful for retrieval, but the writer needs a stable article
        outline with clear blocks. This method bridges that gap.
        """
        normalized_topics: list[tuple[str, str]] = []
        seen_labels: set[str] = set()

        for section_id, raw_text in research_sections:
            heading, detail = self._split_section_text(raw_text)
            label = self._normalize_report_label(heading, title)
            if not label or label in seen_labels:
                continue
            seen_labels.add(label)
            brief = detail or f"围绕“{label}”补足证据、机制、影响和适用边界。"
            normalized_topics.append((section_id, f"{label}\n\n{brief}"))

        selected_topics = normalized_topics[: max(1, max_sections - 3)]
        section_plan: list[WritingSectionPlan] = [
            WritingSectionPlan(
                sectionId="report-intro",
                heading="引言与问题界定",
                brief=(
                    f"围绕“{title}”说明研究目标、分析边界、核心判断标准与读者需要先把握的问题。"
                    f"结合任务背景“{description[:220]}”交代文章为何这样组织。"
                ),
                sourceNodeIds=[],
                priority=10,
                requiredEvidenceCount=1,
            )
        ]

        if selected_topics:
            section_plan.extend(
                WritingSectionPlan(
                    sectionId=section_id,
                    heading=self._split_section_text(raw_text)[0],
                    brief=self._split_section_text(raw_text)[1],
                    sourceNodeIds=[section_id],
                    priority=max(2, 9 - index),
                    requiredEvidenceCount=2,
                )
                for index, (section_id, raw_text) in enumerate(selected_topics, start=1)
            )
        else:
            fallback_topics = [
                WritingSectionPlan(
                    sectionId="report-evidence",
                    heading="关键证据与现状",
                    brief=f"围绕“{title}”梳理现有证据、主要趋势和已形成的共识。",
                    sourceNodeIds=[],
                    priority=8,
                    requiredEvidenceCount=2,
                ),
                WritingSectionPlan(
                    sectionId="report-analysis",
                    heading="争议、机制与边界",
                    brief=f"分析“{title}”中的关键分歧、驱动机制和结论适用边界。",
                    sourceNodeIds=[],
                    priority=7,
                    requiredEvidenceCount=2,
                ),
            ]
            section_plan.extend(fallback_topics[: max(1, max_sections - 3)])

        section_plan.append(
            WritingSectionPlan(
                sectionId="report-synthesis",
                heading="综合分析与风险边界",
                brief=f"跨板块整合“{title}”的证据链、主要争议、限制条件与潜在风险，给出更稳健的综合判断。",
                sourceNodeIds=[
                    section.sectionId for section in section_plan if section.sourceNodeIds],
                priority=3,
                requiredEvidenceCount=2,
            )
        )
        section_plan.append(
            WritingSectionPlan(
                sectionId="report-conclusion",
                heading="结论与建议",
                brief=f"总结“{title}”的核心结论，提出可执行动作、优先级和实施前提。",
                sourceNodeIds=[],
                priority=2,
                requiredEvidenceCount=1,
            )
        )
        return section_plan[:max(4, min(max_sections, len(section_plan)))]

    @staticmethod
    def _seed_topics(title: str, description: str) -> list[str]:
        source = f"{title}。{description}"
        fragments = [
            part.strip("：:;；，,。 ")
            for part in re.split(r"[\n。；;，,]+", source)
            if part.strip()
        ]
        candidates: list[str] = []
        for fragment in fragments:
            cleaned = re.sub(r"^(围绕|关于|研究|请|执行|输出)", "", fragment).strip()
            if 4 <= len(cleaned) <= 28:
                candidates.append(cleaned)
            if len(candidates) >= 4:
                break

        if len(candidates) >= 3:
            return candidates[:4]

        focus = title.strip() or "研究主题"
        fallbacks = [
            f"{focus}的核心问题",
            f"{focus}的关键证据",
            f"{focus}的争议与边界",
            f"{focus}的落地条件",
        ]
        merged: list[str] = []
        for item in candidates + fallbacks:
            if item not in merged:
                merged.append(item)
        return merged[:4]

    @staticmethod
    def _split_section_text(raw_text: str) -> tuple[str, str]:
        parts = [part.strip() for part in raw_text.split("\n\n", 1)]
        heading = parts[0].splitlines()[0].strip(
        ) if parts and parts[0].strip() else ""
        heading = MasterPlanner._sanitize_section_heading(heading)
        detail = parts[1].strip() if len(parts) > 1 else raw_text.strip()
        detail = MasterPlanner._sanitize_section_brief(detail)
        return heading, detail

    @staticmethod
    def _sanitize_section_brief(raw_brief: str, max_length: int = 2000) -> str:
        brief = raw_brief.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not brief:
            return ""

        # Remove fenced code blocks that often leak from malformed LLM output.
        brief = re.sub(r"```[\s\S]*?```", " ", brief)
        brief = brief.replace("```", " ")
        brief = re.sub(r"[ \t]+", " ", brief)
        brief = re.sub(r"\n{3,}", "\n\n", brief).strip()

        if len(brief) <= max_length:
            return brief

        truncated = brief[:max_length].rstrip()
        if len(truncated) >= 3:
            truncated = truncated[:-3].rstrip() + "..."
        return truncated

    @staticmethod
    def _normalize_report_label(raw_label: str, title: str) -> str:
        label = MasterPlanner._sanitize_section_heading(raw_label)
        label = label.strip().strip("：:;；，,。 ")
        if not label:
            return ""
        label = re.sub(r"^(围绕|关于|研究|请|执行|输出)", "", label).strip()
        label = re.sub(r"[：:]?\s*```(?:yaml|yml)?\s*$", "",
                       label, flags=re.IGNORECASE).strip()
        label = re.sub(
            r"：(?:证据补充|关键分歧|适用边界|实施路径|验证方法|风险控制|案例线索|约束条件|后续问题)$", "", label)
        if label == title.strip():
            return f"{title}的关键议题"
        if len(label) > 24:
            label = label[:24].rstrip("：:;；，,。 ")
        return label

    @staticmethod
    def _sanitize_section_heading(raw_heading: str) -> str:
        heading = raw_heading.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not heading:
            return ""
        heading = heading.splitlines()[0].strip().lstrip("#").strip()
        heading = re.sub(r"^[`\-]+|[`\-]+$", "", heading).strip()
        heading = re.sub(r"[：:]?\s*```(?:yaml|yml)?\s*$",
                         "", heading, flags=re.IGNORECASE).strip()
        if heading in {"```", "```yaml", "```yml", "---"}:
            return ""
        return heading

    @staticmethod
    def _expand_topic(parent_title: str, description: str, depth: int) -> list[str]:
        suffix_groups = [
            ("证据补充", "关键分歧", "适用边界"),
            ("实施路径", "验证方法", "风险控制"),
            ("案例线索", "约束条件", "后续问题"),
        ]
        suffixes = suffix_groups[min(depth - 1, len(suffix_groups) - 1)]
        description_focus = description.strip().splitlines()[
            0][:20] if description.strip() else ""
        candidates = [f"{parent_title}：{suffix}" for suffix in suffixes]
        if description_focus:
            candidates.append(f"{parent_title}：{description_focus}")
        deduped: list[str] = []
        for item in candidates:
            if item not in deduped:
                deduped.append(item)
        return deduped[:4]
