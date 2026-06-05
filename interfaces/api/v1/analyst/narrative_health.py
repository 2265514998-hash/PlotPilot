"""叙事健康仪表盘 API

聚合叙事债务、伏笔状态、张力曲线、道具生命周期、声纹漂移等维度数据，
为前端仪表盘提供单一端点。
"""
import logging
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from interfaces.api.dependencies import (
    get_database,
    get_foreshadowing_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["narrative-health"])


# ─── 响应模型 ───


class ForeshadowingHealth(BaseModel):
    total: int = 0
    planted: int = 0
    resolved: int = 0
    abandoned: int = 0
    overdue: int = 0
    upcoming_window: int = 0
    t0_count: int = 0
    deferred_count: int = 0


class DebtHealth(BaseModel):
    total: int = 0
    active: int = 0
    overdue: int = 0
    resolved: int = 0
    abandoned: int = 0
    by_type: Dict[str, int] = {}


class TensionPoint(BaseModel):
    chapter: int
    composite: float = 50.0
    plot: float = 50.0
    emotional: float = 50.0
    pacing: float = 50.0


class PropHealth(BaseModel):
    total: int = 0
    by_state: Dict[str, int] = {}
    stale_count: int = 0


class VoiceDriftHealth(BaseModel):
    latest_score: float = 0.0
    alert: bool = False
    trend: str = "unknown"


class NarrativeHealthResponse(BaseModel):
    foreshadowing: ForeshadowingHealth
    narrative_debts: DebtHealth
    tension_curve: List[TensionPoint]
    props: PropHealth
    voice_drift: VoiceDriftHealth
    health_score: int


# ─── 依赖 ───


def _get_debt_repo():
    from infrastructure.persistence.database.sqlite_narrative_debt_repository import (
        SqliteNarrativeDebtRepository,
    )
    return SqliteNarrativeDebtRepository(get_database())


def _get_prop_repo():
    from infrastructure.persistence.database.unified_prop_repository import (
        SqliteUnifiedPropRepository,
    )
    return SqliteUnifiedPropRepository(get_database())


# ─── 端点 ───


