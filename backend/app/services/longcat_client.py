"""LongCat API 客户端 - 用于用户交互（不用于文章生成）。"""

from __future__ import annotations

import httpx

from app.core.config import settings


class LongCatClient:
    """LongCat API 客户端，用于用户交互。

    注意：此客户端仅用于用户交互，不用于文章生成。
    文章生成应使用主 LLM（OpenRouter/DeepSeek/OpenAI）。
    """

    BASE_URL = "https://api.longcat.chat/openai/v1"
    MODEL = "LongCat-Flash-Lite"

    def __init__(self, api_key: str | None = None) -> None:
        """初始化 LongCat 客户端。

        Args:
            api_key: API 密钥，如果未提供则从配置中获取。
        """
        self.api_key = api_key or getattr(
            settings, 'longcat_api_key', None) or "ak_2Ks0iy2p02oX0V05UN3Mk7YO38R8R"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端。"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7
    ) -> str:
        """发送聊天请求。

        Args:
            system_prompt: 系统提示词。
            user_message: 用户消息。
            temperature: 温度参数，默认 0.7。

        Returns:
            助手回复文本。

        Raises:
            httpx.HTTPError: HTTP 请求错误。
        """
        response = await self.client.post(
            f"{self.BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": temperature
            }
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def get_greeting(self, topic: str | None = None) -> str:
        """获取欢迎消息。

        Args:
            topic: 可选的研究主题。

        Returns:
            欢迎消息文本。
        """
        system_prompt = (
            "你是深度研究工作台的交互助手。你的职责是：\n"
            "1. 友好地欢迎用户\n"
            "2. 简要介绍系统功能\n"
            "3. 引导用户开始研究\n\n"
            "保持回复简洁、友好，不超过 100 字。"
        )
        user_message = f"用户{f'想要研究「{topic}」' if topic else '刚刚打开应用'}，请给出欢迎消息。"
        return await self.chat(system_prompt, user_message)

    async def explain_status(self, status: str, agent_type: str | None = None) -> str:
        """解释当前状态。

        Args:
            status: 当前状态。
            agent_type: 当前运行的智能体类型（如果有）。

        Returns:
            状态解释文本。
        """
        system_prompt = (
            "你是深度研究工作台的交互助手。你的职责是用简洁的语言解释系统当前正在做什么。\n"
            "保持回复简洁、专业，不超过 50 字。"
        )
        user_message = f"当前状态是「{status}」"
        if agent_type:
            agent_names = {
                "IDEATION": "构思智能体",
                "PLANNING": "规划智能体",
                "WRITING": "写作智能体",
                "CHECKING": "检查智能体"
            }
            user_message += f"，正在运行「{agent_names.get(agent_type, agent_type)}」"
        user_message += "，请简要解释。"
        return await self.chat(system_prompt, user_message)

    async def suggest_next_action(self, status: str) -> str:
        """建议下一步操作。

        Args:
            status: 当前状态。

        Returns:
            建议的下一步操作文本。
        """
        system_prompt = (
            "你是深度研究工作台的交互助手。你的职责是根据当前状态建议用户下一步可以做什么。\n"
            "保持回复简洁、实用，不超过 50 字。"
        )
        user_message = f"当前状态是「{status}」，请建议用户下一步可以做什么。"
        return await self.chat(system_prompt, user_message)

    async def summarize_suppressed_writer_note(self, *, topic: str, segments: list[str]) -> str:
        """将被拦截的写作过程说明转成用户可见的简短气泡。"""
        cleaned_segments = [segment.strip()
                            for segment in segments if segment.strip()]
        if not cleaned_segments:
            return ""

        system_prompt = (
            "你是深度研究工作台的写作提示助手。"
            "系统刚刚拦截了一段不应进入正式文章的写作过程说明。"
            "请把它改写成面向用户的简短 Agent 提示，说明发生了什么以及系统如何处理。"
            "要求：使用简洁中文，不超过 80 字，不要复述原文细节，不要输出证据 ID，"
            "并明确说明这段内容不会进入正文。"
        )
        snippet = "\n\n".join(cleaned_segments[:3])[:1200]
        user_message = (
            f"研究主题：{topic}\n"
            "以下内容是被拦截的写作过程说明，请转写为一条用户可见提示：\n"
            f"{snippet}"
        )
        try:
            response = await self.chat(system_prompt, user_message, temperature=0.2)
            return response.strip()
        except Exception:
            return "已拦截一段写作过程说明，系统已转为内部处理提示，不会写入正式文章。"


# 全局实例
longcat_client = LongCatClient()
