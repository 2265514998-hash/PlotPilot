"""
MCTS 层级质量评分 — SuperWriter Hierarchical DPO 等价实现

核心思想（来自 SuperWriter 论文 2506.04180）：
- 生成过程的每个中间步骤（Plan / Think / Write / Edit）都应该被评分
- 最终评分通过层级结构回传到上游步骤
- 这样才能训练/优化每个阶段的品质

实现方式：
- 六维度评分树
- 自动发现"最优路径"（Plan → Think → Write → Edit 的最佳组合）
- 层级分数回传
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QualityDim(str, Enum):
    COHERENCE = "coherence"
    LOGIC = "logic"
    ENGAGEMENT = "engagement"
    CHARACTER = "character"
    STYLE = "style"
    ORIGINALITY = "originality"


@dataclass
class StageScore:
    """单个流水线阶段的质量评分"""
    stage: str = ""
    dimensions: Dict[str, float] = field(default_factory=dict)
    composite: float = 0.0
    weight: float = 1.0  # 此阶段在总分中的权重


@dataclass
class PathScore:
    """一条完整流水线路径的评分"""
    path_id: str = ""
    stage_scores: List[StageScore] = field(default_factory=list)
    final_composite: float = 0.0
    # 层级回传分数：final → edit → write → think → plan
    backpropagated: Dict[str, float] = field(default_factory=dict)


class MCTSScorer:
    """
    层级质量评分器

    工作方式：
    1. 收集每个管道阶段的质量分数
    2. 计算加权综合分
    3. 将最终分回传到上游阶段
    4. 追踪多条路径找最优
    """

    # 六维度的阶段权重——不同阶段侧重不同维度
    STAGE_WEIGHTS: Dict[str, Dict[str, float]] = {
        "plan": {
            "coherence": 0.30, "logic": 0.30, "engagement": 0.15,
            "character": 0.10, "style": 0.05, "originality": 0.10,
        },
        "think": {
            "coherence": 0.25, "logic": 0.20, "engagement": 0.15,
            "character": 0.15, "style": 0.10, "originality": 0.15,
        },
        "write": {
            "coherence": 0.15, "logic": 0.10, "engagement": 0.30,
            "character": 0.20, "style": 0.15, "originality": 0.10,
        },
        "check": {
            "coherence": 0.25, "logic": 0.25, "engagement": 0.10,
            "character": 0.15, "style": 0.15, "originality": 0.10,
        },
        "edit": {
            "coherence": 0.20, "logic": 0.15, "engagement": 0.20,
            "character": 0.15, "style": 0.20, "originality": 0.10,
        },
    }

    # 层级回传的衰减因子
    BACKPROP_DECAY: Dict[str, float] = {
        "edit": 1.0,    # 最终层不收衰减
        "write": 0.9,   # 离最终近
        "think": 0.7,   # 中间层
        "plan": 0.5,    # 最上游
    }

    def __init__(self):
        self._paths: List[PathScore] = []
        self._best_path: PathScore | None = None

    def score_stage(
        self,
        stage: str,
        dim_scores: Dict[str, float],
        llm_eval: str = "",
    ) -> StageScore:
        """评分单个阶段"""
        weights = self.STAGE_WEIGHTS.get(stage, self.STAGE_WEIGHTS["write"])

        weighted = 0.0
        for dim, score in dim_scores.items():
            w = weights.get(dim, 1.0 / len(dim_scores))
            weighted += score * w

        composite = round(weighted / max(sum(weights.get(d, 0) for d in dim_scores), 1), 1)

        # 如果有 LLM 评估文本，尝试提取打分
        if llm_eval:
            try:
                eval_data = json.loads(llm_eval)
                if isinstance(eval_data, dict):
                    llm_composite = float(eval_data.get("overall", eval_data.get("composite", composite)))
                    composite = round((composite + llm_composite) / 2, 1)
            except (json.JSONDecodeError, ValueError):
                pass

        return StageScore(stage=stage, dimensions=dim_scores, composite=composite)

    def backpropagate(self, path: PathScore) -> PathScore:
        """
        层级回传：最终分数向上游回传

        Plan ← Think ← Write ← Edit ← Final
        每层按衰减因子接收下游分数
        """
        if not path.stage_scores:
            return path

        final_score = path.final_composite
        path.backpropagated = {}

        for ss in reversed(path.stage_scores):
            decay = self.BACKPROP_DECAY.get(ss.stage, 0.5)
            path.backpropagated[ss.stage] = round(final_score * decay, 2)
            final_score = path.backpropagated[ss.stage]

        return path

    def score_path(
        self,
        path_id: str,
        stages: List[Tuple[str, Dict[str, float]]],
    ) -> PathScore:
        """评分一条完整流水线路径"""
        stage_scores = [self.score_stage(name, dims) for name, dims in stages]

        # 综合分 = 编辑阶段 40% + 写作阶段 35% + 规划阶段 15% + 思考阶段 10%
        weights = {"edit": 0.40, "write": 0.35, "plan": 0.15, "think": 0.10, "check": 0.0}
        composite = 0.0
        total_w = 0.0
        for ss in stage_scores:
            w = weights.get(ss.stage, 0.15)
            composite += ss.composite * w
            total_w += w

        final = round(composite / max(total_w, 0.01), 1)

        path = PathScore(path_id=path_id, stage_scores=stage_scores, final_composite=final)
        path = self.backpropagate(path)
        self._paths.append(path)

        if self._best_path is None or path.final_composite > self._best_path.final_composite:
            self._best_path = path

        return path

    def get_best_path(self) -> PathScore | None:
        return self._best_path

    def summarize(self) -> Dict[str, Any]:
        """生成评分摘要"""
        if not self._paths:
            return {"status": "no_data"}

        composites = [p.final_composite for p in self._paths]
        return {
            "total_paths": len(self._paths),
            "best_score": max(composites),
            "avg_score": round(sum(composites) / len(composites), 1),
            "best_path_id": self._best_path.path_id if self._best_path else "",
            "dimension_trends": self._dimension_trends(),
        }

    def _dimension_trends(self) -> Dict[str, List[float]]:
        trends: Dict[str, List[float]] = {}
        for path in self._paths:
            for ss in path.stage_scores:
                for dim, score in ss.dimensions.items():
                    if dim not in trends:
                        trends[dim] = []
                    trends[dim].append(score)
        return {dim: [round(sum(scores) / len(scores), 1)] for dim, scores in trends.items()}
