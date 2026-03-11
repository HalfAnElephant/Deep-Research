from app.models.schemas import TaskConfig
from app.services.planner import MasterPlanner


def test_planner_generates_bounded_dag() -> None:
    planner = MasterPlanner()
    dag = planner.build_dag("root", "Root", "desc", TaskConfig(
        maxDepth=3, maxNodes=20, priority=3))
    assert len(dag.nodes) <= 20
    assert dag.nodes[0].taskId == "root"
    assert all(node.metadata.searchDepth <= 3 for node in dag.nodes)


def test_planner_generates_acyclic_edges() -> None:
    planner = MasterPlanner()
    dag = planner.build_dag("root", "Root", "desc", TaskConfig(
        maxDepth=2, maxNodes=10, priority=3))
    edges = {(edge.from_, edge.to) for edge in dag.edges}
    reverse = {(dst, src) for src, dst in edges}
    assert not edges.intersection(reverse)


def test_planner_generates_topic_specific_nodes() -> None:
    planner = MasterPlanner()
    dag = planner.build_dag(
        "root",
        "多智能体工程可靠性评估",
        "需要关注证据、争议和治理边界",
        TaskConfig(maxDepth=2, maxNodes=10, priority=3),
    )
    child_titles = [node.title for node in dag.nodes[1:5]]
    assert child_titles
    assert any(
        "多智能体工程可靠性评估" in title or "证据" in title or "争议" in title for title in child_titles)
    assert child_titles[:3] != ["背景研究", "现状分析", "挑战识别"]


def test_planner_builds_report_sections_for_writing() -> None:
    planner = MasterPlanner()
    report_sections = planner.build_report_sections(
        title="多智能体工程可靠性评估",
        description="需要关注证据质量、争议来源和治理边界",
        research_sections=[
            ("n1", "多智能体工程可靠性评估的关键证据\n\n梳理基准测试和失败案例"),
            ("n2", "多智能体工程可靠性评估：关键分歧\n\n比较不同评估口径"),
        ],
    )
    headings = [text.splitlines()[0] for _, text in report_sections]
    assert len(report_sections) >= 4
    assert headings[0] == "引言与问题界定"
    assert headings[-1] == "结论与建议"
    assert any("关键证据" in heading or "关键议题" in heading for heading in headings)


def test_planner_builds_explicit_writing_plan() -> None:
    planner = MasterPlanner()
    writing_plan = planner.build_writing_plan(
        title="多智能体工程可靠性评估",
        description="需要关注证据质量、争议来源和治理边界",
        research_sections=[
            ("n1", "多智能体工程可靠性评估的关键证据\n\n梳理基准测试和失败案例"),
            ("n2", "多智能体工程可靠性评估：关键分歧\n\n比较不同评估口径"),
        ],
    )

    assert len(writing_plan) >= 4
    assert writing_plan[0].heading == "引言与问题界定"
    assert writing_plan[-1].heading == "结论与建议"
    assert any(section.sourceNodeIds for section in writing_plan[1:-2])
    assert all(section.sectionId for section in writing_plan)


def test_planner_sanitizes_yaml_polluted_heading() -> None:
    planner = MasterPlanner()
    writing_plan = planner.build_writing_plan(
        title="地府货币体系",
        description="关注历史演变与民俗本源",
        research_sections=[
            ("n1", "历史演变与民俗本源: ```yaml\n\n梳理起源与流变"),
            ("n2", "仪式实践\n\n比较不同地区做法"),
        ],
    )

    headings = [section.heading for section in writing_plan]
    assert all("```yaml" not in heading for heading in headings)
    assert any("历史演变与民俗本源" in heading for heading in headings)
