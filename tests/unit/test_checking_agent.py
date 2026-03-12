from app.services.four_agents.checking_agent import CheckingAgent


def test_checking_agent_word_count_excludes_references() -> None:
    agent = CheckingAgent()
    body = "# 标题\n\n## 引言\n\n" + ("正文字数" * 180)
    references = "\n\n## 参考文献\n\n" + ("[1] 参考资料\n" * 200)

    issues = agent._check_structure(body + references)  # noqa: SLF001

    assert any("文章内容过短" in issue.description for issue in issues)


def test_checking_agent_strips_reference_section_for_structure() -> None:
    agent = CheckingAgent()
    content = (
        "# 标题\n\n"
        "## 引言\n\n"
        "这是引言。\n\n"
        "## 分析\n\n"
        "这是分析。\n\n"
        "## 参考文献\n\n"
        "[1] 某文献\n"
    )

    stripped = agent._strip_reference_section(content)  # noqa: SLF001

    assert "## 参考文献" not in stripped
    assert stripped.endswith("这是分析。")
