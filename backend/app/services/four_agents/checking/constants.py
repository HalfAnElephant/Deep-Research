"""Constants for the checking agent."""

from __future__ import annotations

import re
from typing import Final

# 需要检测的禁止模式
FORBIDDEN_PATTERNS: Final[list[tuple[str, str, str]]] = [
    (r"_taskId:\s*\S+_", "内部任务 ID 泄露", "critical"),
    (r"\#\#\s*AI\s*综合解读", "AI 提示词泄露", "critical"),
    (r"\#\#\s*输出格式", "输出格式信息泄露", "major"),
    (r"\#\#\s*Trace\s*Section", "调试信息泄露", "major"),
    (r"\[locked\]", "锁定标记泄露", "minor"),
    (r"system\s*prompt", "系统提示词泄露", "critical"),
    (r"你是.*助手", "角色设定泄露", "major"),
]

# "机器味"检测模式 - 快速初筛
MECHANICAL_PATTERNS: Final[list[tuple[str, str, str]]] = [
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
MIXED_LANGUAGE_PATTERNS: Final[list[tuple[str, str, str]]] = [
    (r"Received:?\s*\w+\s*\d+", "期刊格式标记泄露（Received）", "critical"),
    (r"Accepted:?\s*\w+\s*\d+", "期刊格式标记泄露（Accepted）", "critical"),
    (r"Published:?\s*\w+\s*\d+", "期刊格式标记泄露（Published）", "critical"),
    (r"Shanghai.*\d{4}.*A\s*$", "地址信息泄露", "major"),
]

# 垃圾内容检测模式
GARBAGE_CONTENT_PATTERNS: Final[list[tuple[str, str, str]]] = [
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
NAVIGATION_PATTERNS: Final[list[tuple[str, str, str]]] = [
    (r'下载[：:]\s*\d+\s+页数[：:]', "页面导航元素（CNKI）", "major"),
    (r'引文网络\s*参考文献', "页面导航元素（CNKI）", "major"),
    (r'#####\s*引文网络', "页面导航元素（CNKI）", "major"),
    (r'CNKI\s*AI阅读', "页面导航元素（CNKI）", "minor"),
    (r'原版阅读|HTML阅读|CAJ下载|在线阅读', "页面导航元素", "major"),
]

# 乱码和异常字符检测
GARBAGE_UNICODE_PATTERNS: Final[list[tuple[str, str, str]]] = [
    # 检测大量连续 Unicode 转义
    (r'\\u[0-9a-fA-F]{4}.*?\\u[0-9a-fA-F]{4}.*?\\u[0-9a-fA-F]{4}',
     "Unicode 转义序列堆积", "critical"),
    # 检测印度语、阿拉伯语等非中文内容在中文文章中
    (r'[\u0900-\u097F]{3,}', "梵文/印地文字符", "critical"),
    (r'[\u0A00-\u0A7F]{3,}', "古木基文字符", "critical"),
    (r'[\u0C00-\u0C7F]{3,}', "泰卢固文字符", "critical"),
    # 检测无意义的中文词汇堆砌
    (r'[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}\s+[\u4e00-\u9fff]{2}', "无意义词汇堆砌", "major"),
]

# 参考文献章节标题正则
REFERENCE_HEADING_PATTERN: Final[re.Pattern] = re.compile(
    r"^##\s+(参考文献|References)\s*$", re.MULTILINE | re.IGNORECASE
)

# LLM 提示词模板
MECHANICAL_TONE_PROMPT_TEMPLATE: Final[str] = """请评估以下学术论文片段的写作质量，检测是否存在"机器味"问题：

{content}

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
