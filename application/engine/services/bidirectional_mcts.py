"""
BiT-MCTS: 高潮优先·双向蒙特卡洛树搜索

对标 arXiv:2603.14410 (2026-04)
"BiT-MCTS: A Theme-based Bidirectional MCTS Approach to Chinese Fiction Generation"

核心创新：
1. 从主题中提取核心戏剧冲突 → 生成显式高潮
2. 双向 MCTS 从高潮向前（上升动作/开场）和向后（下落动作/结局）扩展
3. 对应 Freytag 金字塔五段结构

PlotPilot 落地：中文网文优化的高潮优先 + 双向扩展策略
"""

from __future__ import annotations

import math
import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FreytagPhase(str, Enum):
    EXPOSITION = "exposition"       # 开场
    RISING_ACTION = "rising_action" # 上升动作
    CLIMAX = "climax"              # 高潮
    FALLING_ACTION = "falling_action" # 下落动作
    RESOLUTION = "resolution"      # 结局


@dataclass
class MCTSNode:
    id: str = ""
    phase: FreytagPhase = FreytagPhase.CLIMAX
    content: str = ""              # 该节点的叙事内容
    parent_id: str = ""
    children: List[str] = field(default_factory=list)
    visits: int = 0
    quality_score: float = 0.0
    coherence_score: float = 0.0
    theme_score: float = 0.0
    ucb: float = 0.0
    depth: int = 0


@dataclass
class BiTResult:
    climax: str = ""
    forward_chain: List[str] = field(default_factory=list)  # 高潮→结局
    backward_chain: List[str] = field(default_factory=list) # 开场→高潮
    full_structure: Dict[str, Any] = field(default_factory=dict)
    total_nodes: int = 0
    best_path_score: float = 0.0


