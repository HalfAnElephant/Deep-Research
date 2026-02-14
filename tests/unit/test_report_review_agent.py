from app.models.schemas import Evidence, EvidenceMetadata, ExtractedData, SourceType
from app.services.agents import ReportAgent, ReportFormatAgent, ReportReviewAgent
from app.services.writer import ReportBlueprint


def _build_evidence(evidence_id: str) -> Evidence:
    return Evidence(
        id=evidence_id,
        taskId="t1",
        nodeId="n1",
        sourceType=SourceType.PAPER,
        url=f"https://example.org/{evidence_id}",
        content=f"可信研究摘要 {evidence_id}：讨论多智能体系统在工程场景中的可靠性边界与验证方法。",
        metadata=EvidenceMetadata(
            authors=["Alice"],
            publishDate="2024-01-01T00:00:00Z",
            title=f"Paper {evidence_id}",
            abstract="",
            impactFactor=2.0,
            isPeerReviewed=True,
            relevanceScore=0.8,
            citationCount=10,
        ),
        score=0.8,
        extractedData=ExtractedData(),
    )


def test_report_review_agent_detects_trace_and_placeholder() -> None:
    reviewer = ReportReviewAgent()
    blueprint = ReportBlueprint(
        output_format="研究报告",
        objective="测试",
        tone="客观",
        section_titles=["摘要", "背景"],
    )
    body = """## Trace Section 3
挑战识别
挑战识别: 有关罗素悖论的背景、过程
arXiv result for challenge identification
"""
    result = reviewer.review(body=body, blueprint=blueprint, evidences=[_build_evidence("e1")])
    assert not result.approved
    assert any("中间过程痕迹" in issue for issue in result.issues)
    assert any("占位检索文本" in issue for issue in result.issues)


class _StubWriter:
    def __init__(self) -> None:
        self.final_body = ""

    def generate_body(self, **kwargs) -> str:  # noqa: ANN003
        _ = kwargs
        return """## Trace Section 3
挑战识别
挑战识别: 有关罗素悖论的背景、过程
arXiv result for challenge identification
"""

    def generate_template_body(
        self,
        *,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint | None = None,
    ) -> str:
        _ = (task_title, sections)
        selected = blueprint or ReportBlueprint(
            output_format="研究报告",
            objective="测试",
            tone="客观",
            section_titles=["摘要", "背景", "关键发现", "分析", "风险与局限", "结论与建议"],
        )
        ref_line = "、".join(f"[evidence:{ev.id}]" for ev in evidences[:2])
        lines = ["## 输出格式", "体裁：研究报告", "目标：形成可信结论", "风格：客观严谨", ""]
        for title in selected.section_titles:
            lines.append(f"## {title}")
            lines.append(
                f"围绕“{task_title}”进行结构化分析，本节结合来源证据 {ref_line}，"
                "分别从问题界定、影响范围、驱动机制与可执行策略四个角度展开，"
                "确保结论可以被复核而非停留在抽象判断。"
            )
            lines.append(
                "证据解释需要同时说明支持结论的依据与不确定性来源，"
                "例如样本规模、时间窗口、外部变量变化和场景迁移成本，"
                "并给出后续补证方向与优先级，避免单点证据导致的过拟合判断。"
            )
            lines.append(
                "落地层面应拆分短中期动作、责任角色与评估指标，"
                "形成可执行闭环，并通过复盘机制持续校准假设与风险边界。"
            )
            lines.append(
                "评估计划应明确量化指标（如缺陷率、延迟、回滚率与人工干预成本）及验收阈值，"
                "并预设A/B对照与异常告警流程，以便在不同业务负载下验证结论的稳定性。"
            )
            lines.append("")
        return "\n".join(lines)

    def write_report(self, *, report_body: str | None = None, **kwargs):  # noqa: ANN003, ANN201
        _ = kwargs
        self.final_body = report_body or ""
        return "mock.md", "mock.bib", {}


def test_report_agent_revision_loop_produces_approved_body() -> None:
    stub_writer = _StubWriter()
    report_agent = ReportAgent(writer_service=stub_writer, max_review_rounds=2)
    evidences = [_build_evidence("e1"), _build_evidence("e2")]
    report_agent.generate_report(
        task_id="t1",
        task_title="多智能体工程可靠性评估",
        task_description="请输出研究报告，强调结论可信与可执行建议。",
        sections=[("n1", "挑战识别\n梳理背景和技术边界")],
        evidences=evidences,
        locked_sections=set(),
    )

    assert "Trace Section" not in stub_writer.final_body
    assert "挑战识别:" not in stub_writer.final_body
    assert "arXiv result for" not in stub_writer.final_body

    blueprint = ReportFormatAgent().design_blueprint(
        task_title="多智能体工程可靠性评估",
        task_description="请输出研究报告，强调结论可信与可执行建议。",
    )
    review_result = ReportReviewAgent().review(
        body=stub_writer.final_body,
        blueprint=blueprint,
        evidences=evidences,
    )
    assert review_result.approved
