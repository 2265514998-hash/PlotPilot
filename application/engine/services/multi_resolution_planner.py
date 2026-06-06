"""
多分辨率规划骨架 — 全书级生成

对标 arXiv:2605.17064 (2026-05)
"Towards Human-Level Book-Writing Capability"

核心创新：
1. 从公有领域小说提取多层级规划骨架
2. 反转层级：全书前提 → 章节 → 场景 → 散文字段
3. 用人类原始散文作为最终监督目标
4. 远离"助手风格"，靠近人类文学写作

PlotPilot 落地：四级分辨率规划器 — 书→部→卷→幕→章→场景
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResolutionLevel(str, Enum):
    BOOK = "book"           # 全书前提
    PART = "part"           # 部
    VOLUME = "volume"       # 卷
    ACT = "act"             # 幕
    CHAPTER = "chapter"     # 章
    SCENE = "scene"         # 场景


@dataclass
class PlanNode:
    """规划骨架中的一个节点"""
    level: ResolutionLevel
    title: str = ""
    summary: str = ""                  # 该层级的摘要
    word_budget: int = 0               # 字数预算
    emotional_arc: str = ""            # 情感弧线标签
    key_events: List[str] = field(default_factory=list)  # 关键事件
    characters_focused: List[str] = field(default_factory=list)
    parent_id: str = ""
    children: List[str] = field(default_factory=list)
    style_directive: str = ""          # 风格指令


@dataclass
class BookScaffold:
    """全书的四级规划骨架"""
    book_theme: str = ""
    book_premise: str = ""             # 全书前提
    total_chapters: int = 30
    total_words_estimate: int = 90000
    nodes: Dict[str, PlanNode] = field(default_factory=dict)
    root_id: str = ""


class MultiResolutionPlanner:
    """
    四级分辨率规划器

    规划层次：
    Book → Part → Volume → Act → Chapter → Scene
    (全书→部→卷→幕→章→场景)

    每一层都包含：摘要、字数预算、情感弧线、关键事件、角色焦点
    展开时用基于风格指令的 prose 生成，远离"助手风格"
    """

    # 网文章节字数参考
    WORDS_PER_CHAPTER = 3000
    CHAPTERS_PER_ACT = 5
    ACTS_PER_VOLUME = 3
    VOLUMES_PER_PART = 2
    PARTS_PER_BOOK = 2

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def build_book_scaffold(
        self,
        premise: str,
        total_chapters: int = 30,
    ) -> BookScaffold:
        """构建全书的四级规划骨架"""

        scaffold = BookScaffold(
            book_premise=premise,
            total_chapters=total_chapters,
            total_words_estimate=total_chapters * self.WORDS_PER_CHAPTER,
        )

        # Level 0: 全书
        book_node = PlanNode(
            level=ResolutionLevel.BOOK,
            title="全书",
            summary=premise,
            style_directive="文学级叙事，远离AI助手风格，追求人类作家的自然节奏和情感深度",
        )
        book_id = "book_root"
        scaffold.nodes[book_id] = book_node
        scaffold.root_id = book_id

        # Level 1: 部（2 部）
        parts = total_chapters / self.CHAPTERS_PER_ACT / self.ACTS_PER_VOLUME / self.VOLUMES_PER_PART
        parts_count = max(1, min(2, int(parts)))
        for pi in range(parts_count):
            part_chapters = total_chapters // parts_count
            part_node = PlanNode(
                level=ResolutionLevel.PART,
                title=f"第{pi+1}部",
                word_budget=part_chapters * self.WORDS_PER_CHAPTER,
                emotional_arc="rising" if pi == 0 else "climax_resolution",
            )
            part_id = f"part_{pi}"
            scaffold.nodes[part_id] = part_node
            book_node.children.append(part_id)
            part_node.parent_id = book_id

            # Level 2: 卷（每部 1-2 卷）
            vols = max(1, part_chapters // (self.ACTS_PER_VOLUME * self.CHAPTERS_PER_ACT))
            for vi in range(vols):
                vol_chapters = part_chapters // vols
                vol_node = PlanNode(
                    level=ResolutionLevel.VOLUME,
                    title=f"第{pi+1}部 第{vi+1}卷",
                    word_budget=vol_chapters * self.WORDS_PER_CHAPTER,
                )
                vol_id = f"vol_{pi}_{vi}"
                scaffold.nodes[vol_id] = vol_node
                part_node.children.append(vol_id)
                vol_node.parent_id = part_id

                # Level 3: 幕（每卷 3 幕）
                for ai in range(min(self.ACTS_PER_VOLUME, vol_chapters // self.CHAPTERS_PER_ACT)):
                    act_chapters = min(self.CHAPTERS_PER_ACT, vol_chapters - ai * self.CHAPTERS_PER_ACT)
                    act_node = PlanNode(
                        level=ResolutionLevel.ACT,
                        title=f"第{pi+1}部 第{vi+1}卷 第{ai+1}幕",
                        word_budget=act_chapters * self.WORDS_PER_CHAPTER,
                        emotional_arc=["建立", "对抗", "爆发"][ai],
                    )
                    act_id = f"act_{pi}_{vi}_{ai}"
                    scaffold.nodes[act_id] = act_node
                    vol_node.children.append(act_id)
                    act_node.parent_id = vol_id

                    # Level 4: 章（每幕 5 章）
                    for ci in range(act_chapters):
                        chapter_num = (pi * part_chapters + vi * vol_chapters//vols +
                                       ai * act_chapters + ci + 1)
                        ch_node = PlanNode(
                            level=ResolutionLevel.CHAPTER,
                            title=f"第{chapter_num}章",
                            word_budget=self.WORDS_PER_CHAPTER,
                        )
                        ch_id = f"ch_{chapter_num}"
                        scaffold.nodes[ch_id] = ch_node
                        act_node.children.append(ch_id)
                        ch_node.parent_id = act_id

        scaffold.book_theme = f"基于前提 '{premise[:50]}...' 展开的{parts_count}部长篇小说"
        return scaffold

    async def expand_node(
        self,
        scaffold: BookScaffold,
        node_id: str,
        context: str = "",
    ) -> PlanNode:
        """展开一个节点——用 AI 填充摘要、关键事件和角色焦点"""
        node = scaffold.nodes.get(node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not found in scaffold")

        if not self._llm:
            return node

        try:
            result = await self._llm.generate(
                system_prompt=f"你是结构策划师。为{node.level.value}级别节点生成详细规划。",
                user_prompt=f"""在书籍骨架中，请为以下节点生成规划内容：

