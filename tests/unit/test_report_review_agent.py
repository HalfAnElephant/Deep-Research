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
    result = reviewer.review(body=body, blueprint=blueprint, evidences=[
                             _build_evidence("e1")])
    assert not result.approved
    assert any("中间过程痕迹" in issue for issue in result.issues)
    assert any("占位检索文本" in issue for issue in result.issues)


class _StubWriter:
    def __init__(self) -> None:
        self.final_body = ""
        self.final_title = ""
        self.rewrite_called = False

    def generate_body(self, **kwargs) -> str:  # noqa: ANN003
        _ = kwargs
        return """## 引言

围绕多智能体工程可靠性评估，正文首先说明研究对象、关键边界和评估场景，并引用 [evidence:e1] 作为第一组证据支持。这一段落刻意写得较长，以满足审稿器对正文长度和信息密度的要求，同时避免占位检索文本和中间调试痕迹泄露。

进一步来看，系统部署中的失败模式、人工接管成本和验证口径差异共同决定了结论是否可迁移，因此需要把评估条件与结论适用边界一并写清楚，而不是只给出抽象判断或口号式总结 [evidence:e2]。

## 证据与争议

现有证据显示，多智能体系统在复杂工程流程中确实可以改善任务分解与并行处理效率，但同时也会放大协调链路、共享上下文和错误传播带来的不确定性，因此不能把性能提升简单等同于稳定性提升 [evidence:e1]。

不同研究在实验设置、评估任务和人工审核深度上的差异，会导致结论呈现明显分歧。写作时必须把这种分歧转化为可解释的争议结构，而不是把互相冲突的结果机械拼接在一起 [evidence:e2]。

## 综合分析

如果把可靠性问题拆解为任务理解、代理协同、工具调用和人工复核四个环节，可以看到多数风险并非来自单一模型能力不足，而是来自多环节之间缺少稳定的校验与回退机制。这要求报告给出过程级别的治理建议 [evidence:e1]。

综合证据后可以形成更稳健的判断：多智能体架构适合用于高可并行、可审计、可回滚的研究任务，但在高风险决策场景中仍需保留明确的人类把关角色和异常处置流程 [evidence:e2]。

## 结论

因此，文章结论不能停留在“是否值得使用”的二元判断，而应进一步回答在哪些条件下可以使用、需要什么样的验证标准，以及哪些前提缺失时必须停止自动化扩展 [evidence:e1]。

这类写法既保留了证据驱动的结构，也避免了模板化句式，有助于让最终报告更接近真正的人类研究写作成果 [evidence:e2]。
"""

    def generate_title(self, **kwargs) -> str:  # noqa: ANN003
        _ = kwargs
        return "多智能体工程可靠性的证据评估与治理边界"

    def rewrite_body(self, **kwargs) -> str:  # noqa: ANN003
        _ = kwargs
        self.rewrite_called = True
        return self.generate_body()

    def write_report(self, *, report_body: str | None = None, **kwargs):  # noqa: ANN003, ANN201
        self.final_title = kwargs.get(
            "article_title") or kwargs.get("task_title") or ""
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
    assert stub_writer.final_title == "多智能体工程可靠性的证据评估与治理边界"

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


def test_report_agent_fails_without_template_fallback() -> None:
    class _EmptyWriter(_StubWriter):
        def generate_body(self, **kwargs) -> str:  # noqa: ANN003
            _ = kwargs
            return ""

    report_agent = ReportAgent(
        writer_service=_EmptyWriter(), max_review_rounds=1)
    evidences = [_build_evidence("e1")]
    try:
        report_agent.generate_report(
            task_id="t1",
            task_title="多智能体工程可靠性评估",
            task_description="请输出研究报告。",
            sections=[("n1", "问题界定\n说明研究边界")],
            evidences=evidences,
            locked_sections=set(),
        )
    except ValueError as exc:
        assert "停止输出模板化兜底内容" in str(exc)
    else:
        raise AssertionError("expected ValueError when body generation fails")


def test_report_agent_auto_rewrites_when_sections_too_few() -> None:
    class _RewriteWriter(_StubWriter):
        def __init__(self) -> None:
            super().__init__()
            self.generate_calls = 0

        def generate_body(self, **kwargs) -> str:  # noqa: ANN003
            _ = kwargs
            self.generate_calls += 1
            if self.generate_calls == 1:
                return """## 引言

第一段说明主题边界，并引用 [evidence:e1]。

第二段补充背景，但整篇仍然只有两个章节 [evidence:e2]。

## 结论

结论段落给出初步判断 [evidence:e1]。

第二段说明需要补充验证 [evidence:e2]。
"""
            return super().generate_body(**kwargs)

        def rewrite_body(self, **kwargs) -> str:  # noqa: ANN003
            self.rewrite_called = True
            return super().generate_body(**kwargs)

    writer = _RewriteWriter()
    report_agent = ReportAgent(writer_service=writer, max_review_rounds=2)
    evidences = [_build_evidence("e1"), _build_evidence("e2")]

    report_agent.generate_report(
        task_id="t1",
        task_title="多智能体工程可靠性评估",
        task_description="请输出研究报告，强调结论可信与可执行建议。",
        sections=[
            ("s1", "引言与问题界定\n\n说明研究范围"),
            ("s2", "证据与争议\n\n比较主要分歧"),
            ("s3", "综合分析\n\n整合证据链"),
            ("s4", "结论与建议\n\n给出行动建议"),
        ],
        evidences=evidences,
        locked_sections=set(),
    )

    assert writer.rewrite_called
    assert writer.final_body.count("## ") >= 3
