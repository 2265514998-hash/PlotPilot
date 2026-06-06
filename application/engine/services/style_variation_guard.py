"""
叙事扁平化防护 — 风格多样性巡检

对标 arXiv:2605.27878 (2026-05)
"Narrative Flattening: How Post-Training Compresses Thematic, Affective, and Stylistic Variation in LLM Fiction"

核心发现（论文重要警示）：
后训练(RLHF/DPO)会系统性地压缩主题运动、情感变化和风格多样性，
尤其对专业文学小说（纽约客风格）压缩最严重。

PlotPilot 落地：跨章节风格多样性巡检，当检测到"扁平化"时自动注入变化指令
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StyleProfile:
    """单章风格画像"""
    chapter_id: str = ""
    chapter_number: int = 0
    avg_sentence_length: float = 0.0
    dialogue_ratio: float = 0.0
    emotional_variance: float = 0.0
    adjective_density: float = 0.0
    unique_word_ratio: float = 0.0
    paragraph_length_variance: float = 0.0
    tone: str = "neutral"


@dataclass
class FlatteningAlert:
    """扁平化告警"""
    dimension: str = ""        # 检测维度
    severity: str = "low"     # low / medium / high
    chapters_affected: List[int] = field(default_factory=list)
    trend: str = ""           # 趋势描述
    suggestion: str = ""      # 修复建议
    auto_fix_enabled: bool = False


@dataclass
class VariationReport:
    chapters_analyzed: int = 0
    overall_variation_score: float = 1.0  # 越高越多变
    alerts: List[FlatteningAlert] = field(default_factory=list)
    theme_drift_detected: bool = False
    style_monotony_detected: bool = False
    fix_suggestions: List[str] = field(default_factory=list)


class StyleVariationGuard:
    """
    风格多样性巡检器

    检测三个维度的"扁平化"：
    1. 主题运动（thematic movement）— 主题/母题是否在跨章演进？
    2. 情感变化（affective variation）— 情绪跨度是否在收窄？
    3. 风格多样性（stylistic diversity）— 句式/修辞/节奏是否趋同？

    告警时自动注入变化指令到下一章的生成提示中。
    """

    FLATTENING_THRESHOLDS = {
        "sentence_length_std": 3.0,      # 句长方差低于此值 → 告警
        "emotional_range": 0.2,          # 情感跨度低于此值 → 告警
        "adjective_density_range": 0.03, # 形容词密度变化低于此值 → 告警
        "unique_word_drop": 0.15,        # 独特词比例连续下降 → 告警
        "tone_monotony": 3,              # 连续相同语气超过此章数 → 告警
    }

    def __init__(self):
        self._style_history: List[StyleProfile] = []

    def analyze_chapter(self, profile: StyleProfile) -> List[FlatteningAlert]:
        """分析单章风格，返回告警列表"""
        self._style_history.append(profile)
        alerts: List[FlatteningAlert] = []

        if len(self._style_history) < 3:
            return alerts  # 需要至少 3 章数据

        recent = self._style_history[-4:]  # 最近 4 章

        # 1. 句长单调检测
        sent_lengths = [p.avg_sentence_length for p in recent]
        sent_std = self._std(sent_lengths)
        if sent_std < self.FLATTENING_THRESHOLDS["sentence_length_std"]:
            alerts.append(FlatteningAlert(
                dimension="sentence_length",
                severity="medium",
                chapters_affected=[p.chapter_number for p in recent],
                trend=f"句长越来越单调（标准差 {sent_std:.1f}），连续 {len(recent)} 章缺乏变化",
                suggestion="建议在某些场景使用短句增加紧迫感，或通过长句营造氛围",
            ))

        # 2. 情感单调检测
        emotions = [p.emotional_variance for p in recent]
        emo_range = max(emotions) - min(emotions)
        if emo_range < self.FLATTENING_THRESHOLDS["emotional_range"]:
            alerts.append(FlatteningAlert(
                dimension="emotional_variance",
                severity="high",
                chapters_affected=[p.chapter_number for p in recent],
                trend=f"情感变化收窄（跨度 {emo_range:.2f}），情绪曲线趋于平坦",
                suggestion="建议引入情绪转折点、惊喜或挫折",
            ))

        # 3. 形容词密度检测
        adj_densities = [p.adjective_density for p in recent]
        adj_range = max(adj_densities) - min(adj_densities)
        if adj_range < self.FLATTENING_THRESHOLDS["adjective_density_range"]:
            alerts.append(FlatteningAlert(
                dimension="adjective_density",
                severity="low",
                chapters_affected=[p.chapter_number for p in recent],
                trend="形容词使用模式单调",
                suggestion="尝试在描写性段落增加感官细节，在动作段落减少修饰",
            ))

        # 4. 独特词比例连续下降
        unique_ratios = [p.unique_word_ratio for p in recent]
        drops = sum(1 for i in range(1, len(unique_ratios)) if unique_ratios[i] < unique_ratios[i - 1])
        if drops >= 2 and (unique_ratios[0] - unique_ratios[-1]) > self.FLATTENING_THRESHOLDS["unique_word_drop"]:
            alerts.append(FlatteningAlert(
                dimension="vocabulary",
                severity="medium",
                chapters_affected=[p.chapter_number for p in recent],
                trend=f"用词丰富度持续下降（{unique_ratios[0]:.2f} → {unique_ratios[-1]:.2f}）",
                suggestion="尝试在保持可读性的前提下引入新鲜的表达和意象",
            ))

        # 5. 语气单调
        tones = [p.tone for p in recent]
        same_tone_count = 1
        for i in range(len(tones) - 1, 0, -1):
            if tones[i] == tones[i - 1]:
                same_tone_count += 1
            else:
                break
        if same_tone_count >= self.FLATTENING_THRESHOLDS["tone_monotony"]:
            alerts.append(FlatteningAlert(
                dimension="tone",
                severity="medium",
                chapters_affected=[p.chapter_number for p in recent[-same_tone_count:]],
                trend=f"连续 {same_tone_count} 章语气维持 '{recent[-1].tone}'",
                suggestion=f"建议在下一章尝试不同的语气，如从 '叙事' 切换到 '对话驱动' 或 '内心独白'",
            ))

        return alerts

    def get_injection_hints(self) -> str:
        """基于历史风格数据，生成注入到下一章提示中的变化提示"""
        if len(self._style_history) < 2:
            return ""

        hints: List[str] = []
        recent = self._style_history[-3:]

        if recent:
            avg_sent = sum(p.avg_sentence_length for p in recent) / len(recent)
            avg_dialogue = sum(p.dialogue_ratio for p in recent) / len(recent)

            if avg_sent > 50:
                hints.append("本章建议增加短句比例，提升节奏感")
            if avg_dialogue < 0.15:
                hints.append("本章建议增加对话场景，通过角色互动推进剧情")
            if avg_dialogue > 0.5:
                hints.append("本章建议平衡对话与叙述，增加内心独白或环境描写")

        return "；".join(hints) if hints else ""

    def generate_report(self) -> VariationReport:
        """生成风格多样性报告"""
        if not self._style_history:
            return VariationReport()

        profiles = self._style_history[-10:]  # 最近 10 章

        alerts: List[FlatteningAlert] = []
        for i in range(len(profiles)):
            new_alerts = self.analyze_chapter(profiles[i]) if i < 3 else []
            alerts.extend(new_alerts)

        theme_drift = any(a.dimension == "tone" and a.severity == "high" for a in alerts)
        style_monotony = any(a.dimension == "sentence_length" and a.severity == "high" for a in alerts)

        variation_score = 1.0 - min(0.5, len(alerts) * 0.1)

        return VariationReport(
            chapters_analyzed=len(profiles),
            overall_variation_score=round(variation_score, 2),
            alerts=alerts,
            theme_drift_detected=theme_drift,
            style_monotony_detected=style_monotony,
            fix_suggestions=[a.suggestion for a in alerts if a.suggestion],
        )

    @staticmethod
    def _std(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5
