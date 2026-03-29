from __future__ import annotations


def build_ideation_system_prompt(*, num_ideas: int, num_reflections: int) -> str:
    return (
        "你是一名研究构思 Agent。请围绕用户主题提出结构化研究想法，"
        "输出必须是 JSON，不要输出 Markdown 或解释。\n"
        f"请至少生成 {num_ideas} 个候选 idea，并在内部做 {num_reflections} 轮自我检查。\n"
        "每个 idea 必须包含：title, problemStatement, shortHypothesis, abstract, "
        "relatedWork, differentiators, experimentProposals, riskFactors, limitations。\n"
        "relatedWork 必须是数组；experimentProposals 必须包含 title/objective/method/metrics/expectedOutcome；"
        "riskFactors 必须包含 risk/severity/mitigation。\n"
        '最终 JSON 形状固定为：{"ideas":[...]}。'
    )


def build_ideation_user_prompt(
    *,
    topic: str,
    search_sources: list[str],
    evidence_snippets: str,
) -> str:
    return (
        f"研究主题：{topic}\n"
        f"可用检索源：{', '.join(search_sources) or '无'}\n"
        "请基于主题和已有线索提出多个具有区分度的候选研究 idea。\n"
        "每个 idea 需要说明与现有工作的差异、核心假设、实验或验证方式，以及主要风险。\n"
        f"首轮参考证据：\n{evidence_snippets or '- 暂无外部证据，需基于主题做保守构思。'}"
    )

