"""
自适应重试策略 — 替代硬编码 max 3 次重试

特性：
- 按错误类型自适应决策
- 指数退避 + 随机 jitter
- 模型降级支持（主模型 → 备选模型）
- 熔断器状态感知
- 区分临时错误 vs 永久错误
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    TEMPORARY = "temporary"        # 临时错误：超时、限流、网络波动 → 多试几次
    PERMANENT = "permanent"        # 永久错误：API key 无效、权限不足 → 快速失败
    MODEL_SPECIFIC = "model"       # 模型错误：内容过滤、模型不可用 → 尝试降级
    CONTEXT_OVERFLOW = "overflow"  # 上下文超限 → 截断+重试
    UNKNOWN = "unknown"


@dataclass
class RetryConfig:
    max_retries: int = 5
    base_delay: float = 1.0      # 基础等待秒数
    max_delay: float = 30.0       # 最大等待秒数
    jitter: float = 0.3           # 随机抖动比例
    categories: Dict[ErrorCategory, int] = field(default_factory=lambda: {
        ErrorCategory.TEMPORARY: 5,
        ErrorCategory.MODEL_SPECIFIC: 2,
        ErrorCategory.CONTEXT_OVERFLOW: 1,
        ErrorCategory.PERMANENT: 0,
        ErrorCategory.UNKNOWN: 2,
    })
    enable_model_fallback: bool = True


@dataclass
class RetryResult:
    success: bool = False
    data: Any = None
    attempts: int = 0
    final_error: str = ""
    model_fallback_used: bool = False
    total_delay_ms: float = 0.0


class AdaptiveRetry:
    """智能重试：按错误类型决策，支持模型降级"""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """根据异常类型/消息分类"""
        msg = str(error).lower()

        # 临时错误
        if any(kw in msg for kw in ["timeout", "timed out", "rate limit", "too many requests", "connection", "network", "temporarily", "server error", "503", "502", "504"]):
            return ErrorCategory.TEMPORARY

        # 永久错误
        if any(kw in msg for kw in ["401", "403", "invalid api key", "unauthorized", "permission", "forbidden", "insufficient_quota", "billing"]):
            return ErrorCategory.PERMANENT

        # 上下文溢出
        if any(kw in msg for kw in ["context length", "token limit", "too long", "maximum context", "reduce", "truncat"]):
            return ErrorCategory.CONTEXT_OVERFLOW

        # 模型特定
        if any(kw in msg for kw in ["model", "safety", "content filter", "not found", "unavailable", "overloaded"]):
            return ErrorCategory.MODEL_SPECIFIC

        return ErrorCategory.UNKNOWN

    def _delay(self, attempt: int) -> float:
        """指数退避 + jitter"""
        delay = min(self.config.base_delay * (2 ** attempt), self.config.max_delay)
        jitter = delay * self.config.jitter * random.random()
        return delay + jitter

    async def execute(
        self,
        func: Callable[..., Coroutine],
        *args: Any,
        fallback_func: Callable[..., Coroutine] | None = None,
        **kwargs: Any,
    ) -> RetryResult:
        """
        带自适应重试的执行

        Args:
            func: 主调用函数
            fallback_func: 模型降级时的备选函数（需要不同的 model 参数）
        """
        total_delay = 0.0

        for attempt in range(self.config.max_retries + 1):
            try:
                data = await func(*args, **kwargs)
                return RetryResult(success=True, data=data, attempts=attempt + 1, total_delay_ms=total_delay)
            except Exception as e:
                category = self.categorize_error(e)
                max_for_category = self.config.categories.get(category, 2)

                if attempt >= max_for_category:
                    # 尝试模型降级
                    if category == ErrorCategory.MODEL_SPECIFIC and fallback_func and self.config.enable_model_fallback:
                        logger.info(f"[AdaptiveRetry] 模型错误，尝试降级 (attempt {attempt + 1})")
                        try:
                            data = await fallback_func(*args, **kwargs)
                            return RetryResult(success=True, data=data, attempts=attempt + 1, model_fallback_used=True, total_delay_ms=total_delay)
                        except Exception as fe:
                            logger.error(f"[AdaptiveRetry] 降级也失败了: {fe}")
                            return RetryResult(success=False, attempts=attempt + 1, final_error=str(fe), total_delay_ms=total_delay)

                    logger.error(f"[AdaptiveRetry] {category} 错误，已达最大重试次数 {max_for_category}: {e}")
                    return RetryResult(success=False, attempts=attempt + 1, final_error=str(e), total_delay_ms=total_delay)

                if category == ErrorCategory.PERMANENT:
                    # 永久错误不重试
                    return RetryResult(success=False, attempts=0, final_error=str(e), total_delay_ms=total_delay)

                delay = self._delay(attempt)
                total_delay += delay * 1000
                logger.warning(f"[AdaptiveRetry] {category} 错误 (attempt {attempt + 1}/{max_for_category}), {delay:.1f}s 后重试: {e}")
                await asyncio.sleep(delay)

        return RetryResult(success=False, attempts=self.config.max_retries, final_error="max retries exceeded", total_delay_ms=total_delay)
