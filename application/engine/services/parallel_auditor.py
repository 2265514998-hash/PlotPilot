"""
并行审计引擎 — 将单块审计拆为 6 个并行维度

每个维度：
- 独立运行（asyncio.gather）
- 独立超时（默认 30s）
- 独立重试（最多 2 次）
- 失败维度不影响其他维度
- 结果聚合为统一报告
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AuditDimension(str, Enum):
    STYLE = "style"             # 文风一致性
    NARRATIVE = "narrative"     # 叙事同步
    KNOWLEDGE = "knowledge"     # 知识图谱推断
    FORESHADOW = "foreshadow"   # 伏笔追踪
    CHARACTER = "character"     # 角色一致性
    TENSION = "tension"         # 张力评分


@dataclass
class DimensionResult:
    dimension: AuditDimension
    status: str = "pending"  # success | failed | timeout | skipped
    data: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    duration_ms: float = 0.0
    error: str = ""
    retries: int = 0


@dataclass
class AuditReport:
    chapter_id: str = ""
    dimensions: List[DimensionResult] = field(default_factory=list)
    overall_score: float = 0.0
    passed_count: int = 0
    failed_count: int = 0
    total_duration_ms: float = 0.0
    summary: str = ""


class ParallelAuditor:
    """并行执行 6 个审计维度，聚合结果"""

    DIMENSIONS = list(AuditDimension)
    DEFAULT_TIMEOUT = 30  # 每维度 30 秒超时
    MAX_RETRIES = 2       # 每维度最多重试 2 次

    def __init__(self, llm_service=None, chapter_service=None, bible_repo=None):
        self._llm = llm_service
        self._chapter_service = chapter_service
        self._bible_repo = bible_repo

    async def audit_chapter(
        self,
        chapter_id: str,
        chapter_content: str,
        novel_id: str = "",
        dimensions: List[AuditDimension] | None = None,
        timeout: float | None = None,
    ) -> AuditReport:
        """并行审计一个章节"""

        dims = dimensions or self.DIMENSIONS
        t = timeout or self.DEFAULT_TIMEOUT

        start = asyncio.get_event_loop().time()
        tasks = {dim: self._audit_one(dim, chapter_id, chapter_content, novel_id, t) for dim in dims}

        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results: List[DimensionResult] = []

        for dim, result in zip(tasks.keys(), gathered):
            if isinstance(result, Exception):
                results.append(DimensionResult(dimension=dim, status="failed", error=str(result)))
            else:
                results.append(result)

        passed = sum(1 for r in results if r.status == "success")
        failed = len(results) - passed

        avg_score = sum(r.score for r in results if r.status == "success") / max(passed, 1)
        elapsed = (asyncio.get_event_loop().time() - start) * 1000

        return AuditReport(
            chapter_id=chapter_id,
            dimensions=results,
            overall_score=round(avg_score, 2),
            passed_count=passed,
            failed_count=failed,
            total_duration_ms=round(elapsed, 0),
            summary=f"审计完成：{passed}/{len(results)} 维度通过，综合评分 {avg_score:.1f}/5",
        )

    async def _audit_one(
        self, dim: AuditDimension, chapter_id: str, content: str, novel_id: str, timeout: float,
    ) -> DimensionResult:
        """单维度审计（带重试 + 超时保护）"""
        result = DimensionResult(dimension=dim)
        start = asyncio.get_event_loop().time()

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                handler = self._get_handler(dim)
                data = await asyncio.wait_for(handler(content, chapter_id, novel_id), timeout=timeout)
                result.status = "success"
                result.data = data or {}
                result.score = data.get("score", 3.0) if isinstance(data, dict) else 3.0
                result.retries = attempt
                break
            except asyncio.TimeoutError:
                result.status = "timeout"
                result.error = f"{dim.value} 审计超时 ({timeout}s)"
                result.retries = attempt
            except Exception as e:
                result.error = str(e)
                result.retries = attempt
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"[ParallelAuditor] {dim.value} 失败，重试 {attempt + 1}/{self.MAX_RETRIES}: {e}")
                    await asyncio.sleep(1.0 * (attempt + 1))  # 退避
                    continue
                result.status = "failed"

        result.duration_ms = round((asyncio.get_event_loop().time() - start) * 1000, 0)
        return result

    def _get_handler(self, dim: AuditDimension) -> Callable:
        """获取维度处理函数"""
        handlers: Dict[AuditDimension, Callable] = {
            AuditDimension.STYLE: self._audit_style,
            AuditDimension.NARRATIVE: self._audit_narrative,
            AuditDimension.KNOWLEDGE: self._audit_knowledge,
            AuditDimension.FORESHADOW: self._audit_foreshadow,
            AuditDimension.CHARACTER: self._audit_character,
            AuditDimension.TENSION: self._audit_tension,
        }
        return handlers.get(dim, self._audit_skip)

    async def _audit_style(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        """文风审计 — 写在此处作为参考实现，生产环境应连接到 VoiceDriftService"""
        return {"score": 3.5, "status": "mock", "dimension": "style"}

    async def _audit_narrative(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        return {"score": 3.5, "status": "mock", "dimension": "narrative"}

    async def _audit_knowledge(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        return {"score": 3.5, "status": "mock", "dimension": "knowledge"}

    async def _audit_foreshadow(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        return {"score": 3.5, "status": "mock", "dimension": "foreshadow"}

    async def _audit_character(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        return {"score": 3.5, "status": "mock", "dimension": "character"}

    async def _audit_tension(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        return {"score": 3.5, "status": "mock", "dimension": "tension"}

    async def _audit_skip(self, content: str, chapter_id: str, novel_id: str) -> Dict[str, Any]:
        return {"score": 0.0, "status": "skipped"}
