from __future__ import annotations


def build_novelty_system_prompt() -> str:
    return (
        "你是一名研究新颖性评审 Agent。请评估 idea 是否足够新颖且可执行。"
        "输出必须是 JSON，不要输出解释。"
        'JSON 形状固定为：{"summary":"","noveltyScore":0.0,"isNovel":true,'
        '"similarWork":[],"differentiationNotes":[],"feasibilitySummary":"","feasibilityScore":0.0,'
        '"isFeasible":true,"blockers":[],"assumptions":[]}.'
    )


def build_novelty_user_prompt(*, topic: str, idea_json: str, evidence_snippets: str) -> str:
    return (
        f"主题：{topic}\n"
        f"候选 idea JSON：\n{idea_json}\n\n"
        f"相关证据与工作线索：\n{evidence_snippets or '- 暂无'}\n\n"
        "请识别该 idea 与已有工作的重叠、差异、不新颖风险，以及可执行性阻碍。"
    )