节点层级：{node.level.value}
节点标题：{node.title}
字数预算：{node.word_budget} 字
情感弧线目标：{node.emotional_arc or '待定'}
前文上下文：{context[:1000]}

请输出结构化 JSON：
{{
  "summary": "一句话摘要",
  "key_events": ["事件1", "事件2", "事件3"],
  "characters_focused": ["角色A", "角色B"],
  "style_directive": "风格指令（如'节奏紧凑的战斗场景'或'情感深沉的内心独白'）"
}}""",
                temperature=0.7, max_tokens=500,
            )
            text = result.text if hasattr(result, 'text') else ""
            import json
            start = text.find('{'); end = text.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                node.summary = data.get("summary", "")
                node.key_events = data.get("key_events", [])
                node.characters_focused = data.get("characters_focused", [])
                node.style_directive = data.get("style_directive", "")
        except Exception as e:
            logger.warning(f"[MultiResPlanner] 展开节点失败: {e}")

        return node

    def get_chapter_context(self, scaffold: BookScaffold, chapter_number: int) -> Dict[str, str]:
        """获取某章节的上下文摘要（包括所有祖先节点）"""
        ch_id = f"ch_{chapter_number}"
        node = scaffold.nodes.get(ch_id)
        if node is None:
            return {}

        context: Dict[str, str] = {}

        # 向上遍历祖先
        current_id = node.parent_id
        while current_id and current_id in scaffold.nodes:
            ancestor = scaffold.nodes[current_id]
            context[ancestor.level.value] = (
                f"{ancestor.title}: {ancestor.summary or '(未展开)'} "
                f"[{ancestor.emotional_arc or 'N/A'}]"
            )
            current_id = ancestor.parent_id

        return context
