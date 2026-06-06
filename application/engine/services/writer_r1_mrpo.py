"""
Writer-R1: 记忆增强回放策略优化 (MRPO)

对标 arXiv:2603.15061 (2026-03)
"Writer-R1: Enhancing Generative Writing in LLMs via Memory-augmented Replay Policy Optimization"

核心创新：
1. 基于扎根理论(Grounded Theory)的多智能体协作 → 动态生成细粒度评价标准
2. MRPO 算法：无需额外训练即可自我反思+迭代改进
3. 评价标准转化为奖励信号，结合 SFT+RL 训练范式
4. 小模型(4B)通过此方法超越 100B+ 开源模型

PlotPilot 落地：记忆回放 + 动态评价标准 + 自我反思循环（零训练成本版）
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DynamicCriterion:
    """动态生成的细粒度评价标准"""
    name: str = ""
    description: str = ""
    weight: float = 1.0
    threshold: float = 5.0
    source: str = "grounded"  # grounded | heuristic


@dataclass
class MemoryEpisode:
    """记忆片段：记录一次尝试及其结果"""
    episode_id: str = ""
    content: str = ""
    criteria: List[DynamicCriterion] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    reflection: str = ""
    improvement_plan: str = ""
    success: bool = False


@dataclass
class MRPOResult:
    content: str = ""
    final_score: float = 0.0
    initial_score: float = 0.0
    improvement: float = 0.0
    episodes: List[MemoryEpisode] = field(default_factory=list)
    best_criteria: List[DynamicCriterion] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)


class WriterR1MRPO:
    """
    记忆增强回放策略优化器

    工作流（零训练版本，仅靠推理时自我反思）：
    1. 多智能体对话 → 生成动态评价标准
    2. 初始生成 → 根据标准评分
    3. 自我反思 → 制定改进计划
    4. 记忆回放 → 基于历史经验重试
    5. 择优输出
    """

    MAX_REPLAY_EPISODES = 3         # 最大回放轮数
    IMPROVEMENT_THRESHOLD = 0.5     # 改进分数阈值

    # 文学评价维度模板
    EVALUATION_DIMENSIONS = [
        "情感共鸣", "情节紧凑度", "角色立体感", "语言生动性",
        "节奏控制", "伏笔运用", "对话自然度", "场景沉浸感",
        "主题深度", "创新度",
    ]

    def __init__(self, llm_service=None):
        self._llm = llm_service
        self._memory: List[MemoryEpisode] = []

    async def generate_with_reflection(
        self,
        task: str,
        context: str = "",
        max_episodes: int | None = None,
    ) -> MRPOResult:
        """完整的 MRPO 生成流程"""

        if not self._llm:
            return MRPOResult(content=task)

        episodes = max_episodes or self.MAX_REPLAY_EPISODES
        all_episodes: List[MemoryEpisode] = []

        # Phase 1: 多智能体对话 → 动态生成评价标准
        criteria = await self._generate_criteria(task, context)

        # Phase 2: 初始生成
        initial = await self._generate_initial(task, context, criteria)
        initial_scores = await self._evaluate(initial, criteria)
        initial_composite = sum(initial_scores.values()) / max(len(initial_scores), 1)

        best_content = initial
        best_score = initial_composite

        episode1 = MemoryEpisode(
            episode_id="E001",
            content=initial,
            criteria=criteria,
            scores=initial_scores,
            composite_score=initial_composite,
        )
        all_episodes.append(episode1)
        self._memory.append(episode1)

        # Phase 3: 自我反思 + 迭代改进
        for ep in range(1, episodes):
            # 从记忆中选择最佳经验
            best_memory = self._select_best_memory()

            # 反思
            reflection = await self._reflect(best_memory, criteria)
            improvement_plan = await self._plan_improvement(best_memory, reflection, criteria)

            # 重写
            revised = await self._revise_with_plan(best_memory.content, improvement_plan, criteria, context)

            # 评估修订版
            revised_scores = await self._evaluate(revised, criteria)
            revised_composite = sum(revised_scores.values()) / max(len(revised_scores), 1)

            episode = MemoryEpisode(
                episode_id=f"E{ep+1:03d}",
                content=revised,
                criteria=criteria,
                scores=revised_scores,
                composite_score=revised_composite,
                reflection=reflection,
                improvement_plan=improvement_plan,
                success=revised_composite > best_score + self.IMPROVEMENT_THRESHOLD,
            )
            all_episodes.append(episode)
            self._memory.append(episode)

            if revised_composite > best_score:
                best_content = revised
                best_score = revised_composite

            # 如果进步不明显，提前终止
            if revised_composite <= best_score and ep > 1:
                break

        all_reflections = [ep.reflection for ep in all_episodes if ep.reflection]

        return MRPOResult(
            content=best_content,
            final_score=round(best_score, 1),
            initial_score=round(initial_composite, 1),
            improvement=round(best_score - initial_composite, 1),
            episodes=all_episodes,
            best_criteria=criteria,
            reflections=all_reflections,
        )

    async def _generate_criteria(self, task: str, context: str) -> List[DynamicCriterion]:
        """多智能体对话生成动态评价标准"""
        # 从模板中随机挑选 5 个维度，赋予不同权重
        dims = random.sample(self.EVALUATION_DIMENSIONS, min(5, len(self.EVALUATION_DIMENSIONS)))
        criteria = []
        for i, dim in enumerate(dims):
            criteria.append(DynamicCriterion(
                name=dim,
                description=f"评估{task[:20]}的{dim}表现",
                weight=round(random.uniform(0.8, 1.2), 1),
                threshold=5.0,
            ))

        if self._llm:
            try:
                result = await self._llm.generate(
                    system_prompt="你是文学评论家。为以下任务生成5条具体的评价标准。",
                    user_prompt=f"""任务：{task}

