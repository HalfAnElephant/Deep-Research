from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import httpx

from app.core.config import settings
from app.models.schemas import Citation, Evidence, ReportDraft, SectionDraft, WritingSectionPlan

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportBlueprint:
    output_format: str
    objective: str
    tone: str
    section_titles: list[str]


@dataclass(frozen=True)
class SectionOutline:
    key: str
    heading: str
    brief: str
    source_node_ids: list[str]
    required_evidence_count: int = 2


class WriterService:
    """研究文章写作服务，支持分离导出文章和引用列表。"""

    FRONT_MATTER_PATTERN = re.compile(
        r"^---\s*\n(?P<header>[\s\S]*?)\n---\s*(?:\n|$)",
        re.MULTILINE,
    )
    MARKDOWN_FENCE_WRAPPER_PATTERN = re.compile(
        r"^```(?:markdown|md)\s*\n(?P<body>[\s\S]*?)\n```\s*$",
        re.IGNORECASE,
    )
    URL_PATTERN = re.compile(r"https?://\S+")
    PLACEHOLDER_TITLE_PATTERN = re.compile(
        r"(?i)(^\[mock\]|result\s+for|synthetic evidence|semantic scholar result|arxiv result|web result)"
    )
    # 需要过滤的内部标记模式
    INTERNAL_MARKERS_PATTERN = re.compile(
        r"(_taskId:\s*\S+_)"
        r"|(\#\#\s*AI\s*综合解读)"
        r"|(\#\#\s*输出格式)"
        r"|(\#\#\s*Trace\s*Section)"
        r"|(\[locked\])"
    )
    UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")
    ARTICLE_TITLE_BLACKLIST = re.compile(r"(?i)(研究计划|执行步骤|风险与边界|交付标准)")
    GARBLED_PATTERNS = (
        re.compile(r"\\u[0-9a-fA-F]{4}"),
        re.compile(r"publishsource|srsltid|download\?etag=", re.IGNORECASE),
        re.compile(r"(?:_F10_|ͬ˳|ǵ\(|51sjsj|cnki ai阅读)", re.IGNORECASE),
    )
    META_COMMENTARY_PATTERNS = (
        re.compile(r"当前提供的证据列表与.+?研究主题.+?不相关"),
        re.compile(r"无法为本章节的撰写提供有效支持"),
        re.compile(r"本章节的撰写将无法依赖当前提供的证据材料"),
        re.compile(r"必须依据研究计划中预设的.+?进行独立论述"),
        re.compile(r"当前未检索到可用于.+?的有效证据"),
        re.compile(r"为了完成.+?这一章节"),
    )
    META_HEADING_PATTERNS = (
        re.compile(r"^\s*##\s*```(?:yaml|yml)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*```(?:yaml|yml)?\s*$", re.IGNORECASE),
        re.compile(r"^\s*---\s*$"),
        re.compile(r"^\s*研究问题[:：].*```(?:yaml|yml)?\s*$", re.IGNORECASE),
    )

    def __init__(self, output_dir: str = "backend/.data/reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_report(
        self,
        *,
        task_id: str,
        task_title: str,
        article_title: str | None = None,
        task_description: str = "",
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        locked_sections: set[str] | None = None,
        blueprint: ReportBlueprint | None = None,
        report_body: str | None = None,
    ) -> tuple[str, str, dict[str, Citation]]:
        """生成研究文章和引用列表两个独立的文件。

        Returns:
            tuple[str, str, dict]: (文章路径, 引用列表路径, 引用映射)
        """
        _ = locked_sections
        blueprint = blueprint or self._default_blueprint()
        citation_map = self._build_citations(evidences)

        # 创建 evidence_id 到引用编号的映射
        evidence_to_index = {ev_id: idx + 1 for idx,
                             ev_id in enumerate(citation_map.keys())}

        if report_body is None:
            generated_body = self.generate_body(
                task_title=task_title,
                task_description=task_description,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
            )
        else:
            generated_body = report_body

        # 过滤内部标记与计划/代码围栏污染，确保输出的是文章正文。
        clean_body = self._strip_internal_markers(generated_body)
        clean_body, _ = self._sanitize_markdown_output(clean_body)

        # 将 [evidence:xxx] 替换为标准引用编号 [1], [2], ...
        clean_body = self._replace_evidence_refs(clean_body, evidence_to_index)

        display_title = self._sanitize_article_title(
            article_title or task_title, fallback=task_title)

        # 生成文章文件（纯内容，引用在文末）
        article_lines = [f"# {display_title}", ""]
        article_lines.extend(clean_body.splitlines())
        article_lines.append("")
        article_lines.append("## 参考文献")
        for ev_id, c in citation_map.items():
            idx = evidence_to_index.get(ev_id, 0)
            article_lines.append(
                f"[{idx}] {', '.join(c.authors)} ({c.year}). {c.title}. {c.url}")

        article_path = self.output_dir / f"{task_id}_article.md"
        article_path.write_text("\n".join(article_lines), encoding="utf-8")

        # 生成引用列表文件（包含评分和说明）
        references_content = self._build_references_list(
            evidences, citation_map)
        references_path = self.output_dir / f"{task_id}_references.md"
        references_path.write_text(references_content, encoding="utf-8")

        # 保留旧的 .md 和 .bib 文件以保持兼容
        legacy_md_path = self.output_dir / f"{task_id}.md"
        legacy_md_path.write_text("\n".join(article_lines), encoding="utf-8")

        bib_lines: list[str] = []
        for c in citation_map.values():
            key = c.id.replace("-", "")[:8]
            bib_lines.extend(
                [
                    f"@article{{{key},",
                    f"  title = {{{c.title}}},",
                    f"  author = {{{' and '.join(c.authors) or 'Unknown'}}},",
                    f"  year = {{{c.year}}},",
                    f"  url = {{{c.url}}}",
                    "}",
                    "",
                ]
            )
        bib_path = self.output_dir / f"{task_id}.bib"
        bib_path.write_text("\n".join(bib_lines), encoding="utf-8")

        return str(article_path), str(references_path), citation_map

    def generate_body(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint | None = None,
        writing_plan: list[WritingSectionPlan] | None = None,
    ) -> str:
        selected_blueprint = blueprint or self._default_blueprint()
        draft = self.generate_draft(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=selected_blueprint,
            writing_plan=writing_plan,
        )
        return draft.body

    def generate_draft(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint | None = None,
        writing_plan: list[WritingSectionPlan] | None = None,
    ) -> ReportDraft:
        selected_blueprint = blueprint or self._default_blueprint()
        return self._generate_body(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=selected_blueprint,
            writing_plan=writing_plan,
        )

    def rewrite_body(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
        draft_body: str,
        feedback_issues: list[str],
        targeted_sections: list[str] | None = None,
        writing_plan: list[WritingSectionPlan] | None = None,
    ) -> str:
        draft = self.rewrite_draft(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
            draft_body=draft_body,
            feedback_issues=feedback_issues,
            targeted_sections=targeted_sections,
            writing_plan=writing_plan,
        )
        return draft.body

    def rewrite_draft(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
        draft_body: str,
        feedback_issues: list[str],
        targeted_sections: list[str] | None = None,
        writing_plan: list[WritingSectionPlan] | None = None,
    ) -> ReportDraft:
        outlines = self._build_section_outlines(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            blueprint=blueprint,
            writing_plan=writing_plan,
        )
        if settings.use_mock_sources:
            mock_body = self._generate_mock_body(
                task_title=task_title,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
                outlines=outlines,
            )
            return self._build_draft_from_body(mock_body, outlines, status="complete")

        cleaned_evidences = self._prepare_evidence_for_chinese_output(
            evidences)
        existing_sections = self._parse_existing_sections(draft_body)
        targeted_set = {heading.strip() for heading in
                        (targeted_sections or []) if heading and heading.strip()}
        regenerate_all = any(
            keyword in "；".join(feedback_issues)
            for keyword in ("章节过少", "章节深度不足", "章节展开不足", "正文过短", "证据覆盖不足")
        )
        if not existing_sections:
            regenerate_all = True
        elif targeted_set and not regenerate_all:
            regenerate_all = all(
                heading not in existing_sections for heading in targeted_set)

        rebuilt_sections: list[SectionDraft] = []
        for index, outline in enumerate(outlines):
            section_body = existing_sections.get(outline.heading, "").strip()
            should_regenerate = (
                regenerate_all
                or len(section_body) < 80
                or (not regenerate_all and bool(targeted_set) and outline.heading in targeted_set)
            )
            if should_regenerate:
                section_body = self._generate_single_section_with_retries(
                    task_title=task_title,
                    task_description=task_description,
                    outline=outline,
                    outline_index=index,
                    total_outlines=len(outlines),
                    evidences=self._select_section_evidences(
                        cleaned_evidences, outline, index),
                    blueprint=blueprint,
                    rewrite_context=draft_body,
                    feedback_issues=feedback_issues,
                )
            if not section_body.strip():
                section_body = existing_sections.get(
                    outline.heading, "").strip()
            if not section_body.strip():
                section_body = self._build_fallback_section_body(
                    task_title=task_title,
                    outline=outline,
                    evidences=self._select_section_evidences(
                        cleaned_evidences, outline, index),
                )
            normalized_body, suppressed_segments = self._sanitize_markdown_output(
                section_body)
            status = "rewritten" if normalized_body else "failed"
            rebuilt_sections.append(
                SectionDraft(
                    sectionId=outline.key,
                    heading=outline.heading,
                    body=normalized_body,
                    usedEvidenceIds=[ev.id for ev in self._select_section_evidences(
                        cleaned_evidences, outline, index)[:outline.required_evidence_count]],
                    status=status,
                    attempts=1 if should_regenerate else 0,
                    issues=["已移除写作过程说明。"] if suppressed_segments else [],
                )
            )
        return self._finalize_report_draft(
            drafts=rebuilt_sections,
            outlines=outlines,
            blueprint=blueprint,
            evidences=cleaned_evidences,
        )

    def generate_title(
        self,
        *,
        task_title: str,
        task_description: str,
        body: str,
        evidences: list[Evidence],
    ) -> str:
        body = self._normalize_text(body)
        if settings.use_mock_sources:
            return self._derive_title_from_text(task_title=task_title, body=body)

        base_url, api_key, model = self._resolve_provider()
        if not base_url or not api_key:
            return self._derive_title_from_text(task_title=task_title, body=body)

        evidence_titles = "\n".join(
            f"- {self._display_title(ev)}" for ev in evidences[:6])
        prompt = (
            "请为以下研究文章拟定一个自然、具体、像人类学者会使用的中文标题。\n"
            "要求：\n"
            "1. 标题必须紧扣研究主题和正文内容，不得虚构世界观或戏谑化表达。\n"
            "2. 不得出现「研究计划」「执行步骤」等计划性措辞。\n"
            "3. 控制在 18 到 36 个中文字符，必要时可带副标题。\n"
            "4. 只输出标题本身，不要解释。\n\n"
            f"原始主题：{task_title}\n"
            f"任务背景：{task_description[:500]}\n"
            f"证据标题：\n{evidence_titles or '- 无'}\n\n"
            f"正文摘要：\n{body[:1800]}"
        )

        try:
            with httpx.Client(timeout=settings.llm_timeout_medium) as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": "你是一名中文学术论文标题编辑。"},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                payload = response.json()
            candidate = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return self._sanitize_article_title(candidate, fallback=self._derive_title_from_text(task_title=task_title, body=body))
        except Exception as exc:  # noqa: BLE001
            logger.warning("生成文章标题失败，回退为启发式标题: %s", exc)
            return self._derive_title_from_text(task_title=task_title, body=body)

    def _generate_body(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
        writing_plan: list[WritingSectionPlan] | None = None,
    ) -> ReportDraft:
        """生成文章正文内容，不含内部标记。"""
        outlines = self._build_section_outlines(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            blueprint=blueprint,
            writing_plan=writing_plan,
        )
        if settings.use_mock_sources:
            mock_body = self._generate_mock_body(
                task_title=task_title,
                sections=sections,
                evidences=evidences,
                blueprint=blueprint,
                outlines=outlines,
            )
            return self._build_draft_from_body(mock_body, outlines, status="complete")

        section_drafts = self._generate_with_llm(
            task_title=task_title,
            task_description=task_description,
            sections=sections,
            evidences=evidences,
            blueprint=blueprint,
            outlines=outlines,
        )
        return self._finalize_report_draft(
            drafts=section_drafts,
            outlines=outlines,
            blueprint=blueprint,
            evidences=evidences,
        )

    def _generate_with_llm(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
        outlines: list[SectionOutline],
    ) -> list[SectionDraft]:
        base_url, api_key, model = self._resolve_provider()
        if not base_url or not api_key:
            return []

        # 清理证据内容中的期刊格式标记
        cleaned_evidences = self._prepare_evidence_for_chinese_output(
            evidences)
        SYSTEM_PROMPT_ACADEMIC = """你是一位资深的学术写作专家，擅长撰写高质量的中文学术论文。

## 写作风格要求

1. 自然流畅的段落结构
    - 绝对禁止使用“研究问题：”“证据解读：”“综合分析：”等机械标签。
    - 使用自然过渡语句连接段落，形成完整论证链条。
    - 段落之间要有逻辑衔接，避免简单罗列。

2. 灵活但清晰的文章架构
    - 严格围绕给定章节目标写作。
    - 每一节都要回答“这一节要解决什么问题”。
    - 不要输出当前章节之外的标题或参考文献部分。

3. 学术语言规范
    - 使用正式中文学术表达，避免口语化和宣传式措辞。
    - 引用应自然融入论述，而不是机械堆砌。

4. 纯中文输出
    - 正文必须使用中文表达。
    - 不得输出裸露 URL，不得照抄乱码或网页导航文本。

5. 证据驱动
    - 使用 [evidence:证据ID] 作为引用标记。
    - 结合证据做归纳、比较和解释，不要原样复述证据摘要。
"""
        article_sections: list[SectionDraft] = []
        try:
            with httpx.Client(timeout=settings.llm_timeout_long) as client:
                for index, outline in enumerate(outlines):
                    relevant_evidences = self._select_section_evidences(
                        cleaned_evidences, outline, index)
                    section_text = self._generate_single_section_with_retries(
                        task_title=task_title,
                        task_description=task_description,
                        outline=outline,
                        outline_index=index,
                        total_outlines=len(outlines),
                        evidences=relevant_evidences,
                        blueprint=blueprint,
                        client=client,
                        base_url=base_url,
                        api_key=api_key,
                        model=model,
                        system_prompt=SYSTEM_PROMPT_ACADEMIC,
                    )
                    normalized_text, suppressed_segments = self._sanitize_markdown_output(
                        section_text)
                    if not normalized_text:
                        normalized_text = self._build_fallback_section_body(
                            task_title=task_title,
                            outline=outline,
                            evidences=relevant_evidences,
                        )
                    article_sections.append(
                        SectionDraft(
                            sectionId=outline.key,
                            heading=outline.heading,
                            body=normalized_text,
                            usedEvidenceIds=[
                                ev.id for ev in relevant_evidences[:outline.required_evidence_count]],
                            status="generated" if section_text.strip() else "failed",
                            attempts=1 if section_text.strip() else 2,
                            issues=(
                                (["已移除写作过程说明。"] if suppressed_segments else [])
                                if section_text.strip()
                                else ["章节生成失败，已使用回退正文。"]
                            ),
                        )
                    )
        except httpx.TimeoutException:
            logger.error(
                f"LLM API 调用超时 ({settings.llm_timeout_long}s)，task={task_title[:50]}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"LLM API HTTP 错误: {e.response.status_code}, task={task_title[:50]}")
            return []
        except Exception as e:
            logger.error(
                f"LLM API 异常: {type(e).__name__}: {e}, task={task_title[:50]}")
            return []

        return article_sections

    def _resolve_provider(self) -> tuple[str, str, str]:
        provider = settings.default_llm_provider.lower().strip()
        if provider == "openrouter":
            return settings.openrouter_base_url, settings.openrouter_api_key, settings.openrouter_model
        if provider == "deepseek":
            return settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model
        if provider == "openai":
            return settings.openai_base_url, settings.openai_api_key, settings.openai_model
        return "", "", ""

    def _generate_mock_body(
        self,
        *,
        task_title: str,
        sections: list[tuple[str, str]],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
        outlines: list[SectionOutline] | None = None,
    ) -> str:
        ranked = self._prepare_evidence_for_chinese_output(evidences)
        selected_outlines = outlines or self._build_section_outlines(
            task_title=task_title,
            task_description="",
            sections=sections,
            blueprint=blueprint,
        )
        paragraphs: list[str] = []
        for idx, outline in enumerate(selected_outlines):
            paragraphs.append(f"## {outline.heading}")
            matched = ranked[idx: idx + 2] if ranked else []
            if matched:
                citation_bits = [
                    f"{self._display_title(ev)} [evidence:{ev.id}]" for ev in matched]
                evidence_summary = "；".join(citation_bits)
                paragraphs.append(
                    f"围绕“{task_title}”，本节在测试模式下根据当前证据生成验证性正文，重点汇总 {evidence_summary}。"
                    "文本的目的不是模拟真实学术创新，而是确保检索、引用替换、章节组织和导出流程都能在可控环境下被完整触发与检查。"
                )
                paragraphs.append(
                    "从流程角度看，这一节应当同时覆盖问题背景、证据含义和结论边界，因此这里会保留较长的说明性段落，"
                    "以满足审稿器对章节长度、段落层次和引用分布的基础要求，并帮助测试用例验证正文不会泄露 URL、占位符或中间调试痕迹。"
                )
                paragraphs.append(
                    "如果需要真实的研究质量，应切换到真实数据源和正式写作模型；但即便在测试模式下，正文仍然应保持中文表达、"
                    "结构清晰和引用可追溯，避免出现机械标签、碎片化列表或无法解释来源的断裂句子。"
                )
            else:
                paragraphs.append(
                    f"围绕“{task_title}”，当前未检索到可用于“{outline.heading}”的有效证据，因此这里只保留占位性说明，供测试流程验证使用。"
                )
            paragraphs.append("")
        return "\n".join(paragraphs).strip()

    @staticmethod
    def _design_dynamic_sections(task_title: str, blueprint: ReportBlueprint, available_sections: int) -> list[str]:
        section_count = max(3, min(max(available_sections, 3), 6))
        if section_count <= 3:
            return ["引言", "分析", "结论"]
        if section_count == 4:
            return ["引言", "问题界定", "核心分析", "结论"]
        if section_count == 5:
            return ["引言", "问题界定", "证据与争议", "综合分析", "结论"]
        return ["引言", "问题界定", "证据与争议", "综合分析", "实施条件", "结论"]

    @staticmethod
    def _compact_text(text: str, limit: int) -> str:
        compacted = WriterService._normalize_text(text)
        if not compacted:
            return "暂无内容。"
        return compacted[:limit]

    @classmethod
    def _normalize_text(cls, text: str) -> str:
        if not text:
            return ""
        normalized = html.unescape(text)
        normalized = cls.UNICODE_ESCAPE_PATTERN.sub(
            lambda match: chr(int(match.group(1), 16)),
            normalized,
        )
        normalized = normalized.replace("\ufeff", " ").replace("\u200b", " ")
        normalized = "".join(
            " " if unicodedata.category(ch).startswith(
                "C") and ch not in "\n\t" else ch
            for ch in normalized
        )
        normalized = unicodedata.normalize("NFKC", normalized)
        return " ".join(normalized.split()).strip()

    @classmethod
    def _normalize_markdown_text(cls, text: str) -> str:
        if not text:
            return ""
        normalized = html.unescape(text)
        normalized = cls.UNICODE_ESCAPE_PATTERN.sub(
            lambda match: chr(int(match.group(1), 16)),
            normalized,
        )
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\ufeff", " ").replace("\u200b", " ")
        normalized = "".join(
            " " if unicodedata.category(ch).startswith(
                "C") and ch not in "\n\t" else ch
            for ch in normalized
        )
        normalized = unicodedata.normalize("NFKC", normalized)
        lines = [re.sub(r"[ \t]+", " ", line).rstrip()
                 for line in normalized.split("\n")]

        compacted: list[str] = []
        blank_run = 0
        for line in lines:
            if line.strip():
                blank_run = 0
                compacted.append(line)
                continue
            blank_run += 1
            if blank_run <= 1:
                compacted.append("")
        return "\n".join(compacted).strip()

    def _build_section_outlines(
        self,
        *,
        task_title: str,
        task_description: str,
        sections: list[tuple[str, str]],
        blueprint: ReportBlueprint,
        writing_plan: list[WritingSectionPlan] | None = None,
    ) -> list[SectionOutline]:
        outlines: list[SectionOutline] = []
        seen: set[str] = set()
        if writing_plan:
            for section in writing_plan:
                if not section.heading or section.heading in seen:
                    continue
                seen.add(section.heading)
                outlines.append(SectionOutline(
                    key=section.sectionId,
                    heading=section.heading,
                    brief=section.brief,
                    source_node_ids=section.sourceNodeIds,
                    required_evidence_count=section.requiredEvidenceCount,
                ))
            if len(outlines) >= 3:
                return outlines

        for section_id, raw_text in sections:
            heading, brief = self._split_section_entry(raw_text)
            if not heading or heading in seen:
                continue
            seen.add(heading)
            outlines.append(SectionOutline(
                key=section_id,
                heading=heading,
                brief=brief or f"围绕“{heading}”展开分析，并与主题“{task_title}”建立清晰关系。",
                source_node_ids=[section_id],
            ))

        if len(outlines) >= 3:
            return outlines

        fallback_titles = self._design_dynamic_sections(
            task_title, blueprint, len(sections))
        for index, heading in enumerate(fallback_titles):
            if heading in seen:
                continue
            seen.add(heading)
            outlines.append(SectionOutline(
                key=f"fallback-{index + 1}",
                heading=heading,
                brief=f"围绕“{task_title}”撰写“{heading}”部分，并结合任务背景“{task_description[:180]}”展开。",
                source_node_ids=[],
            ))
        return outlines[:max(3, len(fallback_titles))]

    @classmethod
    def _split_section_entry(cls, raw_text: str) -> tuple[str, str]:
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return "", ""
        parts = normalized.split("\n\n", 1)
        heading = cls._sanitize_section_heading(parts[0].splitlines()[0])
        brief = parts[1].strip() if len(parts) > 1 else normalized
        return heading, brief

    @classmethod
    def _sanitize_section_heading(cls, raw_heading: str) -> str:
        heading = raw_heading.strip().lstrip("#").strip()
        heading = re.sub(r"^[`\-]+|[`\-]+$", "", heading).strip()
        heading = re.sub(r"[：:]?\s*```(?:yaml|yml)?\s*$",
                         "", heading, flags=re.IGNORECASE).strip()
        if heading in {"```", "```yaml", "```yml", "---"}:
            return ""
        return heading

    @staticmethod
    def _parse_existing_sections(body: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_heading = ""
        for line in body.splitlines():
            heading_match = re.match(r"^##\s+(.+?)\s*$", line)
            if heading_match:
                current_heading = heading_match.group(1).strip()
                sections.setdefault(current_heading, [])
                continue
            if not current_heading:
                continue
            sections[current_heading].append(line)
        return {heading: "\n".join(lines).strip() for heading, lines in sections.items()}

    @staticmethod
    def _keyword_tokens(text: str) -> list[str]:
        return re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,}", text)

    def _select_section_evidences(
        self,
        evidences: list[Evidence],
        outline: SectionOutline,
        outline_index: int,
    ) -> list[Evidence]:
        if not evidences:
            return []
        tokens = self._keyword_tokens(f"{outline.heading} {outline.brief}")
        scored: list[tuple[int, float, Evidence]] = []
        for ev in evidences:
            haystack = self._normalize_text(
                f"{ev.metadata.title} {ev.metadata.abstract} {ev.content} {ev.nodeId}"
            )
            keyword_score = sum(
                1 for token in tokens if token and token in haystack)
            node_bonus = 2 if outline.key and outline.key == ev.nodeId else 0
            if outline.source_node_ids and ev.nodeId in outline.source_node_ids:
                node_bonus += 3
            scored.append((keyword_score + node_bonus, ev.score, ev))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = [ev for keyword_score, _,
                    ev in scored if keyword_score > 0][:4]
        if len(selected) >= 2:
            return selected

        offset = min(outline_index, max(0, len(evidences) - 1))
        rotated = evidences[offset:] + evidences[:offset]
        for ev in rotated:
            if ev not in selected:
                selected.append(ev)
            if len(selected) >= min(4, len(evidences)):
                break
        return selected

    def _generate_single_section_with_retries(
        self,
        **kwargs,
    ) -> str:
        section_text = self._generate_single_section_with_llm(**kwargs)
        if section_text.strip():
            return section_text

        feedback_issues = list(kwargs.get("feedback_issues") or [])
        retry_kwargs = dict(kwargs)
        retry_kwargs["feedback_issues"] = feedback_issues + \
            ["上一轮生成为空，请补足完整章节正文。"]
        section_text = self._generate_single_section_with_llm(**retry_kwargs)
        return section_text.strip()

    def _generate_single_section_with_llm(
        self,
        *,
        task_title: str,
        task_description: str,
        outline: SectionOutline,
        outline_index: int,
        total_outlines: int,
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
        client: httpx.Client | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        rewrite_context: str = "",
        feedback_issues: list[str] | None = None,
    ) -> str:
        resolved_base_url = base_url
        resolved_api_key = api_key
        resolved_model = model
        if not resolved_base_url or not resolved_api_key or not resolved_model:
            resolved_base_url, resolved_api_key, resolved_model = self._resolve_provider()
        if not resolved_base_url or not resolved_api_key or not resolved_model:
            return ""

        evidence_snippets = "\n".join(
            (
                f"- [{ev.id}] {self._display_title(ev)} | 类型：{ev.sourceType.value} | 时间：{ev.metadata.publishDate or '未知'}\n"
                f"  摘要：{self._compact_text(ev.content, 240)}"
            )
            for ev in evidences[:4]
        )
        feedback_text = "；".join(feedback_issues or [])
        rewrite_hint = (
            f"上一版草稿存在这些问题：{feedback_text}\n"
            f"上一版相关正文：{rewrite_context[:1200]}\n"
            if feedback_text
            else ""
        )
        user_prompt = (
            f"研究题目：{task_title}\n"
            f"任务背景：{task_description[:1000]}\n"
            f"输出体裁：{blueprint.output_format}\n"
            f"当前章节（第 {outline_index + 1}/{total_outlines} 节）：{outline.heading}\n"
            f"章节 brief：{outline.brief}\n"
            f"全文要求：至少 {total_outlines} 个二级章节，当前章节必须自然融入全文。\n"
            "写作要求：\n"
            "1. 只输出当前章节正文，不要再输出章节标题。\n"
            "2. 正常情况下写 2 到 3 段；引言或结论也至少 2 段。\n"
            "3. 用自然学术中文写作，不要使用“研究问题：”“证据解读：”等模板标签。\n"
            "4. 使用 [evidence:证据ID] 作为引用标记，不要输出裸露 URL。\n"
            "5. 不要照抄证据原文，要进行归纳、比较和解释。\n"
            f"6. 当前可用证据：\n{evidence_snippets or '- 无可用证据'}\n"
            f"{rewrite_hint}"
        )
        payload = {
            "model": resolved_model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system_prompt or "你是一名中文学术写作专家。"},
                {"role": "user", "content": user_prompt},
            ],
        }

        owns_client = client is None
        active_client = client or httpx.Client(
            timeout=settings.llm_timeout_long)
        try:
            response = active_client.post(
                f"{resolved_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {resolved_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            result = (
                response.json().get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return self._strip_inline_urls(result)
        finally:
            if owns_client:
                active_client.close()

    def _finalize_report_draft(
        self,
        *,
        drafts: list[SectionDraft],
        outlines: list[SectionOutline],
        blueprint: ReportBlueprint,
        evidences: list[Evidence],
    ) -> ReportDraft:
        valid_drafts = [draft for draft in drafts if draft.body.strip()]
        body = self._assemble_report_body(valid_drafts)
        issues: list[str] = []
        suppressed_segments: list[str] = []
        for draft in drafts:
            if draft.issues and any("写作过程说明" in issue for issue in draft.issues):
                suppressed_segments.append(f"章节“{draft.heading}”包含已移除的写作过程说明。")
        if not valid_drafts:
            issues.append("未生成任何可用章节。")
            return ReportDraft(body="", sections=drafts, status="empty", issues=issues, suppressedSegments=suppressed_segments)

        sanitized = self._strip_inline_urls(body.strip())
        sanitized, removed_in_body = self._sanitize_markdown_output(
            self._strip_internal_markers(sanitized))
        suppressed_segments.extend(removed_in_body)
        required_chars = self._minimum_acceptable_body_chars(
            outlines, evidences, blueprint)
        if len(sanitized) < required_chars:
            issues.append(f"正文长度不足（当前 {len(sanitized)}，最低 {required_chars}）。")

        status = "complete"
        if len(valid_drafts) < min(3, len(outlines)):
            issues.append("可用章节数量不足，已保留部分草稿。")
            status = "partial"
        if issues and status == "complete":
            status = "partial"
        return ReportDraft(
            body=sanitized,
            sections=drafts,
            status=status,
            issues=issues,
            suppressedSegments=self._dedupe_preserved_order(
                suppressed_segments),
        )

    def _build_draft_from_body(
        self,
        body: str,
        outlines: list[SectionOutline],
        *,
        status: str,
    ) -> ReportDraft:
        parsed_sections = self._parse_existing_sections(body)
        drafts = [
            SectionDraft(
                sectionId=outline.key,
                heading=outline.heading,
                body=parsed_sections.get(outline.heading, ""),
                status="generated",
            )
            for outline in outlines
        ]
        normalized_body, suppressed_segments = self._sanitize_markdown_output(
            body)
        return ReportDraft(body=normalized_body, sections=drafts, status=status, issues=[], suppressedSegments=suppressed_segments)

    @staticmethod
    def _assemble_report_body(drafts: list[SectionDraft]) -> str:
        return "\n\n".join(
            f"## {draft.heading}\n\n{draft.body.strip()}"
            for draft in drafts
            if draft.body.strip()
        ).strip()

    @staticmethod
    def _minimum_acceptable_body_chars(
        outlines: list[SectionOutline],
        evidences: list[Evidence],
        blueprint: ReportBlueprint,
    ) -> int:
        base_requirement = 220 + len(outlines or blueprint.section_titles) * 90
        if len(evidences) < 2:
            return max(320, base_requirement - 180)
        return max(420, base_requirement)

    def _build_fallback_section_body(
        self,
        *,
        task_title: str,
        outline: SectionOutline,
        evidences: list[Evidence],
    ) -> str:
        if evidences:
            citations = "、".join(
                f"{self._display_title(ev)} [evidence:{ev.id}]" for ev in evidences[:2])
            return (
                f"围绕“{task_title}”的“{outline.heading}”部分，当前自动写作已依据可用证据补写核心论点，重点整合 {citations} 所呈现的事实与判断。"
                f"本节先交代 {outline.brief}，再说明这些证据如何支持或限制相关结论，以避免整篇报告因为单章失败而中断。\n\n"
                f"从当前材料看，本节最重要的任务是把研究问题、证据含义和适用边界写清楚；若后续需要进一步扩展，可继续对该章节触发定向重写。"
            )
        return (
            f"围绕“{task_title}”的“{outline.heading}”部分，系统已保留结构化草稿，以避免单章生成失败导致全文中断。\n\n"
            f"当前可确认的写作目标是：{outline.brief}。后续可通过补充检索或再次重写来增强这一节的证据密度与分析深度。"
        )

    @staticmethod
    def _clean_journal_markers(text: str) -> str:
        """清理期刊格式标记（如 Received、Accepted、Published 等）。

        这些标记通常出现在学术论文摘要中，会导致中英文混杂问题。
        """
        patterns = [
            r"Received:?\s*\w+\s*\d+,?\s*\d+;?",
            r"Accepted:?\s*\w+\s*\d+,?\s*\d+;?",
            r"Published:?\s*\w+\s*\d+,?\s*\d+;?",
            r"Shanghai\s+Received:.*?(?=\n|$)",
            r"[A-Z][a-z]+\s+Received:.*?(?=\n|$)",
        ]
        cleaned = WriterService._normalize_text(text)
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _prepare_evidence_for_chinese_output(self, evidences: list[Evidence]) -> list[Evidence]:
        """准备证据内容用于中文输出。

        清理期刊元数据标记，避免中英文混杂问题。
        同时过滤低质量和垃圾内容。
        """
        cleaned_evidences = []
        for ev in evidences:
            ev_copy = ev.model_copy(deep=True)
            # 清理期刊元数据标记
            if ev_copy.content:
                ev_copy.content = self._clean_journal_markers(ev_copy.content)
            if ev_copy.metadata.title:
                ev_copy.metadata.title = self._clean_journal_markers(
                    ev_copy.metadata.title)
            if ev_copy.metadata.abstract:
                ev_copy.metadata.abstract = self._clean_journal_markers(
                    ev_copy.metadata.abstract)

            # 过滤低评分证据（低于 0.05 认为是不可靠的）
            if ev_copy.score < 0.05:
                logger.warning(
                    f"过滤低评分证据 (score={ev_copy.score:.3f}): {ev_copy.url[:60]}")
                continue

            # 过滤垃圾内容
            if self._is_garbage_evidence(ev_copy):
                logger.warning(f"过滤垃圾证据: {ev_copy.url[:60]}")
                continue

            cleaned_evidences.append(ev_copy)

        return cleaned_evidences

    @staticmethod
    def _is_garbage_evidence(ev: Evidence) -> bool:
        """检测证据是否为垃圾内容。"""
        content = WriterService._normalize_text(ev.content or "")
        url = ev.url or ""
        title = WriterService._normalize_text(ev.metadata.title or "")

        # 1. 检测特殊文件扩展名
        garbage_extensions = [
            '.diff', '.patch', '.xls', '.xlsx', '.csv',
            '.pdf', '.zip', '.tar', '.gz', '.rar',
            '.exe', '.dll', '.so', '.bin', '.dat',
            '.json', '.xml', '.yaml', '.yml',
        ]
        for ext in garbage_extensions:
            if url.lower().endswith(ext):
                return True

        # 2. 检测分词器 token 格式 (+ll +lo +lp... 或 +不减 +不凡...)
        if re.match(r'^(\+\w+\s*){5,}', content.strip()):
            return True

        # 3. 检测代码仓库 diff 内容
        code_patterns = [
            r'^diff --git',
            r'^@@\s+-\d+,\d+\s+\+\d+,\d+\s+@@',
            r'^index\s+[a-f0-9]{7,}',
            r'^---\s+a/',
            r'^\+\+\+\s+b/',
        ]
        for pattern in code_patterns:
            if re.match(pattern, content.strip(), re.MULTILINE):
                return True

        # 4. 检测页面导航元素（CNKI 等）
        navigation_keywords = [
            '下载：', '页数：', '大小：', '引文网络', '参考文献',
            '共引文献', '同被引文献', '相关文献推荐', 'CNKI AI阅读',
            '原版阅读', 'HTML阅读', 'CAJ下载', '在线阅读',
        ]
        nav_count = sum(1 for kw in navigation_keywords if kw in content)
        if nav_count >= 3:
            return True

        if any(pattern.search(content) or pattern.search(title) for pattern in WriterService.GARBLED_PATTERNS):
            return True

        if content.count("{") + content.count("}") >= 4 and content.count('"') >= 6:
            return True

        if len(content) > 50:
            suspicious = sum(1 for c in content if ord(
                c) > 127 and not ('\u4e00' <= c <= '\u9fff'))
            if suspicious / len(content) > 0.2:
                return True

        # 6. 检测 URL 中包含 commit/diff/blob 等路径
        garbage_url_patterns = [
            r'/commit/[a-f0-9]+\.diff$',
            r'/commit/[a-f0-9]+\.patch$',
            r'/blob/',
            r'/tree/',
            r'/raw/',
            r'download\?etag=',
        ]
        for pattern in garbage_url_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return False

    def _build_evidence_appendix(self, evidences: list[Evidence]) -> str:
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)
        lines = ["## 证据说明与来源链接"]
        if not ranked:
            lines.append("暂无可用证据。")
            return "\n".join(lines)

        for idx, ev in enumerate(ranked, start=1):
            snippet = " ".join(ev.content.split())
            lines.append(f"{idx}. [{ev.id}] {self._display_title(ev)}")
            lines.append(f"说明：{snippet[:220] or '该来源未返回可展示摘要。'}")
            lines.append(
                f"来源：{ev.sourceType.value} | 发表时间：{ev.metadata.publishDate or '未知'} | 评分：{ev.score:.2f}"
            )
            lines.append(f"网址：{ev.url}")
            lines.append("")
        return "\n".join(lines).rstrip()

    @classmethod
    def _strip_inline_urls(cls, text: str) -> str:
        return cls.URL_PATTERN.sub("[链接见文末证据附录]", text)

    @classmethod
    def _sanitize_markdown_output(cls, text: str) -> tuple[str, list[str]]:
        normalized = cls._normalize_markdown_text(text)
        normalized = cls._clean_export_body(normalized)
        sanitized, suppressed_segments = cls._strip_meta_commentary(normalized)
        return sanitized, suppressed_segments

    @classmethod
    def _clean_export_body(cls, text: str) -> str:
        cleaned = text.strip()
        while True:
            wrapper = cls.MARKDOWN_FENCE_WRAPPER_PATTERN.match(cleaned)
            if not wrapper:
                break
            cleaned = wrapper.group("body").strip()

        front_matter = cls.FRONT_MATTER_PATTERN.match(cleaned)
        if front_matter:
            cleaned = cleaned[front_matter.end():].strip()

        lines = cleaned.splitlines()
        if lines and re.fullmatch(r"```(?:markdown|md)\s*", lines[0].strip(), re.IGNORECASE):
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
        return "\n".join(lines).strip()

    @classmethod
    def _strip_meta_commentary(cls, text: str) -> tuple[str, list[str]]:
        if not text.strip():
            return "", []
        paragraphs = re.split(r"\n\s*\n", text)
        kept: list[str] = []
        removed: list[str] = []
        for paragraph in paragraphs:
            block = paragraph.strip()
            if not block:
                continue
            if any(pattern.match(line) for line in block.splitlines() for pattern in cls.META_HEADING_PATTERNS):
                removed.append(block)
                continue
            normalized_block = cls._normalize_text(block)
            if any(pattern.search(normalized_block) for pattern in cls.META_COMMENTARY_PATTERNS):
                removed.append(block)
                continue
            kept.append(block)
        return "\n\n".join(kept).strip(), cls._dedupe_preserved_order(removed)

    @staticmethod
    def _dedupe_preserved_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            candidate = value.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered

    @staticmethod
    def _default_blueprint() -> ReportBlueprint:
        return ReportBlueprint(
            output_format="研究报告",
            objective="给出跨维度、可复核且可执行的研究结论",
            tone="严谨、自然、以证据驱动",
            section_titles=["引言", "问题界定", "证据与争议", "综合分析", "实施条件", "结论"],
        )

    def _build_citations(self, evidences: list[Evidence]) -> dict[str, Citation]:
        citations: dict[str, Citation] = {}
        for ev in evidences:
            year = 2026
            if ev.metadata.publishDate[:4].isdigit():
                year = int(ev.metadata.publishDate[:4])
            citations[ev.id] = Citation(
                id=ev.id,
                authors=ev.metadata.authors or ["Unknown"],
                title=self._display_title(ev),
                year=year,
                source=ev.sourceType.value,
                url=ev.url,
            )
        return citations

    @classmethod
    def _display_title(cls, evidence: Evidence) -> str:
        raw_title = cls._normalize_text(evidence.metadata.title)
        if raw_title and not cls._looks_placeholder_title(raw_title):
            return raw_title
        fallback = cls._cleanup_placeholder_text(
            cls._normalize_text(evidence.content))
        if fallback:
            return fallback[:120]
        return "未命名证据"

    @staticmethod
    def _cleanup_placeholder_text(text: str) -> str:
        cleaned = re.sub(r"(?i)^\[mock\]\s*", "", text).strip()
        cleaned = re.sub(
            r"(?i)^synthetic evidence for query:\s*", "", cleaned).strip()
        cleaned = re.sub(
            r"(?i)^(?:arxiv|semantic scholar|semanticscholar|web) result for\s*", "", cleaned).strip()
        return cleaned

    @classmethod
    def _looks_placeholder_title(cls, title: str) -> bool:
        return bool(cls.PLACEHOLDER_TITLE_PATTERN.search(title.strip()))

    @classmethod
    def _strip_internal_markers(cls, text: str) -> str:
        """移除内部标记，确保输出干净。

        过滤的内容包括：
        - _taskId: xxx_ 内部任务标记
        - ## AI 综合解读 AI 提示词泄露
        - ## 输出格式 输出格式信息泄露
        - ## Trace Section 调试信息
        - [locked] 锁定标记
        """
        # 移除匹配的行
        lines = text.splitlines()
        filtered_lines = []
        skip_next_empty = False

        for line in lines:
            # 检查是否是需要移除的行
            if cls.INTERNAL_MARKERS_PATTERN.search(line):
                skip_next_empty = True
                continue
            # 跳过标记后的空行
            if skip_next_empty and line.strip() == "":
                skip_next_empty = False
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    @staticmethod
    def _replace_evidence_refs(text: str, evidence_to_index: dict[str, int]) -> str:
        """将 [evidence:xxx] 替换为标准引用编号 [1], [2], ...

        Args:
            text: 包含 evidence 引用的文本
            evidence_to_index: evidence_id 到引用编号的映射

        Returns:
            替换后的文本
        """
        pattern = re.compile(r"\[evidence:([\w-]+)\]")

        def replace_match(match: re.Match) -> str:
            ev_id = match.group(1)
            idx = evidence_to_index.get(ev_id)
            if idx:
                return f"[{idx}]"
            # 如果找不到对应的引用，移除该标记
            return ""

        return pattern.sub(replace_match, text)

    @classmethod
    def _derive_title_from_text(cls, *, task_title: str, body: str) -> str:
        body = cls._normalize_text(body)
        headings = re.findall(r"^##\s+(.+)$", body, flags=re.MULTILINE)
        if headings:
            lead = "、".join(headings[:2])
            return cls._sanitize_article_title(f"{task_title}：围绕{lead}的分析", fallback=task_title)
        return cls._sanitize_article_title(task_title, fallback="研究文章")

    @classmethod
    def _sanitize_article_title(cls, title: str, *, fallback: str) -> str:
        candidate = cls._normalize_text(title)
        candidate = re.sub(r"^[#\-\*\d\.\s]+", "", candidate)
        candidate = candidate.strip("“”\"'：:;；，,。")
        candidate = candidate.splitlines()[0] if candidate else ""
        candidate = re.sub(r"\s{2,}", " ", candidate)
        if not candidate:
            return cls._normalize_text(fallback) or "研究文章"
        if cls.ARTICLE_TITLE_BLACKLIST.search(candidate):
            return cls._normalize_text(fallback) or "研究文章"
        if any(pattern.search(candidate) for pattern in cls.GARBLED_PATTERNS):
            return cls._normalize_text(fallback) or "研究文章"
        if len(candidate) > 64:
            candidate = candidate[:64].rstrip("：:;；，,")
        if len(candidate) < 6:
            return cls._normalize_text(fallback) or "研究文章"
        return candidate

    def _build_references_list(
        self,
        evidences: list[Evidence],
        citation_map: dict[str, Citation]
    ) -> str:
        """生成引用列表文件，包含评分和说明。

        Args:
            evidences: 证据列表
            citation_map: 引用映射

        Returns:
            格式化的引用列表内容
        """
        ranked = sorted(evidences, key=lambda item: item.score, reverse=True)

        lines = ["# 引用列表", ""]
        lines.append("本文档包含研究中引用的所有文献，包括评分、来源和相关说明。")
        lines.append("")

        if not ranked:
            lines.append("暂无引用文献。")
            return "\n".join(lines)

        lines.append(f"共 {len(ranked)} 条引用文献，按相关性评分排序。")
        lines.append("")

        for idx, ev in enumerate(ranked, start=1):
            citation = citation_map.get(ev.id)
            lines.append(f"## 文献 {idx}")
            lines.append(f"- **ID**: `{ev.id}`")
            lines.append(f"- **标题**: {self._display_title(ev)}")

            if citation:
                authors_str = "、".join(
                    citation.authors) if citation.authors else "未知"
                lines.append(f"- **作者**: {authors_str}")
                lines.append(f"- **年份**: {citation.year}")

            lines.append(f"- **来源类型**: {ev.sourceType.value}")
            lines.append(f"- **发表时间**: {ev.metadata.publishDate or '未知'}")
            lines.append(f"- **相关性评分**: {ev.score:.2f}")
            lines.append(
                f"- **是否同行评审**: {'是' if ev.metadata.isPeerReviewed else '否'}")

            if ev.metadata.citationCount > 0:
                lines.append(f"- **引用次数**: {ev.metadata.citationCount}")

            lines.append(f"- **链接**: [{ev.url}]({ev.url})")
            lines.append("")

            # 添加摘要/说明
            snippet = " ".join(ev.content.split()).strip()
            if snippet:
                lines.append("**摘要/说明**:")
                lines.append(
                    f"> {snippet[:500]}{'...' if len(snippet) > 500 else ''}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
