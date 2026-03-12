"""Validator classes for the checking agent."""

from __future__ import annotations

import logging
import re
from typing import Protocol

from .constants import (
    FORBIDDEN_PATTERNS,
    GARBAGE_CONTENT_PATTERNS,
    GARBAGE_UNICODE_PATTERNS,
    MECHANICAL_PATTERNS,
    MIXED_LANGUAGE_PATTERNS,
    NAVIGATION_PATTERNS,
    REFERENCE_HEADING_PATTERN,
)
from .models import CheckIssue

logger = logging.getLogger(__name__)


class ContentValidator(Protocol):
    """Protocol for content validators."""

    def validate(self, content: str) -> list[CheckIssue]:
        """Validate content and return list of issues."""
        ...


class PatternValidator:
    """Validator that checks content against regex patterns."""

    def __init__(
        self,
        patterns: list[tuple[str, str, str]],
        suggestion_template: str = "删除或修改该内容",
    ) -> None:
        self.patterns = patterns
        self.suggestion_template = suggestion_template

    def validate(self, content: str) -> list[CheckIssue]:
        """Check content against all patterns."""
        issues = []
        for pattern, description, severity in self.patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=description,
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion=self.suggestion_template,
                ))
        return issues


class PromptLeakageValidator(PatternValidator):
    """Validator for prompt leakage detection."""

    def __init__(self) -> None:
        super().__init__(
            patterns=FORBIDDEN_PATTERNS,
            suggestion_template="删除或修改该内容",
        )


class MechanicalToneValidator(PatternValidator):
    """Validator for mechanical tone detection."""

    def __init__(self) -> None:
        super().__init__(
            patterns=MECHANICAL_PATTERNS,
            suggestion_template="使用过渡语句替换模板标签，如'在...方面'、'值得注意的是'等",
        )

    def validate(self, content: str) -> list[CheckIssue]:
        """Check content for mechanical tone patterns."""
        issues = []
        for pattern, description, severity in self.patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=f"检测到{description}，建议使用自然的学术写作风格",
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion=self.suggestion_template,
                ))

        # Check for mixed language patterns
        for pattern, description, severity in MIXED_LANGUAGE_PATTERNS:
            matches = re.finditer(
                pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                issues.append(CheckIssue(
                    severity=severity,
                    description=description,
                    location=f"位置 {match.start()}-{match.end()}",
                    suggestion="删除或翻译该内容为中文",
                ))

        return issues


class GarbageContentValidator(PatternValidator):
    """Validator for garbage content detection."""

    def __init__(self) -> None:
        super().__init__(
            patterns=GARBAGE_CONTENT_PATTERNS,
            suggestion_template="删除该内容，并检查证据来源",
        )

    def validate(self, content: str) -> list[CheckIssue]:
        """Check content for garbage patterns including navigation elements and URLs."""
        issues = super().validate(content)

        # Check for navigation patterns
        nav_validator = PatternValidator(
            patterns=NAVIGATION_PATTERNS,
            suggestion_template="删除该内容，并检查证据来源",
        )
        for issue in nav_validator.validate(content):
            issue.description = f"检测到{issue.description}，页面导航内容不应出现在文章中"
            issues.append(issue)

        # Check for Unicode garbage patterns
        unicode_validator = PatternValidator(
            patterns=GARBAGE_UNICODE_PATTERNS,
            suggestion_template="删除该内容段落，从可靠的证据源重新获取",
        )
        for issue in unicode_validator.validate(content):
            issue.description = f"检测到{issue.description}，这是明显的乱码或垃圾内容"
            issues.append(issue)
            # Limit critical issues
            if len([i for i in issues if i.severity == "critical"]) > 10:
                break

        # Check for URLs in body content (not in reference section)
        issues.extend(self._check_body_urls(content))

        return issues

    def _check_body_urls(self, content: str) -> list[CheckIssue]:
        """Check for URLs in the body content (excluding reference section)."""
        issues = []
        ref_section_idx = content.find("## 参考文献")
        if ref_section_idx == -1:
            ref_section_idx = content.find("## References")

        if ref_section_idx > 0:
            body_content = content[:ref_section_idx]
            url_matches = re.finditer(r'https?://\S+', body_content)
            for match in url_matches:
                # Exclude citation-style URLs [text](url)
                context = body_content[max(0, match.start()-50):match.end()+50]
                if not re.search(r'\[.*?\]\(' + re.escape(match.group()) + r'\)', context):
                    issues.append(CheckIssue(
                        severity="major",
                        description="正文中出现裸露的网址链接",
                        location=f"位置 {match.start()}-{match.end()}",
                        suggestion="将网址移到参考文献章节，正文中使用引用编号 [1] 等形式",
                    ))
        return issues


class StructureValidator:
    """Validator for article structure."""

    MIN_WORD_COUNT = 1000
    MIN_SECTIONS = 2
    MIN_SECTION_CONTENT_LENGTH = 100

    def __init__(self) -> None:
        self.ref_pattern = REFERENCE_HEADING_PATTERN

    def validate(self, content: str) -> list[CheckIssue]:
        """Check article structure."""
        issues = []
        body_content = self._strip_reference_section(content)

        # Check title
        if not content.strip().startswith("# "):
            issues.append(CheckIssue(
                severity="major",
                description="文章缺少主标题",
                suggestion="在文章开头添加一级标题",
            ))

        # Check sections
        sections = re.findall(r"^##\s+.+$", body_content, re.MULTILINE)
        if len(sections) < self.MIN_SECTIONS:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章章节过少（{len(sections)} 个），建议至少包含引言、主体和结论",
                suggestion="添加更多章节以增强结构完整性",
            ))

        # Check for intro section
        has_intro = any(re.search(r'摘|引言|背景|简介|概述', s) for s in sections)
        if not has_intro:
            issues.append(CheckIssue(
                severity="minor",
                description="文章缺少摘要或引言章节",
                suggestion="考虑添加摘要或引言章节来说明研究目的",
            ))

        # Check for conclusion section
        has_conclusion = any(re.search(r'结论|总结|建议|展望', s) for s in sections)
        if not has_conclusion:
            issues.append(CheckIssue(
                severity="minor",
                description="文章缺少结论章节",
                suggestion="考虑添加结论章节总结研究发现",
            ))

        # Check word count
        word_count = len(body_content.strip())
        if word_count < self.MIN_WORD_COUNT:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章内容过短（{word_count} 字）",
                suggestion=f"扩充文章内容至至少 {self.MIN_WORD_COUNT} 字",
            ))

        # Check section content depth
        issues.extend(self._check_section_depth(body_content, sections))

        return issues

    def _strip_reference_section(self, content: str) -> str:
        """Remove reference section from content for analysis."""
        match = self.ref_pattern.search(content)
        if not match:
            return content
        return content[:match.start()].rstrip()

    def _check_section_depth(self, body_content: str, sections: list[str]) -> list[CheckIssue]:
        """Check if sections have sufficient content."""
        issues = []
        section_contents = re.split(
            r"^##\s+.+$", body_content, flags=re.MULTILINE)[1:]
        shallow_sections = []
        for idx, section_content in enumerate(section_contents):
            if len(section_content.strip()) < self.MIN_SECTION_CONTENT_LENGTH:
                section_name = sections[idx] if idx < len(sections) else f"章节 {idx+1}"
                shallow_sections.append(section_name)

        if shallow_sections:
            issues.append(CheckIssue(
                severity="minor",
                description=f"以下章节内容偏短：{', '.join(shallow_sections[:3])}",
                suggestion="扩充这些章节的内容，增加分析深度",
            ))
        return issues


