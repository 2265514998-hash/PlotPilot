"""本机 OpenAI 兼容 LLM（Ollama / LM Studio 等）连接辅助。"""
from __future__ import annotations

from urllib.parse import urlparse

# Ollama / LM Studio 等通常不校验 Key，但 OpenAI SDK 要求非空
LOCAL_LLM_PLACEHOLDER_API_KEY = "ollama"


def is_local_openai_compatible_base_url(base_url: str) -> bool:
    """是否为本机回环地址上的 OpenAI 兼容端点。"""
    raw = (base_url or "").strip()
    if not raw:
        return False
    if "://" not in raw:
        raw = f"http://{raw}"
    host = (urlparse(raw).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        return True
    return host.endswith(".localhost")


def effective_local_api_key(api_key: str, base_url: str, protocol: str = "openai") -> str:
    """本地端点无 Key 时使用占位符，避免退回 MockProvider。"""
    key = (api_key or "").strip()
    if key:
        return key
    if protocol == "openai" and is_local_openai_compatible_base_url(base_url):
        return LOCAL_LLM_PLACEHOLDER_API_KEY
    return key