@router.get("/novels/{novel_id}/narrative-health", response_model=NarrativeHealthResponse)
async def get_narrative_health(
    novel_id: str,
    foreshadowing_repo=Depends(get_foreshadowing_repository),
):
    """获取小说叙事健康总览

    聚合以下维度：
    - 伏笔状态（planted/resolved/abandoned/overdue/T0/deferred）
    - 叙事债务（active/overdue/resolved/abandoned，按类型分组）
    - 张力曲线（每章三维张力：情节/情感/节奏）
    - 道具生命周期（按状态分组，stale 计数）
    - 声纹漂移（最新分数、告警状态、趋势）
    - 综合健康分（加权公式）
    """
    try:
        # ── 伏笔 ──
        foreshadow_health = ForeshadowingHealth()
        try:
            registry = foreshadowing_repo.get_by_novel_id(novel_id)
            if registry:
                all_f = registry.get_unresolved()
                foreshadow_health.total = len(registry.foreshadowings) if hasattr(registry, 'foreshadowings') else len(all_f)

                from domain.novel.value_objects.foreshadowing import ForeshadowingStatus
                planted = [f for f in all_f if f.status == ForeshadowingStatus.PLANTED]
                resolved = [f for f in (registry.foreshadowings if hasattr(registry, 'foreshadowings') else []) if f.status == ForeshadowingStatus.RESOLVED]
                abandoned = [f for f in (registry.foreshadowings if hasattr(registry, 'foreshadowings') else []) if f.status == ForeshadowingStatus.ABANDONED]

                foreshadow_health.planted = len(planted)
                foreshadow_health.resolved = len(resolved)
                foreshadow_health.abandoned = len(abandoned)

                # 用当前最大章节号估算 overdue
                db = get_database()
                max_ch = db.fetch_one("SELECT MAX(number) as m FROM chapters WHERE novel_id = ?", (novel_id,))
                current_ch = max_ch["m"] if max_ch and max_ch["m"] else 1

                overdue_f = registry.get_overdue_foreshadowings(current_ch)
                foreshadow_health.overdue = len(overdue_f)

                upcoming_f = registry.get_upcoming_foreshadowings(current_ch, window=3)
                foreshadow_health.upcoming_window = len(upcoming_f)

                t0 = registry.get_t0_eligible_foreshadowings(current_ch)
                foreshadow_health.t0_count = len(t0)
                deferred = registry.get_deferred_foreshadowings(current_ch)
                foreshadow_health.deferred_count = len(deferred)
        except Exception as e:
            logger.debug("伏笔健康数据获取失败: %s", e)

        # ── 叙事债务 ──
        debt_health = DebtHealth()
        try:
            debt_repo = _get_debt_repo()
            debts = debt_repo.get_by_novel(novel_id)
            debt_health.total = len(debts)
            type_counter: Counter = Counter()
            for d in debts:
                dt = d.debt_type.value if hasattr(d.debt_type, 'value') else str(d.debt_type)
                type_counter[dt] += 1
                if d.is_resolved:
                    debt_health.resolved += 1
                elif d.is_abandoned:
                    debt_health.abandoned += 1
                elif d.is_overdue:
                    debt_health.overdue += 1
                else:
                    debt_health.active += 1
            debt_health.by_type = dict(type_counter)
        except Exception as e:
            logger.debug("叙事债务数据获取失败: %s", e)

        # ── 张力曲线 ──
        tension_curve: List[TensionPoint] = []
        try:
            db = get_database()
            rows = db.fetch_all(
                "SELECT number, tension_score, plot_tension, emotional_tension, pacing_tension "
                "FROM chapters WHERE novel_id = ? ORDER BY number ASC",
                (novel_id,),
            )
            for row in rows:
                tension_curve.append(TensionPoint(
                    chapter=row["number"],
                    composite=row.get("tension_score", 50.0),
                    plot=row.get("plot_tension", 50.0),
                    emotional=row.get("emotional_tension", 50.0),
                    pacing=row.get("pacing_tension", 50.0),
                ))
        except Exception as e:
            logger.debug("张力曲线数据获取失败: %s", e)

        # ── 道具 ──
        prop_health = PropHealth()
        try:
            prop_repo = _get_prop_repo()
            props = prop_repo.get_all_by_novel(novel_id)
            prop_health.total = len(props)
            state_counter: Counter = Counter()
            for p in props:
                state = p.lifecycle_state.value if hasattr(p.lifecycle_state, 'value') else str(p.lifecycle_state)
                state_counter[state] += 1
            prop_health.by_state = dict(state_counter)

            # stale: INTRODUCED 状态超过 5 章无事件的道具
            stale_threshold = 5
            if rows:
                max_ch_num = rows[-1]["number"] if rows else 1
            else:
                max_ch_num = 1
            for p in props:
                state = p.lifecycle_state.value if hasattr(p.lifecycle_state, 'value') else str(p.lifecycle_state)
                if state == "INTRODUCED" and p.introduced_chapter:
                    if max_ch_num - p.introduced_chapter > stale_threshold:
                        prop_health.stale_count += 1
        except Exception as e:
            logger.debug("道具健康数据获取失败: %s", e)

        # ── 声纹漂移 ──
        voice_health = VoiceDriftHealth()
        try:
            db = get_database()
            drift_row = db.fetch_one(
                "SELECT score, drift_alert FROM chapter_style_scores "
                "WHERE novel_id = ? ORDER BY chapter_number DESC LIMIT 1",
                (novel_id,),
            )
            if drift_row:
                voice_health.latest_score = drift_row.get("score", 0.0)
                voice_health.alert = bool(drift_row.get("drift_alert", 0))
                voice_health.trend = "alert" if voice_health.alert else "stable"
        except Exception as e:
            logger.debug("声纹漂移数据获取失败: %s", e)

        # ── 综合健康分 ──
        score = _compute_health_score(
            foreshadow_health, debt_health, tension_curve, prop_health, voice_health
        )

        return NarrativeHealthResponse(
            foreshadowing=foreshadow_health,
            narrative_debts=debt_health,
            tension_curve=tension_curve,
            props=prop_health,
            voice_drift=voice_health,
            health_score=score,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("叙事健康数据聚合失败: %s", e)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


def _compute_health_score(
    foreshadow: ForeshadowingHealth,
    debts: DebtHealth,
    tension: List[TensionPoint],
    props: PropHealth,
    voice: VoiceDriftHealth,
) -> int:
    """综合健康分（0-100），加权公式"""
    total = 0.0
    weight_sum = 0.0

    # 伏笔健康（权重 30）：resolved / total 越高越好，overdue 惩罚
    if foreshadow.total > 0:
        closure_rate = foreshadow.resolved / max(foreshadow.total, 1)
        overdue_penalty = min(foreshadow.overdue * 0.1, 0.3)
        foreshadow_score = max(0, closure_rate - overdue_penalty)
        total += foreshadow_score * 30
    weight_sum += 30

    # 债务健康（权重 20）：overdue 越少越好
    if debts.total > 0:
        debt_score = 1.0 - min(debts.overdue / max(debts.total, 1), 1.0)
        total += debt_score * 20
    else:
        total += 20  # 无债务 = 满分
    weight_sum += 20

    # 张力曲线（权重 25）：方差越小（平稳）越好，但不能太平（死水）
    if len(tension) >= 3:
        scores = [t.composite for t in tension]
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        # 理想方差 ~200（有起伏但不极端），方差越大扣分越多
        tension_penalty = min(variance / 1000, 0.5)
        dead_water_penalty = 0.3 if avg < 20 else 0.0
        tension_score = max(0, 1.0 - tension_penalty - dead_water_penalty)
        total += tension_score * 25
    weight_sum += 25

    # 道具健康（权重 10）：stale 越少越好
    if props.total > 0:
        prop_score = 1.0 - min(props.stale_count / max(props.total, 1), 1.0)
        total += prop_score * 10
    else:
        total += 10
    weight_sum += 10

    # 声纹健康（权重 15）：drift alert 惩罚
    voice_score = 0.5 if voice.alert else 1.0
    total += voice_score * 15
    weight_sum += 15

    return min(100, max(0, int(total / weight_sum * 100))) if weight_sum > 0 else 50