class BiTMCTS:
    """
    高潮优先，双向搜索

    工作流：
    1. 从主题提取核心冲突 → 生成高潮
    2. 从高潮节点向后搜索：上升动作 → 开场
    3. 从高潮节点向前搜索：下落动作 → 结局
    4. UCB 平衡探索(exploration)与利用(exploitation)
    """

    EXPLORATION_CONSTANT = 1.4     # UCB1 探索参数
    MAX_DEPTH = 6                   # 单向最大深度
    SIMULATION_BUDGET = 20          # 每方向 MCTS 模拟次数

    # 网文节奏的高潮策略
    SHUANGWEN_CLIMAX_TYPES = [
        "身份揭露", "实力碾压", "逆天改命",
        "绝境反杀", "真相大白", "情感爆发",
    ]

    def __init__(self, llm_service=None, theme: str = "", total_chapters: int = 30):
        self._llm = llm_service
        self._theme = theme
        self._total_chapters = total_chapters
        self._nodes: Dict[str, MCTSNode] = {}
        self._climax_node: MCTSNode | None = None

    async def search(self, premise: str = "") -> BiTResult:
        """执行完整的双向 MCTS 搜索"""

        if not self._llm:
            return BiTResult(climax="[需要 LLM]", total_nodes=0)

        # Step 1: 提取核心冲突 + 生成高潮
        climax = await self._generate_climax(premise)
        self._climax_node = MCTSNode(
            id="N_climax", phase=FreytagPhase.CLIMAX,
            content=climax, depth=0, visits=1, quality_score=8.0,
        )
        self._nodes["N_climax"] = self._climax_node

        # Step 2: 向后搜索（高潮→开场）
        backward_root = self._climax_node
        for _ in range(self.SIMULATION_BUDGET):
            await self._mcts_rollout(backward_root, direction="backward")

        backward_chain = self._extract_best_path(backward_root, "backward")

        # Step 3: 向前搜索（高潮→结局）
        forward_root = self._climax_node
        for _ in range(self.SIMULATION_BUDGET):
            await self._mcts_rollout(forward_root, direction="forward")

        forward_chain = self._extract_best_path(forward_root, "forward")

        # Step 4: 组装完整结构
        full = {
            "exposition": backward_chain[-1].content if len(backward_chain) > 0 else "",
            "rising_action": [n.content for n in reversed(backward_chain[:-1])],
            "climax": climax,
            "falling_action": [n.content for n in forward_chain[:-1]],
            "resolution": forward_chain[-1].content if len(forward_chain) > 0 else "",
            "phases": {
                "exposition_pct": 15,
                "rising_pct": 35,
                "climax_pct": 15,
                "falling_pct": 25,
                "resolution_pct": 10,
            },
        }

        return BiTResult(
            climax=climax,
            forward_chain=[n.content for n in forward_chain],
            backward_chain=[n.content for n in reversed(backward_chain)],
            full_structure=full,
            total_nodes=len(self._nodes),
            best_path_score=self._climax_node.quality_score,
        )

    async def _generate_climax(self, premise: str) -> str:
        """生成核心高潮场景"""
        climax_type = random.choice(self.SHUANGWEN_CLIMAX_TYPES)
        try:
            result = await self._llm.generate(
                system_prompt=f"你是一位网文高潮场景设计师。高潮类型：{climax_type}",
                user_prompt=f"""基于以下前提，生成这个故事的核心高潮场景：

前提：{premise}

高潮类型：{climax_type}

请描述：
1. 高潮发生的具体场景和时机
2. 谁是关键参与者
3. 核心冲突如何爆发和解决
4. 情绪顶点是什么
5. 对后续剧情的影响

输出一段300字以内的高潮描述。""",
                temperature=0.9, max_tokens=800,
            )
            return result.text if hasattr(result, 'text') else f"[{climax_type}高潮]"
        except Exception:
            return f"[{climax_type}高潮]"

    async def _mcts_rollout(self, root: MCTSNode, direction: str):
        """单次 MCTS rollout"""
        node = root
        path = [node.id]
        depth = 0

        # Selection + Expansion
        while depth < self.MAX_DEPTH:
            child = self._select_child(node, direction)
            if child is None:
                child = await self._expand(node, direction)
                if child is None:
                    break
            node = child
            path.append(node.id)
            depth += 1

        # Simulation (简化：用 LLM 评估叶节点)
        score = await self._simulate(node, direction)

        # Backpropagation
        for nid in path:
            self._nodes[nid].visits += 1
            self._nodes[nid].quality_score = max(self._nodes[nid].quality_score, score)

    def _select_child(self, parent: MCTSNode, direction: str) -> MCTSNode | None:
        """UCB1 选择最佳子节点"""
        if not parent.children:
            return None

        best = None
        best_ucb = -float('inf')

        for cid in parent.children:
            child = self._nodes.get(cid)
            if child is None:
                continue
            if child.visits == 0:
                child.ucb = float('inf')
            else:
                exploitation = child.quality_score / child.visits
                exploration = self.EXPLORATION_CONSTANT * math.sqrt(
                    math.log(parent.visits) / child.visits
                )
                child.ucb = exploitation + exploration

            if child.ucb > best_ucb:
                best_ucb = child.ucb
                best = child

        return best

    async def _expand(self, parent: MCTSNode, direction: str) -> MCTSNode | None:
        """扩展一个新子节点"""
        if parent.depth >= self.MAX_DEPTH:
            return None

        next_phase = self._next_phase(parent.phase, direction)
        if next_phase is None:
            return None

        node_id = f"N_{next_phase.value}_{len(self._nodes)}"
        content = await self._generate_phase_content(parent.content, next_phase, direction)

        child = MCTSNode(
            id=node_id, phase=next_phase, content=content,
            parent_id=parent.id, depth=parent.depth + 1,
        )
        self._nodes[node_id] = child
        parent.children.append(node_id)
        return child

    async def _simulate(self, node: MCTSNode, direction: str) -> float:
        """评估节点质量（通过 LLM 或启发式）"""
        if not self._llm:
            return 5.0 + random.random() * 2

        try:
            result = await self._llm.generate(
                system_prompt="请给以下叙事节点的质量打分（1-10）。只输出数字。",
                user_prompt=f"节点内容：{node.content[:500]}\n阶段：{node.phase.value}",
                temperature=0.3, max_tokens=10,
            )
            text = result.text if hasattr(result, 'text') else "7"
            return float(text.strip().split()[0])
        except Exception:
            return 5.0 + random.random() * 2

    async def _generate_phase_content(self, parent_content: str, phase: FreytagPhase, direction: str) -> str:
        """生成阶段内容"""
        if not self._llm:
            return f"[{phase.value}节点]"

        dir_cn = "向前" if direction == "forward" else "向后"
        try:
            result = await self._llm.generate(
                system_prompt=f"你是一位故事策划师。正在{dir_cn}展开故事。当前阶段：{phase.value}",
                user_prompt=f"""从前一节点 {dir_cn} 推进到 {phase.value} 阶段。

前一节点：{parent_content[:500]}

请用一段话描述这个阶段的核心事件。200字以内。""",
                temperature=0.8, max_tokens=400,
            )
            return result.text if hasattr(result, 'text') else f"[{phase.value}]"
        except Exception:
            return f"[{phase.value}]"

    def _next_phase(self, current: FreytagPhase, direction: str) -> FreytagPhase | None:
        """计算下一个叙事阶段"""
        if direction == "backward":
            # 高潮 ← 上升动作 ← 开场 ← None
            mapping = {
                FreytagPhase.CLIMAX: FreytagPhase.RISING_ACTION,
                FreytagPhase.RISING_ACTION: FreytagPhase.EXPOSITION,
                FreytagPhase.EXPOSITION: None,
            }
        else:
            # 高潮 → 下落动作 → 结局 → None
            mapping = {
                FreytagPhase.CLIMAX: FreytagPhase.FALLING_ACTION,
                FreytagPhase.FALLING_ACTION: FreytagPhase.RESOLUTION,
                FreytagPhase.RESOLUTION: None,
            }
        return mapping.get(current)

    def _extract_best_path(self, root: MCTSNode, direction: str) -> List[MCTSNode]:
        """从根节点提取质量最高的路径"""
        path = [root]
        node = root
        while node.children:
            best_child = max(
                (self._nodes[cid] for cid in node.children if cid in self._nodes),
                key=lambda n: n.quality_score / max(n.visits, 1),
                default=None,
            )
            if best_child is None:
                break
            path.append(best_child)
            node = best_child
        return path
