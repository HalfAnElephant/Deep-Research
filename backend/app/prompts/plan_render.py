from __future__ import annotations


def build_plan_render_system_prompt() -> str:
    return (
        "你是研究计划渲染 Agent。请把结构化研究 idea 渲染成可执行 Markdown 研究方案。"
        "输出必须是完整 Markdown，并包含 front matter。不要输出额外解释。"
    )


def build_plan_render_user_prompt(*, topic: str, config_summary: str, idea_json: str) -> str:
    return (
        f"主题：{topic}\n"
        f"配置：{config_summary}\n"
        f"结构化 idea：\n{idea_json}\n\n"
        "请输出包含 front matter 的完整研究计划，正文至少覆盖：研究目标、研究问题拆解、"
        "方法与来源、执行步骤、风险与边界、交付标准。"
    )
