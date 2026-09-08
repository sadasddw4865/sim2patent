"""sim2patent.llm —— DeepSeek(OpenAI 兼容)客户端与接口抽象。

设计要点:
- 上层只依赖 `LLMBackend` 的两个方法(chat_json / chat_text),
  方便替换为其它厂商或本地模型;
- openai 包为惰性导入:未安装时给出清晰报错;
- 无 API key 时不会在此崩溃 —— 由 bridge/cli 决定降级为 mock。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .config import Settings

try:  # 惰性导入,便于在未安装 openai 的纯解析场景下使用
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


class LLMError(RuntimeError):
    """LLM 调用/解析失败。"""


class LLMBackend:
    """LLM 调用抽象:两个方法,全部以结构化 JSON 往返。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        s = settings or Settings()
        if not s.has_key:
            raise LLMError(
                "缺少 DEEPSEEK_API_KEY。请设置环境变量,或用 --mock 走离线模式。"
            )
        if OpenAI is None:  # pragma: no cover
            raise LLMError("未安装 openai 包,请先 `pip install -r requirements.txt`")
        self.model = s.model
        self.temperature = s.temperature
        self.timeout = s.timeout
        self._client = OpenAI(api_key=s.api_key, base_url=s.base_url, timeout=s.timeout)

    # -- 公共接口 ----------------------------------------------------------
    def chat_json(self, system: str, user: str, temperature: Optional[float] = None) -> dict[str, Any]:
        """强制返回 JSON 对象;解析失败抛 LLMError(由调用方决定是否重试)。"""
        text = self._complete(system, user, temperature=temperature or self.temperature)
        return self._load_json(text)

    def chat_text(self, system: str, user: str, temperature: Optional[float] = None) -> str:
        return self._complete(system, user, temperature=temperature or self.temperature)

    # -- 内部 --------------------------------------------------------------
    def _complete(self, system: str, user: str, temperature: float) -> str:
        """带 JSON 模式调用;若网关不支持 response_format 参数则退化为普通调用。"""
        last_exc: Optional[Exception] = None
        for use_json_mode in (True, False):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = self._client.chat.completions.create(**kwargs)
            except Exception as exc:  # 网络/鉴权/限流/参数不支持
                last_exc = exc
                continue
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
        raise LLMError(f"LLM 调用失败(JSON 模式与普通模式均失败): {last_exc}") from last_exc

    @staticmethod
    def _load_json(text: str) -> dict[str, Any]:
        # 容忍 ```json ... ``` 围栏
        t = text.strip()
        if t.startswith("```"):
            t = t.strip("`")
            if t.lower().startswith("json"):
                t = t[4:]
        try:
            obj = json.loads(t)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM 未返回合法 JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise LLMError("LLM 返回的 JSON 不是对象")
        return obj
