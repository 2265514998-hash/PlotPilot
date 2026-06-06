"""
反思式规划器 — 替代单次规划，采用 Plan → Critique → Refine 循环

支持三种深度：
- quick (1轮): 直接生成
- standard (2轮): Plan → Critique → Refine
- deep (3轮): Plan → Critique → Refine → Critique → Re-refine
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlannerDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class ReflectivePlan:
    plan: str = ""
    weaknesses: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    score: float = 0.0
    rounds: int = 0
    final: bool = False


class ReflectivePlanner:
    """Plan → Critique → Refine 反思循环"""

    CRITIQUE_PROMPT_TEMPLATE = """你是一位资深编辑。请审阅以下大纲，找出至少 3 个可以改进的地方：

## 大纲
{plan}

## 审阅要求
1. 情节连贯性：事件之间是否存在逻辑跳跃？
2. 角色合理性：角色的行动是否符合其动机？
3. 节奏：是否有拖沓或过于仓促的段落？
4. 高潮储备：高潮是否有足够的铺垫？
5. 商业性：是否包含"爽点"和"钩子"？

请以严格 JSON 格式返回审阅结果。
"""

    REFINE_PROMPT_TEMPLATE = """你是一位资深故事策划。请根据以下审阅意见，精炼你的大纲。

## 当前大纲
{plan}

## 审阅意见
{critique}

## 精炼要求
- 保留核心情节主线不变
- 针对性修复每个指出的问题
- 增加具体细节而非泛泛修改
- 确保修改后各个场景之间的过渡自然

请输出精炼后的完整大纲。
"""

    SYSTEM_PLAN = "你是一位经验丰富的长篇小说策划师。你精于构建紧凑、有张力、商业性强的章节大纲。"
    SYSTEM_CRITIQUE = "你是一位挑剔的资深编辑。你的审阅精准、不客气，但每一条批评都附带具体的改进方向。"
    SYSTEM_REFINE = "你是一位善于听取反馈的故事策划师。你能在不丢失原创想法的情况下，精准地修复每个问题。"

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def plan_with_reflection(
        self,
        task: str,
        context: str = "",
        target_chapters: int = 3,
        depth: PlannerDepth = PlannerDepth.STANDARD,
    ) -> ReflectivePlan:
        """带反思的规划过程"""

        if not self._llm:
            logger.warning("[ReflectivePlanner] 无 LLM 服务，返回空规划")
            return ReflectivePlan()

        # Round 1: 初始规划
        plan = await self._generate_plan(task, context, target_chapters)
        weaknesses: List[str] = []
        improvements: List[str] = []
        score = 0.0

        if depth == PlannerDepth.QUICK:
            return ReflectivePlan(plan=plan, score=0.7, rounds=1, final=True)

        # Round 2: 批判
        critique = await self._critique_plan(plan)
        if critique:
            weaknesses = critique.get("weaknesses", [])
            score = critique.get("overall_score", 0.5)

            # 如果分数足够高，跳过精炼
            if score >= 0.75 and depth != PlannerDepth.DEEP:
                return ReflectivePlan(plan=plan, weaknesses=weaknesses, score=score, rounds=2, final=True)

            # 精炼
            plan = await self._refine_plan(plan, json.dumps(critique, ensure_ascii=False))
            improvements.append("基于审阅意见做了针对性精炼")

        # Round 3: 深度模式 — 再次批判 + 精炼
        if depth == PlannerDepth.DEEP:
            critique2 = await self._critique_plan(plan)
            if critique2:
                score2 = critique2.get("overall_score", 0.5)
                if score2 < 0.8:
                    plan = await self._refine_plan(plan, json.dumps(critique2, ensure_ascii=False))
                    improvements.append("第二轮精炼完成")
                score = score2
                weaknesses.extend(critique2.get("weaknesses", []))
            return ReflectivePlan(plan=plan, weaknesses=weaknesses, improvements=improvements, score=score, rounds=3, final=True)

        return ReflectivePlan(plan=plan, weaknesses=weaknesses, improvements=improvements, score=score, rounds=2, final=True)

    async def _generate_plan(self, task: str, context: str, target_chapters: int) -> str:
        """生成初始大纲"""
        prompt = f"""{task}

上下文信息：
{context}

目标章节数：{target_chapters} 章

请生成一个完整的章节大纲，格式为每章一行：
第N章：本章核心事件（一句话概括）
"""
        try:
            result = await self._llm.generate(
                system_prompt=self.SYSTEM_PLAN,
                user_prompt=prompt,
                temperature=0.8,
                max_tokens=2000,
            )
            return result.text if hasattr(result, 'text') else str(result)
        except Exception as e:
            logger.error(f"[ReflectivePlanner] 生成规划失败: {e}")
            return ""

    async def _critique_plan(self, plan: str) -> Dict[str, Any]:
        """审阅大纲"""
        prompt = self.CRITIQUE_PROMPT_TEMPLATE.format(plan=plan)
        try:
            result = await self._llm.generate(
                system_prompt=self.SYSTEM_CRITIQUE,
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=1000,
            )
            text = result.text if hasattr(result, 'text') else str(result)
            return json.loads(text) if isinstance(text, str) else text
        except Exception as e:
            logger.warning(f"[ReflectivePlanner] 审阅失败: {e}")
            return {}

    async def _refine_plan(self, plan: str, critique: str) -> str:
        """精炼大纲"""
        prompt = self.REFINE_PROMPT_TEMPLATE.format(plan=plan, critique=critique)
        try:
            result = await self._llm.generate(
                system_prompt=self.SYSTEM_REFINE,
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=2500,
            )
            return result.text if hasattr(result, 'text') else str(result)
        except Exception as e:
            logger.error(f"[ReflectivePlanner] 精炼失败: {e}")
            return plan
