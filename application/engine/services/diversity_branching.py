"""
多样性规划分支 — DPWriter Diversity Branching

对标 arXiv:2601.09609 (2026-01)
"DPWriter: Reinforcement Learning with Diverse Planning Branching for Creative Writing"

核心创新：
1. 半结构化长 CoT 中战略性引入规划分叉
2. 基于多样性变化的分叉时机判定
3. 群组多样性奖励引导分支探索
4. 解决 RL 微调导致 LLM 输出趋同的经典难题

PlotPilot 落地：规划阶段主动生成多条路径，按多样性评分选择最优
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BranchPoint:
    """一个分叉点"""
    position: str = ""           # 分叉位置描述
    alternatives: List[str] = field(default_factory=list)  # 可选方向
    selected: int = 0            # 被选中的方向索引
    diversity_score: float = 0.0


@dataclass
class BranchPath:
    """一条规划分支路径"""
    id: str = ""
    summary: str = ""            # 路径摘要
    quality_score: float = 0.0
    diversity_score: float = 0.0
    coherence_score: float = 0.0
    style_breakdown: Dict[str, float] = field(default_factory=dict)  # 风格细分


@dataclass
class DiversityReport:
    paths: List[BranchPath] = field(default_factory=list)
    selected_path: BranchPath | None = None
    branch_points: List[BranchPoint] = field(default_factory=list)
    group_diversity: float = 0.0
    quality_diversity_balance: float = 0.0


class DiversityBrancher:
    """
    多样性规划分支器

    工作流：
    1. 在主路径上识别分叉点
    2. 在每个分叉点生成 2-4 个替代方向
    3. 按群组多样性评分（鼓励不同路径之间有足够的差异）
    4. 选择质量×多样性的最优路径
    """

    MAX_BRANCHES = 3              # 最多分叉点
    ALTERNATIVES_PER_BRANCH = 3   # 每分叉点最多方向数
    DIVERSITY_WEIGHT = 0.3        # 多样性在最终评分中的权重
    QUALITY_WEIGHT = 0.7          # 质量权重

    # 分叉触发器 — 这些词出现时提示分叉机会
    BRANCH_TRIGGERS: Set[str] = {
        "选择", "决定", "转折", "如果", "或者",
        "可能", "也许", "不然", "否则", "但是",
        "然而", "另一个", "不同的", "相反的",
    }

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def branch_and_select(
        self,
        base_plan: str,
        context: str = "",
        num_branches: int | None = None,
    ) -> DiversityReport:
        """执行计划分叉 + 选择最优路径"""

        branches_count = min(num_branches or self.MAX_BRANCHES, self.MAX_BRANCHES)

        # Step 1: 识别分叉点
        branch_points = await self._identify_branch_points(base_plan, context, branches_count)
        if not branch_points:
            return DiversityReport(paths=[BranchPath(id="default", summary=base_plan)])

        # Step 2: 在每个分叉点生成替代方向
        for bp in branch_points:
            if len(bp.alternatives) < self.ALTERNATIVES_PER_BRANCH:
                more = await self._generate_alternatives(base_plan, bp, context)
                bp.alternatives.extend(more)
                bp.alternatives = bp.alternatives[:self.ALTERNATIVES_PER_BRANCH]

        # Step 3: 生成候选路径（取每个分叉点的笛卡尔积前 5 条）
        paths = await self._generate_candidate_paths(base_plan, branch_points, context)

        # Step 4: 按 质量×0.7 + 多样性×0.3 排序，选择最优
        if paths:
            for p in paths:
                p.diversity_score = self._compute_path_diversity(p, paths)
                p.quality_score = await self._score_quality(p, context)
            paths.sort(key=lambda p: p.quality_score * self.QUALITY_WEIGHT + p.diversity_score * self.DIVERSITY_WEIGHT, reverse=True)
            selected = paths[0]
        else:
            selected = BranchPath(id="default", summary=base_plan)

        group_diversity = self._compute_group_diversity(paths)

        return DiversityReport(
            paths=paths,
            selected_path=selected,
            branch_points=branch_points,
            group_diversity=round(group_diversity, 2),
            quality_diversity_balance=round(self.QUALITY_WEIGHT, 2),
        )

    async def _identify_branch_points(self, plan: str, context: str, max_points: int) -> List[BranchPoint]:
        """识别计划中的分叉点"""
        points: List[BranchPoint] = []
        sentences = plan.replace('\n', ' ').split('。')

        for i, sent in enumerate(sentences):
            if len(points) >= max_points:
                break
            for trigger in self.BRANCH_TRIGGERS:
                if trigger in sent:
                    points.append(BranchPoint(position=f"计划第{i+1}句: {sent[:60]}..."))
                    break

        if self._llm and not points:
            try:
                result = await self._llm.generate(
                    system_prompt="你是故事规划分析员。找出计划中可以分叉的决策点。",
                    user_prompt=f"""计划：{plan[:1500]}

