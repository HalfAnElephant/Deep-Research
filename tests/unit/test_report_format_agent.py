from app.services.agents import ReportFormatAgent


def test_report_format_agent_detects_speech() -> None:
    agent = ReportFormatAgent()
    blueprint = agent.design_blueprint(
        task_title="AI 安全趋势演讲",
        task_description="请输出一份面向技术大会的演讲稿，强调落地建议。",
    )
    assert blueprint.output_format == "演讲稿"
    assert "开场" in blueprint.section_titles


def test_report_format_agent_detects_custom_format() -> None:
    agent = ReportFormatAgent()
    blueprint = agent.design_blueprint(
        task_title="量子计算入门",
        task_description="输出形式：内部备忘录；简明说明机会与风险。",
    )
    assert blueprint.output_format == "内部备忘录"
    assert blueprint.section_titles == ["开篇", "主体", "结论"]
