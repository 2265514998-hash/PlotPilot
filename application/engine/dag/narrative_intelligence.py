"""
PlotPilot 智能叙事分析节点集

新增 9 个 AI 驱动的 DAG 验证/生成节点：
- val_structure: 章节结构分类器
- val_character: 角色一致性自动检查
- val_plot_hole: 情节漏洞检测（基于 KG）
- val_emotion: 情感弧线追踪
- val_pacing: 语调节奏分析（纯启发式）
- val_theme: 主题漂移检测
- review_coach: 智能写作教练
- review_beta: AI β 读者
- gen_enrich: 细节增强器（五感描写）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from application.engine.dag.models import NodeCategory, NodeDefinition, NodeMeta
from application.engine.dag.registry import NodeRegistry

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 输出数据类型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class StructureResult:
    structural_role: str = ""
    act_phase: str = ""
    story_beat: str = ""
    beat_label_cn: str = ""
    confidence: float = 0.0
    rationale: str = ""
    progress_estimate: float = 0.0
    next_milestone: str = ""
    structure_tags: List[str] = field(default_factory=list)

@dataclass
class CharacterViolation:
    character_name: str = ""
    dimension: str = ""
    severity: str = "medium"
    expected_behavior: str = ""
    actual_behavior: str = ""
    location_hint: str = ""
    suggestion: str = ""

@dataclass
class PlotHole:
    id: str = ""
    type: str = ""
    severity: str = "medium"
    description: str = ""
    entities_involved: List[str] = field(default_factory=list)
    chapters_involved: List[int] = field(default_factory=list)
    suggested_fix: str = ""
    auto_fixable: bool = False

@dataclass
class EmotionState:
    character_name: str = ""
    primary_emotion: str = ""
    primary_intensity: int = 5
    secondary_emotions: List[str] = field(default_factory=list)
    trigger_event: str = ""

@dataclass
class CoachSuggestion:
    priority: int = 1
    tag: str = ""
    question: str = ""
    context_hint: str = ""
    actionable: bool = True

@dataclass
class BetaReaderFeedback:
    reader_persona: str = ""
    overall_sentiment: str = "neutral"
    engagement_level: int = 5
    concerns: List[Dict[str, Any]] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    readability_score: int = 70
    would_continue_reading: bool = True

@dataclass
class PacingMetrics:
    avg_sentence_length: float = 0.0
    dialogue_ratio: float = 0.0
    action_verb_density: float = 0.0
    paragraph_rhythm_score: float = 0.0
    pace_label: str = "balanced"

# ═══════════════════════════════════════════════════════════════════════════════
# 智能分析服务
# ═══════════════════════════════════════════════════════════════════════════════

class NarrativeIntelligenceService:
    """统一智能叙事分析服务——所有新增节点通过此服务调用"""

    @staticmethod
    async def classify_structure(
        narrative_events: List[str],
        chapter_number: int,
        total_chapters: int,
        novel_genre: str = "玄幻",
        llm_invoke=None,
    ) -> StructureResult:
        """章节结构分类"""
        if not llm_invoke:
            return StructureResult(structure_tags=["analysis_unavailable"])
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("structure-classification", {
                "narrative_events": json.dumps(narrative_events, ensure_ascii=False),
                "chapter_number": str(chapter_number),
                "total_chapters": str(total_chapters),
                "novel_genre": novel_genre,
            })
            raw = await llm_invoke(prompt)
            data = json.loads(raw) if isinstance(raw, str) else raw
            return StructureResult(**{k: v for k, v in data.items() if k in StructureResult.__dataclass_fields__})
        except Exception as e:
            logger.warning(f"[StructureClassifier] 分类失败: {e}")
            return StructureResult(structure_tags=["classification_failed"])

    @staticmethod
    async def check_character_consistency(
        chapter_content: str,
        character_states: str,
        chapter_characters: str,
        llm_invoke=None,
    ) -> Dict[str, Any]:
        """角色一致性检查"""
        if not llm_invoke:
            return {"overall_ooc_score": 0, "violations": []}
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("character-consistency-check", {
                "chapter_content": chapter_content[:8000],
                "character_states": character_states,
                "chapter_characters": chapter_characters,
            })
            raw = await llm_invoke(prompt)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f"[CharConsistency] 检查失败: {e}")
            return {"overall_ooc_score": 0, "violations": []}

    @staticmethod
    async def detect_plot_holes(
        knowledge_triples: str,
        causal_edges: str,
        timeline_entries: str,
        foreshadow_registry: str,
        chapter_content: str = "",
        llm_invoke=None,
    ) -> Dict[str, Any]:
        """情节漏洞检测"""
        if not llm_invoke:
            return {"has_holes": False, "plot_holes": [], "unresolved_foreshadows": []}
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("plot-hole-detection", {
                "knowledge_triples": knowledge_triples,
                "causal_edges": causal_edges,
                "timeline_entries": timeline_entries,
                "foreshadow_registry": foreshadow_registry,
                "chapter_content": chapter_content[:3000],
            })
            raw = await llm_invoke(prompt)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f"[PlotHole] 检测失败: {e}")
            return {"has_holes": False, "plot_holes": [], "unresolved_foreshadows": []}

    @staticmethod
    async def track_emotion_arc(
        narrative_events: str,
        character_names: List[str],
        previous_arc: str = "",
        chapter_number: int = 0,
        llm_invoke=None,
    ) -> Dict[str, Any]:
        """情感弧线追踪"""
        if not llm_invoke:
            return {"chapter_emotions": {}, "chapter_emotional_tone": "unknown"}
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("emotion-arc", {
                "narrative_events": narrative_events,
                "character_names": json.dumps(character_names, ensure_ascii=False),
                "previous_arc": previous_arc,
                "chapter_number": str(chapter_number),
            })
            raw = await llm_invoke(prompt)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f"[EmotionArc] 追踪失败: {e}")
            return {"chapter_emotions": {}, "chapter_emotional_tone": "unknown"}

    @staticmethod
    def analyze_pacing(chapter_content: str) -> PacingMetrics:
        """语调节奏分析（纯启发式，不消耗 token）"""
        import re
        if not chapter_content:
            return PacingMetrics()

        sentences = re.split(r'[。！？；\n!?;]', chapter_content)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

        dialogue_lines = len(re.findall(r'[「「""『』][^」」""』』]*[」」""』』]', chapter_content))
        total_lines = max(len(sentences), 1)
        dialogue_ratio = dialogue_lines / total_lines

        action_verbs = len(re.findall(r'(打|跑|跳|飞|斩|冲|跃|踢|挥|击|撞|摔|抓|推|拉|扯|劈|刺|砍)', chapter_content))
        total_words = max(len(chapter_content), 1)
        action_density = action_verbs / total_words * 100

        pace_label = "balanced"
        if avg_len < 20 and action_density > 0.5:
            pace_label = "fast"
        elif avg_len > 60 and dialogue_ratio < 0.15:
            pace_label = "slow"
        elif dialogue_ratio > 0.4:
            pace_label = "dialogue_heavy"

        return PacingMetrics(
            avg_sentence_length=round(avg_len, 1),
            dialogue_ratio=round(dialogue_ratio, 2),
            action_verb_density=round(action_density, 2),
            paragraph_rhythm_score=round(min(1.0, dialogue_ratio * 0.5 + action_density * 0.5), 2),
            pace_label=pace_label,
        )

    @staticmethod
    async def coach_suggest(
        chapter_content: str,
        tension_scores: str = "",
        drift_score: str = "",
        beat_focus: str = "",
        character_states: str = "",
        chapter_number: int = 0,
        llm_invoke=None,
    ) -> Dict[str, Any]:
        """智能写作教练"""
        if not llm_invoke:
            return {"encouragement": "", "suggestions": []}
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("writing-coach", {
                "chapter_content": chapter_content[:6000],
                "tension_scores": tension_scores,
                "drift_score": drift_score,
                "beat_focus": beat_focus,
                "character_states": character_states,
                "chapter_number": str(chapter_number),
            })
            raw = await llm_invoke(prompt)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f"[Coach] 生成建议失败: {e}")
            return {"encouragement": "", "suggestions": []}

    @staticmethod
    async def beta_read(
        chapter_content: str,
        reader_persona: str = "casual",
        chapter_number: int = 0,
        previous_summary: str = "",
        llm_invoke=None,
    ) -> BetaReaderFeedback:
        """AI β 读者"""
        if not llm_invoke:
            return BetaReaderFeedback()
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("beta-reader", {
                "chapter_content": chapter_content[:8000],
                "reader_persona": reader_persona,
                "chapter_number": str(chapter_number),
                "previous_summary": previous_summary[:2000],
            })
            raw = await llm_invoke(prompt)
            data = json.loads(raw) if isinstance(raw, str) else raw
            return BetaReaderFeedback(**{k: v for k, v in data.items() if k in BetaReaderFeedback.__dataclass_fields__})
        except Exception as e:
            logger.warning(f"[BetaReader] 分析失败: {e}")
            return BetaReaderFeedback()

    @staticmethod
    async def enrich_describe(
        selected_text: str,
        sense_focus: str = "visual,auditory",
        intensity_level: str = "moderate",
        llm_invoke=None,
    ) -> Dict[str, Any]:
        """细节增强（五感描写）"""
        if not llm_invoke:
            return {"enriched_text": selected_text, "added_senses": []}
        try:
            from infrastructure.ai.prompt_utils import render_prompt
            prompt = render_prompt("enrich-describe", {
                "selected_text": selected_text,
                "sense_focus": sense_focus,
                "intensity_level": intensity_level,
            })
            raw = await llm_invoke(prompt)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f"[Enrich] 增强失败: {e}")
            return {"enriched_text": selected_text, "added_senses": []}

    @staticmethod
    async def detect_theme_drift(
        theme_keywords: List[str],
        chapter_content: str,
        threshold: float = 0.3,
        llm_invoke=None,
    ) -> Dict[str, Any]:
        """主题漂移检测"""
        result = {"drift_score": 0.0, "missing_themes": [], "weakened_themes": [], "suggestion": ""}
        if not chapter_content or not theme_keywords:
            return result

        # 启发式层：关键词频率检测
        content_lower = chapter_content.lower()
        for kw in theme_keywords:
            count = content_lower.count(kw.lower())
            if count == 0:
                result["missing_themes"].append(kw)
            elif count < 2:
                result["weakened_themes"].append(kw)

        total_themes = len(theme_keywords)
        if total_themes > 0:
            missing_ratio = len(result["missing_themes"]) / total_themes
            result["drift_score"] = round(missing_ratio, 2)

        if result["drift_score"] > 0.5:
            result["suggestion"] = f"主题漂移严重：{', '.join(result['missing_themes'][:3])} 在本章中未出现"

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# DAG 节点注册
# ═══════════════════════════════════════════════════════════════════════════════

INTELLIGENCE_NODES: List[NodeMeta] = [
    NodeMeta(
        node_type="val_structure",
        category=NodeCategory.VALIDATION,
        display_name="📊 结构分类",
        description="分析章节在故事结构中的位置（三幕/英雄之旅/七点结构）",
        inputs={"narrative_events": "list[str]", "chapter_number": "int", "total_chapters": "int", "novel_genre": "str"},
        outputs={"structural_role": "str", "act_phase": "str", "story_beat": "str", "confidence": "float"},
        priority=30,
    ),
    NodeMeta(
        node_type="val_character",
        category=NodeCategory.VALIDATION,
        display_name="👤 角色一致性",
        description="自动检测角色 OOC、能力矛盾、知识矛盾、关系矛盾",
        inputs={"chapter_content": "str", "character_states": "str", "chapter_characters": "str"},
        outputs={"ooc_score": "float", "violations": "list"},
        priority=25,
    ),
    NodeMeta(
        node_type="val_plot_hole",
        category=NodeCategory.VALIDATION,
        display_name="🔍 情节漏洞",
        description="基于知识图谱检测跨章节矛盾、时间线冲突、因果链断裂",
        inputs={"knowledge_triples": "str", "causal_edges": "str", "timeline_entries": "str", "foreshadow_registry": "str"},
        outputs={"has_holes": "bool", "plot_holes": "list"},
        priority=20,
    ),
    NodeMeta(
        node_type="val_emotion",
        category=NodeCategory.VALIDATION,
        display_name="💭 情感弧线",
        description="追踪每个主要角色的情感状态轨迹，检测情感平坦区段",
        inputs={"narrative_events": "str", "character_names": "list[str]", "previous_arc": "str", "chapter_number": "int"},
        outputs={"character_emotions": "dict", "flat_segments": "list"},
        priority=22,
    ),
    NodeMeta(
        node_type="val_pacing",
        category=NodeCategory.VALIDATION,
        display_name="⏱️ 节奏分析",
        description="句长分布、对话比例、动作密度——纯启发式，零 token 消耗",
        inputs={"chapter_content": "str"},
        outputs={"avg_sentence_length": "float", "dialogue_ratio": "float", "pace_label": "str"},
        priority=28,
    ),
    NodeMeta(
        node_type="val_theme",
        category=NodeCategory.VALIDATION,
        display_name="🎯 主题漂移",
        description="追踪关键主题词跨章节出现频率，检测主题遗忘和漂移",
        inputs={"theme_keywords": "list[str]", "chapter_content": "str", "threshold": "float"},
        outputs={"drift_score": "float", "missing_themes": "list[str]"},
        priority=18,
    ),
    NodeMeta(
        node_type="review_coach",
        category=NodeCategory.VALIDATION,
        display_name="🧑‍🏫 写作教练",
        description="以提问式引导给出 2-3 条可执行建议，不代替写作",
        inputs={"chapter_content": "str", "tension_scores": "str", "drift_score": "str", "character_states": "str"},
        outputs={"suggestions": "list", "encouragement": "str"},
        priority=35,
    ),
    NodeMeta(
        node_type="review_beta",
        category=NodeCategory.VALIDATION,
        display_name="📖 β 读者",
        description="模拟硬核/休闲/挑剔三种读者视角，提供真实阅读体验反馈",
        inputs={"chapter_content": "str", "reader_persona": "str", "previous_summary": "str"},
        outputs={"concerns": "list", "highlights": "list", "readability_score": "int"},
        priority=32,
    ),
    NodeMeta(
        node_type="gen_enrich",
        category=NodeCategory.EXECUTION,
        display_name="✨ 细节增强",
        description="为指定段落注入五感细节（Sudowrite Describe 等价功能）",
        inputs={"selected_text": "str", "sense_focus": "str", "intensity_level": "str"},
        outputs={"enriched_text": "str", "added_senses": "list"},
        priority=40,
    ),
]


def register_intelligence_nodes():
    """将智能节点注册到 DAG 节点注册表"""
    for meta in INTELLIGENCE_NODES:
        try:
            NodeRegistry.register(meta)
        except Exception as e:
            logger.warning(f"[IntelligenceNodes] 注册 {meta.node_type} 失败: {e}")
    logger.info(f"[IntelligenceNodes] 已注册 {len(INTELLIGENCE_NODES)} 个智能分析节点")
    return INTELLIGENCE_NODES
