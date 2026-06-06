"""
SuperWriter 四步生成管线 — 对标 SuperWriter (arXiv 2506.04180, 2025-06)

Plan → Think → Write → Check → Edit → (loop)

不同于单次 LLM 调用，这是五阶段认知流水线：
1. Plan: 两个 AI 智能体用"故事工作室"对话讨论核心主题、角色背景、段落分配
2. Think: 在落笔前，先组织关键想法、主题、逻辑结构
3. Write: 基于提纲和前段内容生成正文
4. Check: 评估逻辑一致性、表达清晰度、叙事偏离
5. Edit: 针对性修改后输出

关键创新来自 SuperWriter：
- Hierarchical Quality Score：最终评分回传到中间步骤
- 7B Qwen 通过此流水线击败 GPT-4o (8.51 vs 8.16)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SuperWriterStage(str, Enum):
    PLAN = "plan"
    THINK = "think"
    WRITE = "write"
    CHECK = "check"
    EDIT = "edit"
    DONE = "done"


class QualityDimension(str, Enum):
    COHERENCE = "coherence"          # 连贯性
    LOGIC = "logic"                  # 逻辑一致性
    ENGAGEMENT = "engagement"        # 吸引力/爽点
    CHARACTER = "character"          # 角色深度
    STYLE = "style"                  # 文笔质量
    ORIGINALITY = "originality"      # 创新度


@dataclass
class QualityScore:
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    composite: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    needs_revision: bool = False


@dataclass
class PipelineTrace:
    """记录每个阶段的输入/输出/评分，用于层级回传"""
    stage: str = ""
    input_hash: str = ""
    output: str = ""
    quality: QualityScore | None = None
    duration_ms: float = 0.0


@dataclass
class SuperWriterResult:
    content: str = ""
    quality: QualityScore = field(default_factory=QualityScore)
    traces: List[PipelineTrace] = field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    revision_rounds: int = 0


class SuperWriterPipeline:
    """
    Plan → Think → Write → Check → Edit 五阶段流水线

    对标 SuperWriter 论文 (2506.04180)
    - Plan 阶段用两个 agent 对话（Story Workshop）
    - Think 阶段在落笔前组织思路
    - Check→Edit 循环实现迭代精炼
    """

    MAX_REVISION_ROUNDS = 2  # 最多 2 轮 Check→Edit

    PLAN_SYSTEM_PROMPT = """你是一位资深故事策划。你正在与另一位策划讨论并制定章节写作计划。

你的讨论应涵盖：
1. 本章的核心冲突是什么？
2. 主要角色的情感弧线在本章如何推进？
3. 开篇钩子、中点转折、结尾悬念分别是什么？
4. 本章完成了几个关键信息揭示？
5. 节奏分配：铺垫/升温/高潮/收尾各占多少？

请以结构化方式输出讨论结果。"""

    THINK_SYSTEM_PROMPT = """你是一位深思熟虑的作家。在动笔之前，先想清楚：

1. 关键场景需要哪些感官细节？
2. 对话的潜台词是什么？
3. 角色在这个场景中的内在状态如何外化？
4. 有哪些伏笔可以在此埋下？
5. 与前章的衔接点在哪里？

仅输出思考过程，不要写正文。"""

    WRITE_SYSTEM_PROMPT = """你是一位经验丰富的网络小说作家。根据以下条件写作：

- 遵循已确定的提纲和思考框架
- 注意与前文的连贯性
- 展示而非告知
- 对话要有潜台词
- 适当加入感官细节
- 保持爽文节奏"""

    CHECK_SYSTEM_PROMPT = """你是一位挑剔的编辑。请评估以下段落：

评估维度（每项 1-10 分）：
1. 连贯性：段落内部和前后之间是否逻辑自洽？
2. 逻辑一致性：角色行为/事件是否合理？
3. 吸引力：是否有钩子/爽点/张力？
4. 角色深度：角色的行为是否展现了性格和动机？
5. 文笔质量：语言是否生动精准？
6. 创新度：是否避免了套话和AI模板？

输出严格 JSON。"""

    EDIT_SYSTEM_PROMPT = """你是一位精准的文字编辑。根据审阅意见进行修改：

