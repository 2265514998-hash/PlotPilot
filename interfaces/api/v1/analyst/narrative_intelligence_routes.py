"""叙事智能分析 API 路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/ai", tags=["Narrative Intelligence"])


class CoachRequest(BaseModel):
    chapter_content: str = ""
    chapter_number: int = 0
    tension_scores: str = ""
    drift_score: str = ""
    beat_focus: str = ""


class EnrichRequest(BaseModel):
    selected_text: str
    sense_focus: str = "visual,auditory"
    intensity_level: str = "moderate"


class BetaReadRequest(BaseModel):
    chapter_content: str
    reader_persona: str = "casual"
    chapter_number: int = 0
    previous_summary: str = ""


class AnalysisRequest(BaseModel):
    chapter_content: str = ""
    chapter_number: int = 0
    total_chapters: int = 100
    narrative_events: List[str] = Field(default_factory=list)
    knowledge_triples: str = ""
    character_states: str = ""
    theme_keywords: List[str] = Field(default_factory=list)


@router.post("/coach")
async def writing_coach(req: CoachRequest):
    """智能写作教练"""
    try:
        from infrastructure.ai.provider_factory import LLMProviderFactory
        llm = LLMProviderFactory.create_default()
    except Exception:
        llm = None

    from application.engine.dag.narrative_intelligence import NarrativeIntelligenceService
    result = await NarrativeIntelligenceService.coach_suggest(
        chapter_content=req.chapter_content,
        chapter_number=req.chapter_number,
        tension_scores=req.tension_scores,
        drift_score=req.drift_score,
        beat_focus=req.beat_focus,
        llm_invoke=llm.invoke_json if llm else None,
    )
    return result


@router.post("/enrich")
async def enrich_describe(req: EnrichRequest):
    """细节增强（五感描写）"""
    try:
        from infrastructure.ai.provider_factory import LLMProviderFactory
        llm = LLMProviderFactory.create_default()
    except Exception:
        llm = None

    from application.engine.dag.narrative_intelligence import NarrativeIntelligenceService
    result = await NarrativeIntelligenceService.enrich_describe(
        selected_text=req.selected_text,
        sense_focus=req.sense_focus,
        intensity_level=req.intensity_level,
        llm_invoke=llm.invoke_json if llm else None,
    )
    return result


@router.post("/beta-read")
async def beta_read(req: BetaReadRequest):
    """AI β 读者"""
    try:
        from infrastructure.ai.provider_factory import LLMProviderFactory
        llm = LLMProviderFactory.create_default()
    except Exception:
        llm = None

    from application.engine.dag.narrative_intelligence import NarrativeIntelligenceService
    feedback = await NarrativeIntelligenceService.beta_read(
        chapter_content=req.chapter_content,
        reader_persona=req.reader_persona,
        chapter_number=req.chapter_number,
        previous_summary=req.previous_summary,
        llm_invoke=llm.invoke_json if llm else None,
    )
    return {
        "reader_persona": feedback.reader_persona,
        "overall_sentiment": feedback.overall_sentiment,
        "engagement_level": feedback.engagement_level,
        "concerns": feedback.concerns,
        "highlights": feedback.highlights,
        "readability_score": feedback.readability_score,
        "would_continue_reading": feedback.would_continue_reading,
    }


@router.post("/analyze/{novel_id}")
async def full_narrative_analysis(novel_id: str, req: AnalysisRequest):
    """全方位叙事智能分析"""
    try:
        from infrastructure.ai.provider_factory import LLMProviderFactory
        llm = LLMProviderFactory.create_default()
    except Exception:
        llm = None

    invoke = llm.invoke_json if llm else None
    from application.engine.dag.narrative_intelligence import NarrativeIntelligenceService as NIS

    results: Dict[str, Any] = {}

    # 1. 结构分类
    if req.narrative_events:
        results["structure"] = {
            "structural_role": "",
            "act_phase": "",
            "story_beat": "",
            "beat_label_cn": "",
            "confidence": 0.0,
            "rationale": "",
            "progress_estimate": 0.0,
            "next_milestone": "",
            "structure_tags": [],
        }
        try:
            sr = await NIS.classify_structure(
                narrative_events=req.narrative_events,
                chapter_number=req.chapter_number,
                total_chapters=req.total_chapters,
                novel_genre="玄幻",
                llm_invoke=invoke,
            )
            results["structure"] = {
                "structural_role": sr.structural_role,
                "act_phase": sr.act_phase,
                "story_beat": sr.story_beat,
                "beat_label_cn": sr.beat_label_cn,
                "confidence": sr.confidence,
                "rationale": sr.rationale,
                "progress_estimate": sr.progress_estimate,
                "next_milestone": sr.next_milestone,
                "structure_tags": sr.structure_tags,
            }
        except Exception as e:
            results["structure"] = {"error": str(e)}

    # 2. 节奏分析（纯启发式，永远可用）
    pacing = NIS.analyze_pacing(req.chapter_content)
    results["pacing"] = {
        "avg_sentence_length": pacing.avg_sentence_length,
        "dialogue_ratio": pacing.dialogue_ratio,
        "action_verb_density": pacing.action_verb_density,
        "paragraph_rhythm_score": pacing.paragraph_rhythm_score,
        "pace_label": pacing.pace_label,
    }

    # 3. 角色一致性（需要 LLM + 角色状态）
    if req.character_states and req.chapter_content:
        try:
            char_result = await NIS.check_character_consistency(
                chapter_content=req.chapter_content,
                character_states=req.character_states,
                chapter_characters="",
                llm_invoke=invoke,
            )
            results["ooc_score"] = char_result.get("overall_ooc_score", 0)
            results["violations"] = char_result.get("violations", [])
        except Exception:
            results["ooc_score"] = 0
            results["violations"] = []

    # 4. 情节漏洞
    if req.knowledge_triples:
        try:
            holes = await NIS.detect_plot_holes(
                knowledge_triples=req.knowledge_triples,
                causal_edges="",
                timeline_entries="",
                foreshadow_registry="",
                chapter_content=req.chapter_content,
                llm_invoke=invoke,
            )
            results["plot_holes"] = holes.get("plot_holes", [])
        except Exception:
            results["plot_holes"] = []

    # 5. 主题漂移
    if req.theme_keywords and req.chapter_content:
        results["theme_drift"] = await NIS.detect_theme_drift(
            theme_keywords=req.theme_keywords,
            chapter_content=req.chapter_content,
            llm_invoke=invoke,
        )

    return results
