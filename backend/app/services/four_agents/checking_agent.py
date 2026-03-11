"""检查智能体 - 评审文章质量，确保符合要求。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import settings
from app.models.schemas import AgentType
from app.services.four_agents.base import AgentContext, AgentResult, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class CheckIssue:
    """检查发现的问题。"""
    severity: str  # "critical", "major", "minor"
    description: str
    location: str | None = None
    suggestion: str | None = None


class CheckingAgent(BaseAgent):
    """检查智能体。

    职责：
    - 评审文章质量
    - 检测提示词泄露
    - 验证引用格式
    - 检测"机器味"问题
    - 如有问题可打回写作智能体
    """

    agent_type = AgentType.CHECKING

    # 需要检测的禁止模式
    FORBIDDEN_PATTERNS = [
        (r"_taskId:\s*\S+_", "内部任务 ID 泄露", "critical"),
        (r"\#\#\s*AI\s*综合解读", "AI 提示词泄露", "critical"),
        (r"\#\#\s*输出格式", "输出格式信息泄露", "major"),
        (r"\#\#\s*Trace\s*Section", "调试信息泄露", "major"),
        (r"\[locked\]", "锁定标记泄露", "minor"),
        (r"system\s*prompt", "系统提示词泄露", "critical"),
        (r"你是.*助手", "角色设定泄露", "major"),
    ]

    # "机器味"检测模式 - 快速初筛
    MECHANICAL_PATTERNS = [
        (r"研究问题[：:]", "模板化开头「研究问题：」", "major"),
        (r"证据解读[：:]", "模板化开头「证据解读：」", "major"),
        (r"综合分析[：:]", "模板化开头「综合分析：」", "major"),
        (r"本节围绕.*展开", "模板化语句「本节围绕...展开」", "major"),
        (r"以上证据共同支持本节判断", "模板化总结语句", "minor"),
        (r"在.*方面，.*的研究提供了重要参考", "机械化的证据引入句式", "minor"),
        (r"此外，.*的研究进一步表明", "机械化的证据补充句式", "minor"),
        (r"综合以上.*成果.*可以看出", "机械化的总结句式", "minor"),
        (r"基于现有.*资料.*本节将从", "模板化的段落开头", "minor"),
    ]

    # 中英文混杂检测模式
    MIXED_LANGUAGE_PATTERNS = [
        (r"Received:?\s*\w+\s*\d+", "期刊格式标记泄露（Received）", "critical"),
        (r"Accepted:?\s*\w+\s*\d+", "期刊格式标记泄露（Accepted）", "critical"),
        (r"Published:?\s*\w+\s*\d+", "期刊格式标记泄露（Published）", "critical"),
        (r"Shanghai.*\d{4}.*A\s*$", "地址信息泄露", "major"),
    ]

    # 垃圾内容检测模式
    GARBAGE_CONTENT_PATTERNS = [
        (r'^(\+\w+\s*){5,}', "分词器词汇表内容", "critical"),
        (r'^diff --git', "代码仓库 diff 文件", "critical"),
        (r'^@@\s+-\d+,\d+\s+\+\d+,\d+\s+@@', "代码仓库 diff 文件", "critical"),
        (r'download\?etag=', "二进制文件下载链接", "major"),
        (r'\.diff$', "代码仓库 diff 文件", "critical"),
        (r'\.xlsx?\?srsltid=', "Excel 文件内容", "major"),
        # URL 直接出现在正文中（非参考文献部分）
        (r'https?://[^\s\]]{30,}', "正文中出现长网址", "critical"),
        (r'https?://raw\.githubusercontent\.com/', "代码仓库原始链接", "critical"),
        (r'https?://huggingface\.co/api', "API 端点链接", "critical"),
        # Unicode 乱码检测
        (r'\\u[0-9a-fA-F]{4}', "Unicode 转义序列", "critical"),
        # 无意义词汇组合（中文+乱码）
        (r'[\u4e00-\u9fff]{2,4}\s+[\u4e00-\u9fff]{2,4}\s+[\u4e00-\u9fff]{2,4}\s+[\u4e00-\u9fff]{2,4}\s+[\u4e00-\u9fff]{2,4}\s+[\u4e00-\u9fff]{2,4}', "无规律词汇堆砌", "major"),
    ]

    # 页面导航元素检测模式
    NAVIGATION_PATTERNS = [
        (r'下载[：:]\s*\d+\s+页数[：:]', "页面导航元素（CNKI）", "major"),
        (r'引文网络\s*参考文献', "页面导航元素（CNKI）", "major"),
        (r'#####\s*引文网络', "页面导航元素（CNKI）", "major"),
        (r'CNKI\s*AI阅读', "页面导航元素（CNKI）", "minor"),
        (r'原版阅读|HTML阅读|CAJ下载|在线阅读', "页面导航元素", "major"),
    ]

    # 乱码和异常字符检测
    GARBAGE_UNICODE_PATTERNS = [
        # 检测大量连续 Unicode 转义
        (r'\\u[0-9a-fA-F]{4}.*?\\u[0-9a-fA-F]{4}.*?\\u[0-9a-fA-F]{4}', "Unicode 转义序列堆积", "critical"),
        # 检测印度语、阿拉伯语等非中文内容在中文文章中
        (r'[\u0900-\u097F]{3,}', "梵文/印地文字符", "critical"),
        (r'[\u0A00-\u0A7F]{3,}', "古木基文字符", "critical"),
        (r'[\u0C00-\u0C7F]{3,}', "泰卢固文字符", "critical"),
        # 检测无意义的中文词汇堆砌
        (r'[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}', "无意义词汇堆砌", "major"),
    ]

    # Longcat API 配置
    LONGCAT_API_URL = "https://api.longcat.chat/openai/v1/chat/completions"
    LONGCAT_MODEL = "LongCat-Flash-Lite"
    LONGCAT_API_KEY = "ak_2Ks0iy2p02oX0V05UN3Mk7YO38R8"

    def __init__(self, on_progress=None) -> None:
        super().__init__(on_progress)

    async def run(self, context: AgentContext) -> AgentResult:
        """执行检查阶段任务。

        Args:
            context: 执行上下文，应包含 article_path。

        Returns:
            包含检查结果的执行结果。
        """
        article_path = context.config.get("article_path")
        if not article_path:
            return AgentResult(
                success=False,
                output={},
                error="缺少文章路径"
            )

        self._set_progress(10, "读取文章内容")

        # 读取文章
        try:
            article_content = Path(article_path).read_text(encoding="utf-8")
        except Exception as e:
            return AgentResult(
                success=False,
                output={},
                error=f"无法读取文章: {e}"
            )

        self._set_progress(20, "检测提示词泄露")

        # 检测泄露
        issues = self._check_prompt_leakage(article_content)

        # 检测"机器味"（快速初筛）
        self._set_progress(40, "检测机器味")
        mechanical_issues = self._check_mechanical_tone(article_content)
        issues.extend(mechanical_issues)

        # 检测结构
        self._set_progress(60, "检查文章结构")
        structure_issues = self._check_structure(article_content)
        issues.extend(structure_issues)

        # 检测引用
        self._set_progress(70, "验证引用格式")
        citation_issues = self._check_citations(article_content)
        issues.extend(citation_issues)

        # 检测垃圾内容
        garbage_issues = self._check_garbage_content(article_content)
        issues.extend(garbage_issues)

        # 使用 LLM 深度检测"机器味"（如果有需要）
        if mechanical_issues:
            self._set_progress(80, "使用 LLM 深度检测")
            llm_issues = await self._check_mechanical_tone_with_llm(article_content)
            issues.extend(llm_issues)

        self._set_progress(95, "生成检查报告")

        # 判断是否通过 - 更严格的判断标准
        critical_issues = [i for i in issues if i.severity == "critical"]
        major_issues = [i for i in issues if i.severity == "major"]

        # 有严重问题直接不通过
        if len(critical_issues) > 0:
            approved = False
        # 有主要问题且数量超过1个则不通过
        elif len(major_issues) > 1:
            approved = False
        else:
            approved = True

        return AgentResult(
            success=approved,
            output={
                "approved": approved,
                "issues": [
                    {
                        "severity": i.severity,
                        "description": i.description,
                        "location": i.location,
                        "suggestion": i.suggestion
                    }
                    for i in issues
                ],
                "summary": {
                    "total_issues": len(issues),
                    "critical": len(critical_issues),
                    "major": len(major_issues),
                    "minor": len(issues) - len(critical_issues) - len(major_issues)
                },
                "needs_rewrite": len(critical_issues) > 0 or len(major_issues) > 2
            }
        )

    def _check_prompt_leakage(self, content: str) -> list[CheckIssue]:
        """检测提示词泄露。"""
        issues = []
        for pattern, description, severity in self.FORBIDDEN_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=description,
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除或修改该内容"
                ))
        return issues

    def _check_mechanical_tone(self, content: str) -> list[CheckIssue]:
        """检测"机器味"问题（快速初筛）。"""
        issues = []

        # 检测模板化写作模式
        for pattern, description, severity in self.MECHANICAL_PATTERNS:
            matches = re.finditer(pattern, content)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=f"检测到{description}，建议使用自然的学术写作风格",
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="使用过渡语句替换模板标签，如'在...方面'、'值得注意的是'等"
                ))

        # 检测中英文混杂
        for pattern, description, severity in self.MIXED_LANGUAGE_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=description,
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除或翻译该内容为中文"
                ))

        return issues

    def _check_garbage_content(self, content: str) -> list[CheckIssue]:
        """检测垃圾内容问题。"""
        issues = []

        # 检测垃圾内容模式
        for pattern, description, severity in self.GARBAGE_CONTENT_PATTERNS:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=f"检测到{description}，内容不应出现在学术文章中",
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除该内容，并检查证据来源"
                ))

        # 检测页面导航元素
        for pattern, description, severity in self.NAVIGATION_PATTERNS:
            matches = re.finditer(pattern, content)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=f"检测到{description}，页面导航内容不应出现在文章中",
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除该内容，并检查证据来源"
                ))

        # 检测 Unicode 乱码
        for pattern, description, severity in self.GARBAGE_UNICODE_PATTERNS:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                # 限制报告数量
                if len([i for i in issues if i.severity == "critical"]) > 10:
                    break
                issues.append(CheckIssue(
                    severity=severity,
                    description=f"检测到{description}，这是明显的乱码或垃圾内容",
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除该内容段落，从可靠的证据源重新获取"
                ))

        # 检测引用格式问题（除了参考文献章节外，正文中不应有完整URL）
        ref_section_idx = content.find("## 参考文献")
        if ref_section_idx == -1:
            ref_section_idx = content.find("## References")

        if ref_section_idx > 0:
            body_content = content[:ref_section_idx]
            # 检测正文中的 URL
            url_matches = re.finditer(r'https?://\S+', body_content)
            for match in url_matches:
                # 排除引用标记中的 URL [text](url)
                if not re.search(r'\[.*?\]\(' + re.escape(match.group()) + r'\)', body_content[max(0, match.start()-50):match.end()+50]):
                    issues.append(CheckIssue(
                        severity="major",
                        description="正文中出现裸露的网址链接",
                        location=f"位置 {match.start()}-{match.end()}",
                        suggestion="将网址移到参考文献章节，正文中使用引用编号 [1] 等形式"
                    ))

        return issues

    async def _check_mechanical_tone_with_llm(self, content: str) -> list[CheckIssue]:
        """使用 LLM 深度检测"机器味"和学术写作质量问题。"""
        issues = []

        # 截取前 3000 字符进行分析
        sample_content = content[:3000]

        prompt = f"""请评估以下学术论文片段的写作质量，检测是否存在"机器味"问题：