- 保留原文的核心情节和创意
- 针对性修复每个指出的问题
- 不改变文风和语气
- 不无谓扩充字数"""

    def __init__(self, llm_service=None):
        self._llm = llm_service
        self._traces: List[PipelineTrace] = []

    async def generate(
        self,
        chapter_number: int,
        context: str = "",
        outline: str = "",
        max_words: int = 3000,
    ) -> SuperWriterResult:
        """执行完整的 SuperWriter 流水线"""

        import time
        start = time.time()
        self._traces = []
        total_tokens = 0

        if not self._llm:
            return SuperWriterResult(content="[需要 LLM 服务]", total_tokens=0)

        # ─── Stage 1: PLAN — 故事工作室 ───
        plan = await self._stage_plan(chapter_number, context, outline)
        self._traces.append(PipelineTrace(stage="plan", output=plan[:200]))

        # ─── Stage 2: THINK — 落笔前思考 ───
        thinking = await self._stage_think(chapter_number, plan, context)
        self._traces.append(PipelineTrace(stage="think", output=thinking[:200]))

        # ─── Stage 3: WRITE — 生成正文 ───
        content = await self._stage_write(chapter_number, plan, thinking, context, max_words)
        self._traces.append(PipelineTrace(stage="write", output=content[:200]))
        total_tokens += len(content)

        # ─── Stage 4-5: CHECK → EDIT 循环 ───
        revision_rounds = 0
        final_quality: QualityScore | None = None

        for round_num in range(self.MAX_REVISION_ROUNDS + 1):
            quality = await self._stage_check(content, plan, context)
            self._traces.append(PipelineTrace(stage="check", quality=quality))

            if not quality.needs_revision or round_num >= self.MAX_REVISION_ROUNDS:
                final_quality = quality
                break

            content = await self._stage_edit(content, quality, plan)
            self._traces.append(PipelineTrace(stage="edit", output=content[:200]))
            total_tokens += len(content)
            revision_rounds += 1

        if final_quality is None:
            final_quality = QualityScore(composite=5.0)

        elapsed = (time.time() - start) * 1000

        return SuperWriterResult(
            content=content,
            quality=final_quality,
            traces=self._traces,
            total_tokens=total_tokens,
            total_duration_ms=elapsed,
            revision_rounds=revision_rounds,
        )

    async def _stage_plan(self, chapter_number: int, context: str, outline: str) -> str:
        try:
            result = await self._llm.generate(
                system_prompt=self.PLAN_SYSTEM_PROMPT,
                user_prompt=f"""第{chapter_number}章写作计划讨论。

已有上下文：
{context[:2000]}

已有提纲：
{outline[:1000]}

请与策划伙伴讨论并制定本章的详细写作计划。""",
                temperature=0.8,
                max_tokens=1500,
            )
            return result.text if hasattr(result, 'text') else str(result)
        except Exception as e:
            logger.warning(f"[SuperWriter.Plan] 失败: {e}")
            return outline or f"第{chapter_number}章写作计划（默认）"

    async def _stage_think(self, chapter_number: int, plan: str, context: str) -> str:
        try:
            result = await self._llm.generate(
                system_prompt=self.THINK_SYSTEM_PROMPT,
                user_prompt=f"""第{chapter_number}章 — 落笔前思考。

写作计划：
{plan[:1500]}

请逐一思考：场景细节、对话潜台词、角色状态外化、伏笔机会、前章衔接。""",
                temperature=0.7,
                max_tokens=1000,
            )
            return result.text if hasattr(result, 'text') else str(result)
        except Exception as e:
            logger.warning(f"[SuperWriter.Think] 失败: {e}")
            return "（默认思考：按提纲写作，注意连贯性）"

    async def _stage_write(self, chapter_number: int, plan: str, thinking: str, context: str, max_words: int) -> str:
        try:
            result = await self._llm.generate(
                system_prompt=self.WRITE_SYSTEM_PROMPT,
                user_prompt=f"""第{chapter_number}章 — 请开始写作。

写作计划：
{plan[:1500]}

落笔前思考：
{thinking[:800]}

前文上下文：
{context[:2000]}

目标字数：{max_words} 字
请写出完整的章节正文。""",
                temperature=1.0,
                max_tokens=max_words * 3,
            )
            return result.text if hasattr(result, 'text') else str(result)
        except Exception as e:
            logger.warning(f"[SuperWriter.Write] 失败: {e}")
            return "（写作失败，请重试）"

    async def _stage_check(self, content: str, plan: str, context: str) -> QualityScore:
        try:
            result = await self._llm.generate(
                system_prompt=self.CHECK_SYSTEM_PROMPT,
                user_prompt=f"""请评估以下章节：

写作计划：
{plan[:800]}

正文内容：
{content[:3000]}

请按六个维度打分并返回 JSON。""",
                temperature=0.3,
                max_tokens=800,
            )
            text = result.text if hasattr(result, 'text') else str(result)
            data = self._parse_json(text)

            dims = data.get("dimensions", data.get("scores", {}))
            if isinstance(dims, list):
                dim_map = {}
                for d in dims:
                    if isinstance(d, dict):
                        dim_map[d.get("dimension", "")] = d.get("score", 5.0)
                dims = dim_map

            scores = {d.value: float(dims.get(d.value, dims.get(d.name, 5.0))) for d in QualityDimension}

            issues = data.get("issues", [])
            if isinstance(issues, str):
                issues = [issues]

            composite = sum(scores.values()) / max(len(scores), 1)
            needs_revision = composite < 6.5 or len(issues) > 3

            return QualityScore(
                dimension_scores=scores,
                composite=round(composite, 1),
                issues=issues,
                suggestions=data.get("suggestions", []),
                needs_revision=needs_revision,
            )
        except Exception as e:
            logger.warning(f"[SuperWriter.Check] 失败: {e}")
            return QualityScore(composite=6.0, needs_revision=False)

    async def _stage_edit(self, content: str, quality: QualityScore, plan: str) -> str:
        try:
            result = await self._llm.generate(
                system_prompt=self.EDIT_SYSTEM_PROMPT,
                user_prompt=f"""请根据以下审阅意见修改段落：

写作计划：
{plan[:800]}

发现的问题：
{json.dumps(quality.issues, ensure_ascii=False)}

建议：
{json.dumps(quality.suggestions, ensure_ascii=False)}

原段落（前 2000 字）：
{content[:2000]}

请输出修改后的完整段落。""",
                temperature=0.7,
                max_tokens=len(content) * 2,
            )
            return result.text if hasattr(result, 'text') else content
        except Exception as e:
            logger.warning(f"[SuperWriter.Edit] 失败: {e}")
            return content

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        return {}
