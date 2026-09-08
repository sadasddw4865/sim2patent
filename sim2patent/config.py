"""sim2patent.config —— 从环境变量读取配置,零第三方依赖(纯 os)。"""
from __future__ import annotations

import os

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com"


class Settings:
    """运行期配置。全部来自环境变量:

    DEEPSEEK_API_KEY   必填(除非 --mock):DeepSeek API 密钥
    DEEPSEEK_BASE_URL  可选:API 网关,默认 https://api.deepseek.com
    SIM2PATENT_MODEL   可选:模型名,默认 deepseek-chat
    SIM2PATENT_TIMEOUT 可选:HTTP 超时秒数,默认 120
    """

    def __init__(self) -> None:
        self.api_key: str = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.base_url: str = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
        self.model: str = os.environ.get("SIM2PATENT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        try:
            self.timeout: float = float(os.environ.get("SIM2PATENT_TIMEOUT", "120"))
        except ValueError:
            self.timeout = 120.0
        self.temperature: float = 0.2

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def describe(self) -> str:
        key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if self.has_key else "(未设置)"
        return (
            f"Settings(model={self.model}, base_url={self.base_url}, "
            f"api_key={key}, temperature={self.temperature})"
        )


settings = Settings()