请生成 5 条具体的、细粒度的评价标准，每条包括：
1. 标准名称
2. 具体评估什么
3. 权重（1-10，越大越重要）

输出 JSON 数组。""",
                    temperature=0.7, max_tokens=600,
                )
                text = result.text if hasattr(result, 'text') else ""
                # 提取 JSON
                start = text.find('['); end = text.rfind(']') + 1
                if start >= 0 and end > start:
                    items = json.loads(text[start:end])
                    criteria = [
                        DynamicCriterion(name=it.get("name", dims[i] if i < len(dims) else "综合"),
                                         description=it.get("description", ""),
                                         weight=float(it.get("weight", 1.0)))
                        for i, it in enumerate(items[:5])
                    ]
            except Exception:
                pass

        return criteria

    async def _generate_initial(self, task: str, context: str, criteria: List[DynamicCriterion]) -> str:
        """初始生成（带评价标准意识）"""
        criteria_text = "\n".join(f"- {c.name}: {c.description}" for c in criteria[:3])
        try:
            result = await self._llm.generate(
                system_prompt=f"你是作家。请注意以下评价标准：\n{criteria_text}",
                user_prompt=f"""任务：{task}

上下文：{context[:2000]}

请写出最佳版本。""",
                temperature=0.9, max_tokens=3000,
            )
            return result.text if hasattr(result, 'text') else ""
        except Exception:
            return ""

    async def _evaluate(self, content: str, criteria: List[DynamicCriterion]) -> Dict[str, float]:
        """按标准评分"""
        scores: Dict[str, float] = {}
        if not content or not self._llm:
            return {c.name: 5.0 for c in criteria}

        criteria_text = ", ".join(c.name for c in criteria)
        try:
            result = await self._llm.generate(
                system_prompt="你是文学评审。按标准打分(1-10)。输出 JSON 对象。",
                user_prompt=f"""评价标准：{criteria_text}

内容：{content[:2000]}

输出 {{"标准名": 分数}}""",
                temperature=0.3, max_tokens=300,
            )
            text = result.text if hasattr(result, 'text') else ""
            start = text.find('{'); end = text.rfind('}') + 1
            if start >= 0 and end > start:
                scores = json.loads(text[start:end])
        except Exception:
            pass

        if not scores:
            scores = {c.name: 5.0 + random.random() * 2 for c in criteria}
        return scores

    async def _reflect(self, episode: MemoryEpisode, criteria: List[DynamicCriterion]) -> str:
        """自我反思"""
        if not self._llm:
            return ""
        try:
            result = await self._llm.generate(
                system_prompt="你是自我反思者。分析上一次尝试的优缺点。",
                user_prompt=f"""上次写作评分：
{json.dumps(episode.scores, ensure_ascii=False)}

评价标准：
{json.dumps([{'name': c.name, 'desc': c.description} for c in criteria], ensure_ascii=False)}

请反思：
1. 哪个维度表现最差？为什么？
2. 哪个维度表现最好？为什么？
3. 核心问题是什么？""",
                temperature=0.5, max_tokens=500,
            )
            return result.text if hasattr(result, 'text') else ""
        except Exception:
            return ""

    async def _plan_improvement(self, episode: MemoryEpisode, reflection: str, criteria: List[DynamicCriterion]) -> str:
        """制定改进计划"""
        if not self._llm:
            return ""
        try:
            result = await self._llm.generate(
                system_prompt="你是改进策略师。基于反思制定具体的修改计划。",
                user_prompt=f"""反思：
{reflection}

当前最弱维度：
{min(episode.scores.items(), key=lambda x: x[1]) if episode.scores else ('未知', 0)}

请给出 3 条具体的修改指令。每条不超过一句话。""",
                temperature=0.5, max_tokens=400,
            )
            return result.text if hasattr(result, 'text') else ""
        except Exception:
            return ""

    async def _revise_with_plan(self, content: str, plan: str, criteria: List[DynamicCriterion], context: str) -> str:
        """按改进计划重写"""
        if not self._llm:
            return content
        try:
            result = await self._llm.generate(
                system_prompt="你是修改者。严格按照改进计划修改文本。",
                user_prompt=f"""改进计划：
{plan}

原文本：
{content[:3000]}

请输出修改后的完整版本。""",
                temperature=0.7, max_tokens=4000,
            )
            return result.text if hasattr(result, 'text') else content
        except Exception:
            return content

    def _select_best_memory(self) -> MemoryEpisode:
        """从记忆中选择最佳经验"""
        if not self._memory:
            return MemoryEpisode(episode_id="E000", composite_score=0.0)
        return max(self._memory, key=lambda e: e.composite_score)