class CitationValidator:
    """Validator for citation format."""

    def validate(self, content: str) -> list[CheckIssue]:
        """Check citation format in the article."""
        issues = []

        # Check standard reference format [1], [2], ...
        standard_refs = re.findall(r"\[\d+\]", content)
        # Check for evidence citations
        evidence_refs = re.findall(r"\[evidence:[\w-]+\]", content)

        if evidence_refs:
            issues.append(CheckIssue(
                severity="major",
                description=f"文章包含未转换的证据引用格式（{len(evidence_refs)} 处）",
                suggestion="将 [evidence:xxx] 转换为标准引用编号 [1], [2] 等",
            ))

        # Check for reference section
        if standard_refs or evidence_refs:
            if "## 参考文献" not in content and "## References" not in content:
                issues.append(CheckIssue(
                    severity="major",
                    description="文章包含引用但缺少参考文献章节",
                    suggestion="在文章末尾添加参考文献章节",
                ))

        # Check citation density
        issues.extend(self._check_citation_density(content))

        # Check for excessive citations
        issues.extend(self._check_excessive_citations(content))

        return issues

    def _check_citation_density(self, content: str) -> list[CheckIssue]:
        """Check if citations are distributed throughout the article."""
        issues = []
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        cited_paragraphs = sum(
            1 for p in paragraphs if re.search(r"\[\d+\]", p))
        if len(paragraphs) > 3 and cited_paragraphs / len(paragraphs) < 0.3:
            issues.append(CheckIssue(
                severity="minor",
                description="引用覆盖度偏低，部分段落缺少引用支持",
                suggestion="在关键论点处添加引用支持",
            ))
        return issues

    def _check_excessive_citations(self, content: str) -> list[CheckIssue]:
        """Check for clusters of excessive citations."""
        issues = []
        excessive_citation = re.findall(r"(\[\d+\].*?){3,}", content)
        if excessive_citation:
            issues.append(CheckIssue(
                severity="minor",
                description="检测到连续多处密集引用",
                suggestion="适当整合引用，避免引用堆砌",
            ))
        return issues
