"""
智能模型路由器 — 根据任务类型自动选择最优模型/速度层

任务分类 → 模型类型：
- planning / analysis   → fast 层 (便宜快模型)
- creative_writing      → creative 层 (强模型)
- review / critique     → fast 层
- rewrite               → creative 层
- enrichment            → creative 层
- classification        → fast 层
- summarization         → fast 层

支持降级：主模型失败时自动切换到备选模型
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    PLANNING = "planning"
    CREATIVE_WRITING = "creative_writing"
    REVIEW = "review"
    REWRITE = "rewrite"
    ENRICHMENT = "enrichment"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    ANALYSIS = "analysis"
    DEFAULT = "default"


@dataclass
class ModelTier:
    tier: str = "fast"  # fast | creative
    model: str = ""
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    priority: int = 1  # 1=主, 2=降级


@dataclass
class RouteResult:
    model: str = ""
    provider: str = ""
    tier: str = ""
    fallback_used: bool = False


class SmartRouter:
    """按任务类型智能选择模型"""

    # 任务 → 模型层的默认映射
    TASK_TO_TIER: Dict[TaskType, str] = {
        TaskType.PLANNING: "fast",
        TaskType.REVIEW: "fast",
        TaskType.CLASSIFICATION: "fast",
        TaskType.SUMMARIZATION: "fast",
        TaskType.EXTRACTION: "fast",
        TaskType.ANALYSIS: "fast",
        TaskType.CREATIVE_WRITING: "creative",
        TaskType.REWRITE: "creative",
        TaskType.ENRICHMENT: "creative",
        TaskType.DEFAULT: "fast",
    }

    # 速度层的默认模型（可配置）
    FAST_MODELS: List[ModelTier] = [
        ModelTier(tier="fast", model="deepseek-v4-flash", provider="deepseek", priority=1),
        ModelTier(tier="fast", model="doubao-seed-2-0-mini-260215", provider="volcengine", priority=2),
    ]
    CREATIVE_MODELS: List[ModelTier] = [
        ModelTier(tier="creative", model="deepseek-v4-pro", provider="deepseek", priority=1),
        ModelTier(tier="creative", model="claude-sonnet-4-20250514", provider="anthropic", priority=2),
    ]

    def __init__(self):
        self._fast_pool = list(self.FAST_MODELS)
        self._creative_pool = list(self.CREATIVE_MODELS)
        self._cache: Dict[str, str] = {}  # context_key → last_used_model

    def route(self, task_type: TaskType = TaskType.DEFAULT) -> RouteResult:
        """根据任务类型选择最优模型"""
        tier = self.TASK_TO_TIER.get(task_type, "fast")
        pool = self._fast_pool if tier == "fast" else self._creative_pool
        model = pool[0]  # 取优先级最高的
        return RouteResult(model=model.model, provider=model.provider, tier=tier)

    def route_fallback(self, task_type: TaskType, previous_model: str) -> RouteResult | None:
        """从降级池中选择备选模型"""
        tier = self.TASK_TO_TIER.get(task_type, "fast")
        pool = self._fast_pool if tier == "fast" else self._creative_pool

        for model in pool:
            if model.model != previous_model:
                return RouteResult(model=model.model, provider=model.provider, tier=tier, fallback_used=True)
        return None

    def get_temperature(self, task_type: TaskType) -> float:
        """按任务类型返回推荐温度"""
        temps = {
            TaskType.PLANNING: 0.8,
            TaskType.CREATIVE_WRITING: 1.0,
            TaskType.REVIEW: 0.3,
            TaskType.REWRITE: 0.7,
            TaskType.ENRICHMENT: 0.9,
            TaskType.CLASSIFICATION: 0.2,
            TaskType.SUMMARIZATION: 0.4,
            TaskType.EXTRACTION: 0.3,
            TaskType.ANALYSIS: 0.5,
        }
        return temps.get(task_type, 0.7)

    def get_max_tokens(self, task_type: TaskType) -> int:
        """按任务类型推荐 max_tokens"""
        tokens = {
            TaskType.PLANNING: 2000,
            TaskType.CREATIVE_WRITING: 4000,
            TaskType.REVIEW: 800,
            TaskType.REWRITE: 3000,
            TaskType.ENRICHMENT: 2000,
            TaskType.CLASSIFICATION: 400,
            TaskType.SUMMARIZATION: 1000,
            TaskType.EXTRACTION: 1500,
            TaskType.ANALYSIS: 1000,
        }
        return tokens.get(task_type, 2000)


# 全局单例
_smart_router: SmartRouter | None = None


def get_router() -> SmartRouter:
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartRouter()
    return _smart_router
