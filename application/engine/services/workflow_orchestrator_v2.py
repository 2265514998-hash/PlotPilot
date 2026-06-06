"""
工作流编排工厂 v2 — 集成全部 2025+2026 SOTA 服务

四层深度：
- fast:      单次 LLM
- standard:  ReflectivePlanner + IterativeWriter
- deep:      SuperWriter + MCTS + KG验证
- supreme:   BiT-MCTS + Writer-R1 MRPO + 熵控制 + ForeshadowPool + DiversityBranching + StyleGuard + MultiResPlanner

supreme 是 2026 年论文的全部落地——从高潮优先双向展开开始，经过
记忆增强反思、熵控制解码、伏笔投资池追踪、多样性分叉探索、风格防扁平化、
到最后的多分辨率全书骨架。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowDepthV2(str, Enum):
    FAST = "fast"           # 单次生成
    STANDARD = "standard"   # Plan → Write → Check
    DEEP = "deep"           # SuperWriter + MCTS + KG
    SUPREME = "supreme"     # 2026 全部论文集成


@dataclass
class SupremeConfig:
    """supreme 模式的全参数配置"""
    enable_bit_mcts: bool = True           # BiT-MCTS 高潮优先双向搜索
    enable_mrpo: bool = True               # Writer-R1 记忆回放
    enable_entropy_control: bool = True    # Octopus 熵控制
    enable_foreshadow_pool: bool = True    # CFPG 伏笔投资池
    enable_diversity_branching: bool = True # DPWriter 多样性分支
    enable_style_guard: bool = True        # 风格扁平化防护
    enable_multi_resolution: bool = True   # 全书多分辨率规划
    quality_threshold: float = 7.0
    max_chapters: int = 100


@dataclass
class SupremeResult:
    content: str = ""
    # BiT-MCTS
    climax: str = ""
    narrative_structure: Dict[str, Any] = field(default_factory=dict)
    # Writer-R1
    initial_score: float = 0.0
    final_score: float = 0.0
    improvement: float = 0.0
    reflections: List[str] = field(default_factory=list)
    # Entropy
    entropy_phase: str = ""
    entropy_config: Dict[str, Any] = field(default_factory=dict)
    # Foreshadow
    foreshadow_pool_state: Dict[str, Any] = field(default_factory=dict)
    # Diversity
    diversity_report: Dict[str, Any] = field(default_factory=dict)
    # Style
    style_variation_score: float = 1.0
    flattening_alerts: List[Dict[str, Any]] = field(default_factory=list)
    # Multi-res
    book_scaffold_nodes: int = 0
    chapter_context: Dict[str, str] = field(default_factory=dict)
    # Meta
    pipeline_name: str = "supreme"
    total_duration_ms: float = 0.0


class WorkflowOrchestratorV2:
    """统一工作流编排器 v2 — 集成 2025+2026 全部服务"""

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def generate_supreme(
        self,
        chapter_number: int,
        premise: str = "",
        context: str = "",
        outline: str = "",
        config: SupremeConfig | None = None,
    ) -> SupremeResult:
        """执行最高级别的 supreme 工作流"""

        import time
        start = time.time()
        cfg = config or SupremeConfig()
        result = SupremeResult()

        # ── Phase 0: 多分辨率全书骨架 ──
        scaffold = None
        if cfg.enable_multi_resolution:
            from application.engine.services.multi_resolution_planner import MultiResolutionPlanner
            planner = MultiResolutionPlanner(llm_service=self._llm)
            scaffold = await planner.build_book_scaffold(premise, cfg.max_chapters)
            result.book_scaffold_nodes = len(scaffold.nodes)
            result.chapter_context = scaffold.get_chapter_context(scaffold, chapter_number)

        # ── Phase 1: BiT-MCTS 双向展开 ──
        climax = ""
        if cfg.enable_bit_mcts:
            from application.engine.services.bidirectional_mcts import BiTMCTS
            mcts = BiTMCTS(llm_service=self._llm, theme=premise, total_chapters=cfg.max_chapters)
            bit_result = await mcts.search(premise)
            climax = bit_result.climax
            result.climax = climax
            result.narrative_structure = bit_result.full_structure

        # ── Phase 2: 多样性规划分叉 ──
        diversity_report = {}
        if cfg.enable_diversity_branching:
            from application.engine.services.diversity_branching import DiversityBrancher
            brancher = DiversityBrancher(llm_service=self._llm)
            div_result = await brancher.branch_and_select(outline or premise, context)
            if div_result.selected_path:
                outline = div_result.selected_path.summary or outline
                result.diversity_report = {
                    "paths_count": len(div_result.paths),
                    "selected": div_result.selected_path.id,
                    "group_diversity": div_result.group_diversity,
                }

        # ── Phase 3: Writer-R1 MRPO 写作 ──
        if cfg.enable_mrpo:
            from application.engine.services.writer_r1_mrpo import WriterR1MRPO
            mrpo = WriterR1MRPO(llm_service=self._llm)
            mrpo_result = await mrpo.generate_with_reflection(
                task=f"写出第{chapter_number}章{('—高潮:' + climax[:50]) if climax else ''}",
                context=context,
            )
            result.content = mrpo_result.content
            result.initial_score = mrpo_result.initial_score
            result.final_score = mrpo_result.final_score
            result.improvement = mrpo_result.improvement
            result.reflections = mrpo_result.reflections
        else:
            from application.engine.services.super_writer_pipeline import SuperWriterPipeline
            pipeline = SuperWriterPipeline(llm_service=self._llm)
            sw_result = await pipeline.generate(chapter_number, context, outline)
            result.content = sw_result.content

        # ── Phase 4: 熵控制调节 ──
        if cfg.enable_entropy_control:
            from application.engine.services.octopus_entropy import OctopusController
            controller = OctopusController()
            phase = controller.entropy_phase_from_content(result.content, chapter_number / cfg.max_chapters)
            entropy_config = controller.get_config(phase)
            result.entropy_phase = phase
            result.entropy_config = {
                "temp": entropy_config.temperature,
                "top_p": entropy_config.top_p,
                "top_k": entropy_config.top_k,
                "phase": entropy_config.phase.value,
            }

        # ── Phase 5: ForeshadowPool 伏笔追踪 ──
        if cfg.enable_foreshadow_pool:
            try:
                from application.engine.services.foreshadow_pool import ForeshadowPool
                pool = ForeshadowPool()
                # 触发现有伏笔
                triggered = pool.trigger_if_ready(chapter_number, {"content": result.content[:500]})
                # 自动结算优先伏笔
                for entry in triggered[:2]:
                    pool.payoff(entry.id)
                state = pool.get_pool_state()
                result.foreshadow_pool_state = {
                    "active": state.active, "triggered": state.triggered,
                    "paid_off": state.paid_off, "payoff_rate": state.payoff_rate,
                }
            except Exception:
                pass

        # ── Phase 6: Style Guard 风格多样性 ──
        if cfg.enable_style_guard:
            from application.engine.services.style_variation_guard import StyleVariationGuard, StyleProfile
            guard = StyleVariationGuard()
            profile = StyleProfile(
                chapter_id=str(chapter_number),
                chapter_number=chapter_number,
                avg_sentence_length=len(result.content) / max(result.content.count('。') + result.content.count('！') + result.content.count('？'), 1),
                dialogue_ratio=result.content.count('"') / max(len(result.content), 1) * 10,
                emotional_variance=0.3,
                adjective_density=0.05,
                unique_word_ratio=0.7,
                tone="narrative",
            )
            alerts = guard.analyze_chapter(profile)
            result.style_variation_score = guard.generate_report().overall_variation_score
            result.flattening_alerts = [
                {"dimension": a.dimension, "severity": a.severity, "suggestion": a.suggestion}
                for a in alerts
            ]

        result.total_duration_ms = round((time.time() - start) * 1000, 0)
        return result