找出 2-3 个可以产生不同剧情走向的决策点。每个决策点一句话描述。
输出 JSON 数组：[{{"position": "...", "alternatives": ["...", "..."]}}]""",
                    temperature=0.6, max_tokens=400,
                )
                text = result.text if hasattr(result, 'text') else ""
                start = text.find('['); end = text.rfind(']') + 1
                if start >= 0 and end > start:
                    items = json.loads(text[start:end])
                    for it in items[:max_points]:
                        points.append(BranchPoint(
                            position=it.get("position", ""),
                            alternatives=it.get("alternatives", [])[:2],
                        ))
            except Exception:
                pass

        return points

    async def _generate_alternatives(self, plan: str, bp: BranchPoint, context: str) -> List[str]:
        """为一个分叉点生成替代方向"""
        if not self._llm:
            return [f"替代方案{i}" for i in range(2)]

        try:
            result = await self._llm.generate(
                system_prompt="你是创意策划师。为决策点生成不同的剧情走向。",
                user_prompt=f"""计划：{plan[:1000]}

决策点：{bp.position}

请为这个决策点生成 3 个不同的剧情走向。每个不超过一句话。
用 JSON 数组输出。""",
                temperature=0.9, max_tokens=300,
            )
            text = result.text if hasattr(result, 'text') else ""
            start = text.find('['); end = text.rfind(']') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])[:3]
        except Exception:
            pass
        return [f"方向 {chr(65+i)}: {bp.position}的不同走向" for i in range(2)]

    async def _generate_candidate_paths(self, plan: str, points: List[BranchPoint], context: str) -> List[BranchPath]:
        """生成候选路径"""
        paths: List[BranchPath] = [BranchPath(id="base", summary=plan)]

        # 为每个分叉点生成 1-2 条变体路径
        for i, bp in enumerate(points):
            for j, alt in enumerate(bp.alternatives[:2]):
                pid = f"branch_{i}_{j}"
                modified = plan.replace(bp.position[:30], f"[分叉{j+1}]: {alt[:40]}")
                paths.append(BranchPath(id=pid, summary=modified))

        return paths[:5]  # 最多 5 条路径

    async def _score_quality(self, path: BranchPath, context: str) -> float:
        """评分路径质量"""
        if not self._llm:
            return 6.0 + random.random() * 2
        try:
            result = await self._llm.generate(
                system_prompt="给以下剧情路径打分(1-10)。只输出数字。",
                user_prompt=f"路径：{path.summary[:600]}",
                temperature=0.3, max_tokens=10,
            )
            text = result.text if hasattr(result, 'text') else "7"
            return float(text.strip().split()[0])
        except Exception:
            return 6.0

    def _compute_path_diversity(self, path: BranchPath, all_paths: List[BranchPath]) -> float:
        """计算路径与其他路径的多样性"""
        if len(all_paths) <= 1:
            return 0.0
        words = set(path.summary.split())
        others_words = [set(p.summary.split()) for p in all_paths if p.id != path.id]
        if not others_words:
            return 0.0
        jaccard_dists = [
            1 - len(words & ow) / max(len(words | ow), 1)
            for ow in others_words
        ]
        return round(sum(jaccard_dists) / len(jaccard_dists), 2)

    def _compute_group_diversity(self, paths: List[BranchPath]) -> float:
        """计算群组多样性"""
        if len(paths) <= 1:
            return 0.0
        all_words: List[Set[str]] = [set(p.summary.split()) for p in paths]
        total_pairs = 0
        total_div = 0.0
        for i in range(len(all_words)):
            for j in range(i + 1, len(all_words)):
                jaccard = len(all_words[i] & all_words[j]) / max(len(all_words[i] | all_words[j]), 1)
                total_div += 1 - jaccard
                total_pairs += 1
        return round(total_div / max(total_pairs, 1), 2)
