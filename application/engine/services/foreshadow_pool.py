"""
伏笔投资池 — CFPG: Codified Foreshadowing-Payoff Generation

对标 arXiv:2601.07033 (2026-01)
"Codified Foreshadowing-Payoff Text Generation"

核心创新：
1. 编码 Foreshadow-Trigger-Payoff 三元组为可执行因果谓词
2. 动态 Foreshadow Pool（有限状态机追踪未结算承诺）
3. payoff 激活仅在叙事上下文满足触发条件时才被授权
4. 显著减少"Chekhov's guns left unfired"

PlotPilot 落地：伏笔投资池 — 设置→等待触发→回收，状态机驱动
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ForeshadowStatus(str, Enum):
    SET = "set"              # 已设伏
    ACTIVE = "active"        # 活跃中（条件部分满足）
    TRIGGERED = "triggered"  # 触发条件满足，等待回收
    PAID_OFF = "paid_off"    # 已回收
    EXPIRED = "expired"      # 超时未回收
    ABANDONED = "abandoned"  # 主动放弃


@dataclass
class ForeshadowEntry:
    """单个伏笔条目"""
    id: str = ""
    description: str = ""               # 伏笔内容
    set_chapter: int = 0                # 设置章节
    trigger_condition: str = ""         # 触发条件（自然语言）
    trigger_predicate: str = ""         # 触发谓词（可执行）
    payoff_description: str = ""        # 回收时大致应如何回收
    payoff_predicate: str = ""          # 回收谓词（可执行）
    promised_chapter: int = 0           # 承诺回收章节
    status: ForeshadowStatus = ForeshadowStatus.SET
    set_at: str = ""                    # 设置时间
    triggered_at: str = ""              # 触发时间
    paid_off_at: str = ""               # 回收时间
    priority: int = 1                   # 1-5，越高越重要
    tags: List[str] = field(default_factory=list)


@dataclass
class PoolState:
    """伏笔池整体状态"""
    total_set: int = 0
    active: int = 0
    triggered: int = 0
    paid_off: int = 0
    expired: int = 0
    payoff_rate: float = 0.0           # 回收率
    avg_wait_chapters: float = 0.0     # 平均回收等待章节数
    critical_expiring: List[ForeshadowEntry] = field(default_factory=list)


class ForeshadowPool:
    """
    伏笔投资池 — 有限状态机驱动的因果承诺追踪

    ┌──────┐   条件部分满足   ┌────────┐   条件完全满足   ┌──────────┐   成功回收   ┌──────────┐
    │ SET  │ ──────────────→ │ ACTIVE │ ─────────────→ │ TRIGGERED│ ───────────→│ PAID_OFF │
    └──────┘                  └────────┘                 └──────────┘              └──────────┘
        │                          │                         │                         │
        └──────────────────────────┴─────────────────────────┴─────────────────────────┘
                                    超时 → EXPIRED
                                  主动 → ABANDONED
    """

    MAX_ACTIVE_FORESHADOWS = 15   # 最多同时活跃的伏笔数
    EXPIRE_AFTER_CHAPTERS = 20    # 超出承诺章节多久后过期

    def __init__(self):
        self._pool: Dict[str, ForeshadowEntry] = {}
        self._pool_history: List[ForeshadowEntry] = []

    def set_foreshadow(
        self,
        description: str,
        trigger_condition: str,
        payoff_description: str,
        set_chapter: int = 0,
        promised_chapter: int = 0,
        priority: int = 1,
        tags: List[str] | None = None,
    ) -> ForeshadowEntry:
        """设置新的伏笔"""
        entry = ForeshadowEntry(
            id=f"FS_{uuid.uuid4().hex[:8]}",
            description=description,
            trigger_condition=trigger_condition,
            payoff_description=payoff_description,
            set_chapter=set_chapter,
            promised_chapter=promised_chapter or set_chapter + 10,
            status=ForeshadowStatus.SET,
            set_at=datetime.now(timezone.utc).isoformat(),
            priority=priority,
            tags=tags or [],
        )

        if len([e for e in self._pool.values() if e.status in (ForeshadowStatus.SET, ForeshadowStatus.ACTIVE)]) >= self.MAX_ACTIVE_FORESHADOWS:
            # 伏笔池满了——降低最低优先级的伏笔
            lowest = min(
                (e for e in self._pool.values() if e.status in (ForeshadowStatus.SET, ForeshadowStatus.ACTIVE)),
                key=lambda e: e.priority,
                default=None,
            )
            if lowest and lowest.priority < entry.priority:
                lowest.status = ForeshadowStatus.ABANDONED
                logger.info(f"[ForeshadowPool] 放弃低优先级伏笔 {lowest.id} 为新伏笔 {entry.id} 让路")

        self._pool[entry.id] = entry
        logger.info(f"[ForeshadowPool] 设置伏笔 {entry.id}: {description[:50]}")
        return entry

    def trigger_if_ready(self, chapter_number: int, chapter_context: Dict[str, Any]) -> List[ForeshadowEntry]:
        """检查并触发满足条件的伏笔"""
        triggered: List[ForeshadowEntry] = []

        for entry in self._pool.values():
            if entry.status not in (ForeshadowStatus.SET, ForeshadowStatus.ACTIVE):
                continue

            if self._check_condition(entry, chapter_context):
                entry.status = ForeshadowStatus.TRIGGERED
                entry.triggered_at = datetime.now(timezone.utc).isoformat()
                triggered.append(entry)
                logger.info(f"[ForeshadowPool] 触发伏笔 {entry.id}: {entry.description[:50]}")

            elif self._partially_ready(entry, chapter_context):
                entry.status = ForeshadowStatus.ACTIVE

        return triggered

    def payoff(self, entry_id: str, content_hint: str = "") -> bool:
        """回收一个伏笔"""
        entry = self._pool.get(entry_id)
        if entry is None:
            return False
        if entry.status != ForeshadowStatus.TRIGGERED:
            logger.warning(f"[ForeshadowPool] 伏笔 {entry_id} 未触发，无法回收 (status={entry.status})")
            return False

        entry.status = ForeshadowStatus.PAID_OFF
        entry.paid_off_at = datetime.now(timezone.utc).isoformat()
        self._pool_history.append(entry)
        logger.info(f"[ForeshadowPool] 回收伏笔 {entry_id}: {entry.description[:50]}")
        return True

    def expire_check(self, current_chapter: int) -> List[ForeshadowEntry]:
        """检查并过期超时的伏笔"""
        expired: List[ForeshadowEntry] = []
        for entry in self._pool.values():
            if entry.status in (ForeshadowStatus.PAID_OFF, ForeshadowStatus.EXPIRED, ForeshadowStatus.ABANDONED):
                continue
            if current_chapter > entry.promised_chapter + self.EXPIRE_AFTER_CHAPTERS:
                entry.status = ForeshadowStatus.EXPIRED
                expired.append(entry)
                logger.warning(f"[ForeshadowPool] 伏笔 {entry.id} 已过期: {entry.description[:50]}")
        return expired

    def get_pool_state(self) -> PoolState:
        """获取伏笔池当前状态"""
        entries = list(self._pool.values())
        statuses = {
            ForeshadowStatus.SET: [e for e in entries if e.status == ForeshadowStatus.SET],
            ForeshadowStatus.ACTIVE: [e for e in entries if e.status == ForeshadowStatus.ACTIVE],
            ForeshadowStatus.TRIGGERED: [e for e in entries if e.status == ForeshadowStatus.TRIGGERED],
            ForeshadowStatus.PAID_OFF: [e for e in entries if e.status == ForeshadowStatus.PAID_OFF],
            ForeshadowStatus.EXPIRED: [e for e in entries if e.status == ForeshadowStatus.EXPIRED],
        }

        paid = statuses[ForeshadowStatus.PAID_OFF]
        all_completed = paid + [e for e in entries if e.status in (ForeshadowStatus.EXPIRED, ForeshadowStatus.ABANDONED)]
        payoff_rate = len(paid) / max(len(all_completed), 1) if all_completed else 0.0

        wait_chapters = [e.paid_off_at or 0 for e in paid if e.set_chapter > 0]
        avg_wait = sum(wait_chapters) / max(len(wait_chapters), 1) if wait_chapters else 0

        # 即将过期的关键伏笔
        expiring = [
            e for e in entries
            if e.status in (ForeshadowStatus.SET, ForeshadowStatus.ACTIVE)
            and e.priority >= 4
        ]

        return PoolState(
            total_set=len(entries),
            active=len(statuses[ForeshadowStatus.ACTIVE]),
            triggered=len(statuses[ForeshadowStatus.TRIGGERED]),
            paid_off=len(paid),
            expired=len(statuses[ForeshadowStatus.EXPIRED]),
            payoff_rate=round(payoff_rate, 2),
            avg_wait_chapters=round(avg_wait, 1),
            critical_expiring=expiring,
        )

    def _check_condition(self, entry: ForeshadowEntry, context: Dict[str, Any]) -> bool:
        """检查触发条件是否完全满足"""
        cond = entry.trigger_condition.lower()
        # 简化的文本匹配（生产环境应使用更精确的谓语匹配）
        for key, value in context.items():
            if key.lower() in cond and str(value).lower() in cond:
                return True
        return False

    def _partially_ready(self, entry: ForeshadowEntry, context: Dict[str, Any]) -> bool:
        """检查触发条件是否部分满足"""
        cond = entry.trigger_condition.lower()
        matched = 0
        total_keywords = max(len(cond.split()), 1) * 0.3
        for key in context:
            if key.lower() in cond:
                matched += 1
        return matched >= total_keywords