{sample_content}

请检查以下问题：
1. 是否存在固定模板标签（如"研究问题："、"证据解读："、"综合分析："）
2. 段落结构是否机械化、缺乏自然过渡
3. 是否存在中英文混杂问题
4. 是否符合学术论文的自然写作风格
5. 是否存在无意义的词汇堆砌或乱码
6. 引用格式是否规范
7. 文章结构是否合理（是否有引言、主体、结论）

如发现问题，请以 JSON 格式返回：
{{"issues": [{{"type": "问题描述", "severity": "minor/major/critical", "location": "大致位置", "suggestion": "修改建议"}}]}}

如无问题，返回：{{"issues": []}}

只返回 JSON，不要其他解释。"""

        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_medium) as client:
                response = await client.post(
                    self.LONGCAT_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.LONGCAT_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.LONGCAT_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                payload = response.json()

            result_text = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            # 解析 JSON 结果
            if result_text:
                # 提取 JSON 部分
                json_match = re.search(r'\{[\s\S]*\}', result_text)
                if json_match:
                    result = json.loads(json_match.group())
                    for issue in result.get("issues", []):
                        issues.append(CheckIssue(
                            severity=issue.get("severity", "minor"),
                            description=issue.get("type", "写作质量问题"),
                            location=issue.get("location"),
                            suggestion=issue.get("suggestion", "请人工检查并修改")
                        ))

        except httpx.TimeoutException:
            logger.warning(f"LLM 深度检测超时 ({settings.llm_timeout_medium}s)")
        except httpx.HTTPStatusError as e:
            logger.warning(f"LLM 深度检测 HTTP 错误: {e.response.status_code}")
        except Exception as e:
            logger.warning(f"LLM 深度检测失败: {type(e).__name__}: {e}")

        return issues

    def _check_structure(self, content: str) -> list[CheckIssue]:
        """检查文章结构。"""
        issues = []

        # 检查标题
        if not content.strip().startswith("# "):
            issues.append(CheckIssue(
                severity="major",
                description="文章缺少主标题",
                suggestion="在文章开头添加一级标题"
            ))

        # 检查章节 - 更智能的章节检测
        sections = re.findall(r"^##\s+.+$", content, re.MULTILINE)
        if len(sections) < 2:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章章节过少（{len(sections)} 个），建议至少包含引言、主体和结论",
                suggestion="添加更多章节以增强结构完整性"
            ))

        # 检查是否有摘要/引言章节
        has_intro = any(re.search(r'摘|引言|背景|简介|概述', s) for s in sections)
        if not has_intro:
            issues.append(CheckIssue(
                severity="minor",
                description="文章缺少摘要或引言章节",
                suggestion="考虑添加摘要或引言章节来说明研究目的"
            ))

        # 检查是否有结论章节
        has_conclusion = any(re.search(r'结论|总结|建议|展望', s) for s in sections)
        if not has_conclusion:
            issues.append(CheckIssue(
                severity="minor",
                description="文章缺少结论章节",
                suggestion="考虑添加结论章节总结研究发现"
            ))

        # 检查字数
        word_count = len(content)
        if word_count < 1000:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章内容过短（{word_count} 字）",
                suggestion="扩充文章内容至至少 1000 字"
            ))

        # 检查章节内容深度
        section_contents = re.split(r"^##\s+.+$", content, flags=re.MULTILINE)[1:]
        shallow_sections = []
        for idx, section_content in enumerate(section_contents):
            if len(section_content.strip()) < 100:
                shallow_sections.append(sections[idx] if idx < len(sections) else f"章节 {idx+1}")

        if shallow_sections:
            issues.append(CheckIssue(
                severity="minor",
                description=f"以下章节内容偏短：{', '.join(shallow_sections[:3])}",
                suggestion="扩充这些章节的内容，增加分析深度"
            ))

        return issues

    def _check_citations(self, content: str) -> list[CheckIssue]:
        """检查引用格式。"""
        issues = []

        # 检查标准引用格式 [1], [2], ...
        standard_refs = re.findall(r"\[\d+\]", content)
        # 检查证据引用（如果还存在的话）
        evidence_refs = re.findall(r"\[evidence:[\w-]+\]", content)

        if evidence_refs:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章包含未转换的证据引用格式（{len(evidence_refs)} 处）",
                suggestion="将 [evidence:xxx] 转换为标准引用编号 [1], [2] 等"
            ))

        # 检查是否有对应的参考文献
        if standard_refs or evidence_refs:
            if "## 参考文献" not in content and "## References" not in content:
                issues.append(CheckIssue(
                    severity="major",
                    description="文章包含引用但缺少参考文献章节",
                    suggestion="在文章末尾添加参考文献章节"
                ))

        # 检查引用密度 - 引用应该均匀分布在文章中
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        cited_paragraphs = sum(1 for p in paragraphs if re.search(r"\[\d+\]", p))
        if len(paragraphs) > 3 and cited_paragraphs / len(paragraphs) < 0.3:
            issues.append(CheckIssue(
                severity="minor",
                description="引用覆盖度偏低，部分段落缺少引用支持",
                suggestion="在关键论点处添加引用支持"
            ))

        # 检查是否有过度引用（连续多个引用）
        excessive_citation = re.findall(r"(\[\d+\].*?){3,}", content)
        if excessive_citation:
            issues.append(CheckIssue(
                severity="minor",
                description="检测到连续多处密集引用",
                suggestion="适当整合引用，避免引用堆砌"
            ))

        return issues