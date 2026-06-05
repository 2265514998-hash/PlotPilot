"""场景生成 API 路由"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from application.core.services.scene_generation_service import SceneGenerationService
from application.blueprint.services.beat_sheet_service import BeatSheetService
from application.world.services.bible_service import BibleService
from application.core.services.chapter_service import ChapterService
from domain.novel.value_objects.scene import Scene
from interfaces.api.dependencies import (
    get_scene_generation_service,
    get_beat_sheet_service,
    get_bible_service,
    get_chapter_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scenes", tags=["scenes"])


class GenerateSceneRequest(BaseModel):
    """生成场景请求"""
    novel_id: str = Field(..., description="小说 ID")
    chapter_id: str = Field(..., description="章节 ID")
    chapter_number: int = Field(..., ge=1, description="章节号")
    scene_index: int = Field(..., ge=0, description="场景索引（从 0 开始）")


class GenerateSceneResponse(BaseModel):
    """生成场景响应"""
    scene_title: str
    scene_index: int
    content: str
    word_count: int


def _build_bible_context(bible_service: BibleService, novel_id: str) -> Dict:
    """从 Bible 服务构建上下文字典（复用 ContinuousPlanningService 模式）"""
    bible = bible_service.get_bible_by_novel(novel_id)
    if not bible:
        return {}
    return {
        "characters": [
            {"id": c.id, "name": c.name, "description": c.description,
             "reveal_chapter": c.reveal_chapter}
            for c in bible.characters
        ],
        "world_settings": [
            {"id": w.id, "name": w.name, "description": w.description}
            for w in bible.world_settings
        ],
        "locations": [
            {"id": l.id, "name": l.name, "description": l.description}
            for l in bible.locations
        ],
        "timeline_notes": [
            {"id": t.id, "event": t.event, "description": t.description}
            for t in bible.timeline_notes
        ],
    }


@router.post("/generate", response_model=GenerateSceneResponse)
async def generate_scene(
    request: GenerateSceneRequest,
    scene_gen_service: SceneGenerationService = Depends(get_scene_generation_service),
    beat_sheet_service: BeatSheetService = Depends(get_beat_sheet_service),
    bible_service: BibleService = Depends(get_bible_service),
    chapter_service: ChapterService = Depends(get_chapter_service),
):
    """为指定场景生成正文

    根据节拍表中的场景信息，结合 Bible 上下文、前置场景和向量检索生成正文。
    """
    try:
        # 1. 获取节拍表
        beat_sheet = await beat_sheet_service.get_beat_sheet(request.chapter_id)
        if not beat_sheet:
            raise HTTPException(
                status_code=404,
                detail=f"Beat sheet not found for chapter {request.chapter_id}"
            )

        # 2. 获取目标场景
        if request.scene_index >= len(beat_sheet.scenes):
            raise HTTPException(
                status_code=400,
                detail=f"Scene index {request.scene_index} out of range (total: {len(beat_sheet.scenes)})"
            )

        target_scene = beat_sheet.scenes[request.scene_index]

        # 3. 获取前置场景正文（同章节中 scene_index 之前的场景）
        previous_scenes: List[str] = []
        # 从节拍表中取已有的场景大纲作为前置上下文
        for i in range(request.scene_index):
            prev = beat_sheet.scenes[i]
            if hasattr(prev, 'generated_content') and prev.generated_content:
                previous_scenes.append(prev.generated_content)

        # 4. 获取 Bible 上下文
        bible_context = _build_bible_context(bible_service, request.novel_id)

        # 5. 生成场景正文
        content = await scene_gen_service.generate_scene(
            scene=target_scene,
            chapter_number=request.chapter_number,
            previous_scenes=previous_scenes,
            bible_context=bible_context,
            novel_id=request.novel_id,
        )

        return GenerateSceneResponse(
            scene_title=target_scene.title,
            scene_index=request.scene_index,
            content=content,
            word_count=len(content)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate scene: %s", e)
        raise HTTPException(status_code=500, detail="场景生成失败，请稍后重试")
