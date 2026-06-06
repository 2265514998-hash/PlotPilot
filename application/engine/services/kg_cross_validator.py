"""
知识图谱生成后交叉验证 — 对标 SAGA 的 Graph Healing 节点

功能：
1. 从刚生成的章节提取新版三元组
2. 与现有 KG 进行差异比对
3. 标记冲突三元组（矛盾）
4. 标记新增三元组（新信息）
5. 标记过期三元组（需要更新/删除的旧信息）
6. 输出验证报告

这是 SAGA architecture 中 "validate_consistency" 和 "heal_graph" 两个节点的等价实现。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TripleStatus(str, Enum):
    CONFIRMED = "confirmed"         # 新旧一致
    NEW = "new"                     # 新增
    CONFLICT = "conflict"           # 矛盾
    UPDATED = "updated"             # 更新（旧值被覆盖）
    ORPHANED = "orphaned"           # 旧三元组在新章未被提及
    RESOLVED = "resolved"           # 冲突已自动解决
    NEEDS_HUMAN = "needs_human"     # 需要人工判断


@dataclass
class TripleDiff:
    """单个三元组的变更记录"""
    subject: str = ""
    predicate: str = ""
    old_value: str = ""
    new_value: str = ""
    status: TripleStatus = TripleStatus.CONFIRMED
    chapter_number: int = 0
    auto_resolved: bool = False
    suggestion: str = ""


@dataclass
class KGValidationReport:
    """KG 交叉验证报告"""
    chapter_id: str = ""
    total_triples_before: int = 0
    total_triples_after: int = 0
    diffs: List[TripleDiff] = field(default_factory=list)
    conflicts: List[TripleDiff] = field(default_factory=list)
    new_triples: List[TripleDiff] = field(default_factory=list)
    resolved: List[TripleDiff] = field(default_factory=list)
    needs_human: List[TripleDiff] = field(default_factory=list)
    health_score: float = 1.0


class KGCrossValidator:
    """
    知识图谱交叉验证器

    工作流程：
    1. 从新章提取候选三元组
    2. 与现有 KG 比对
    3. 标记冲突/新增/更新
    4. 自动解决简单冲突（如时间推进导致的状态变化）
    5. 标记需要人工判断的复杂冲突
    """

    # 可逆谓词——这些谓词的值可以随时间自然变化
    MUTABLE_PREDICATES: Set[str] = {
        "location", "status", "mood", "goal", "believes",
        "relationship_with", "current_plan", "holding",
        "位置", "状态", "情绪", "目标", "信念",
        "与...的关系", "当前计划", "持有",
    }

    # 不可逆谓词——这些谓词的值不应改变
    IMMUTABLE_PREDICATES: Set[str] = {
        "born_in", "parent_of", "original_name", "species",
        "birth_place", "master_of", "creator_of",
        "出生于", "父母", "原名", "种族",
        "出生地", "掌控", "创造者",
    }

    def __init__(self, llm_service=None):
        self._llm = llm_service

    def validate(
        self,
        chapter_id: str,
        existing_triples: List[Tuple[str, str, str]],
        new_candidates: List[Tuple[str, str, str]],
        chapter_number: int = 0,
    ) -> KGValidationReport:
        """运行完整的 KG 交叉验证"""

        existing: Dict[str, Dict[str, str]] = {}
        for s, p, o in existing_triples:
            existing.setdefault(s, {})[p] = o

        new: Dict[str, Dict[str, str]] = {}
        for s, p, o in new_candidates:
            new.setdefault(s, {})[p] = o

        diffs: List[TripleDiff] = []

        # 遍历新的候选三元组
        for s, predicates in new.items():
            for p, new_o in predicates.items():
                old_o = existing.get(s, {}).get(p)

                if old_o is None:
                    # 全新三元组
                    diffs.append(TripleDiff(
                        subject=s, predicate=p, new_value=new_o,
                        status=TripleStatus.NEW, chapter_number=chapter_number,
                    ))
                elif old_o == new_o:
                    # 一致
                    diffs.append(TripleDiff(
                        subject=s, predicate=p, old_value=old_o, new_value=new_o,
                        status=TripleStatus.CONFIRMED, chapter_number=chapter_number,
                    ))
                else:
                    # 值变了 —— 检查是否合理
                    diff = TripleDiff(
                        subject=s, predicate=p, old_value=old_o, new_value=new_o,
                        status=TripleStatus.NEEDS_HUMAN, chapter_number=chapter_number,
                    )

                    if p in self.MUTABLE_PREDICATES:
                        # 可变谓词的变化通常是合法的
                        diff.status = TripleStatus.RESOLVED
                        diff.auto_resolved = True
                        diff.suggestion = f"{s} 的 {p} 从 '{old_o}' 更新为 '{new_o}'（合理变化）"
                    elif p in self.IMMUTABLE_PREDICATES:
                        # 不可变谓词的变化需要仔细审查
                        diff.status = TripleStatus.NEEDS_HUMAN
                        diff.suggestion = f"警告：{s} 的 {p} 从 '{old_o}' 变为 '{new_o}'，此项不应改变！"
                    else:
                        # 未知谓词 —— 标记需要人工判断
                        diff.status = TripleStatus.NEEDS_HUMAN
                        diff.suggestion = f"{s} 的 {p} 值发生了变化：'{old_o}' → '{new_o}'，请确认是否合理。"

                    diffs.append(diff)

        # 检查旧三元组是否被遗漏
        for s, predicates in existing.items():
            for p, old_o in predicates.items():
                if s not in new or p not in new.get(s, {}):
                    # 旧三元组在新章中未被提及
                    diffs.append(TripleDiff(
                        subject=s, predicate=p, old_value=old_o,
                        status=TripleStatus.ORPHANED, chapter_number=chapter_number,
                        suggestion=f"{s} 的 {p} ({old_o}) 在新章节中未被提及，考虑是否仍需保留。",
                    ))

        report = KGValidationReport(
            chapter_id=chapter_id,
            total_triples_before=len(existing_triples),
            total_triples_after=len(new_candidates),
            diffs=diffs,
            conflicts=[d for d in diffs if d.status == TripleStatus.CONFLICT],
            new_triples=[d for d in diffs if d.status == TripleStatus.NEW],
            resolved=[d for d in diffs if d.status == TripleStatus.RESOLVED],
            needs_human=[d for d in diffs if d.status == TripleStatus.NEEDS_HUMAN],
        )

        # 计算健康分数
        total_issues = len(report.conflicts) + len(report.needs_human)
        total_triples = max(len(existing_triples) + len(new_candidates), 1)
        report.health_score = round(max(0, 1.0 - (total_issues / total_triples * 5)), 2)

        return report

    def heal(
        self,
        report: KGValidationReport,
        auto_apply: bool = True,
    ) -> Dict[str, Any]:
        """基于验证报告修复 KG（自动处理可解决的冲突）"""
        actions: List[Dict[str, str]] = []

        for diff in report.resolved:
            if auto_apply and diff.auto_resolved:
                actions.append({
                    "action": "update",
                    "subject": diff.subject,
                    "predicate": diff.predicate,
                    "from": diff.old_value,
                    "to": diff.new_value,
                    "reason": diff.suggestion,
                })

        for diff in report.new_triples:
            actions.append({
                "action": "insert",
                "subject": diff.subject,
                "predicate": diff.predicate,
                "value": diff.new_value,
            })

        human_actions = []
        for diff in report.needs_human:
            human_actions.append({
                "subject": diff.subject,
                "predicate": diff.predicate,
                "old_value": diff.old_value,
                "new_value": diff.new_value,
                "suggestion": diff.suggestion,
            })

        return {
            "auto_applied": len(actions),
            "auto_actions": actions,
            "needs_human_review": len(human_actions),
            "human_actions": human_actions,
            "health_score": report.health_score,
        }
