"""
迭代式写作引擎 — Write → Review → Rewrite 循环

每节拍生成后自动运行质量审查，未达标时触发重写。
最多 2 轮 rewrite，避免无限循环。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    content: str = ""
    quality_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    rounds: int = 1
    final: bool = True
    rewrote: bool = False


class IterativeWriter:
    """Write → Review → Rewrite — 质量闭环"""

    REVIEW_PROMPT = """请以挑剔的编辑眼光审查以下段落：

## 段落内容
{content}

## 审查维度 (每项打分 1-5)
1. 连贯性 (coherence): 段落内部逻辑是否自洽？
2. 文笔质量 (prose): 语言是否生动/精准/无陈词滥调？
3. 角色一致性 (character): 角色的言行是否与设定一致？
4. 展示vs告知 (show_dont_tell): 是否在"展示"而非"告知"？
5. 阅读流畅度 (readability): 是否容易理解？有无语病？

## 输出格式
严格 JSON：
{{
  "scores": {{"coherence": 4, "prose": 3, "character": 5, "show_dont_tell": 3, "readability": 4}},
  "overall": 3.8,
  "issues": ["问题1", "问题2"],
  "needs_rewrite": true/false,
  "rewrite_instructions": "如果 needs_rewrite=true，给出具体的重写方向"
}}
"""

    REWRITE_PROMPT = """请根据审查意见重写以下段落：

## 原段落
{content}

## 审查发现的问题
{issues}

## 重写方向
{instructions}

## 要求
- 保持原文的核心内容和情节不变
- 针对性修复每个指出的问题
- 不改变段落长度过多（±30%文字量）
- 保持原文的语气风格
"""

    REWRITE_THRESHOLD = 3.0  # 低于此分触发重写
    MAX_ROUNDS = 3  # 最多 3 轮（1 写 + 2 重写）

    def __init__(self, llm_service=None):
        self._llm = llm_service

    async def write_with_review(
        self,
        content: str,
        beat_context: str = "",
        rewrite_threshold: float | None = None,
    ) -> WriteResult:
        """对一段内容执行 Write → Review → Rewrite 闭环"""

        threshold = rewrite_threshold or self.REWRITE_THRESHOLD

        if not self._llm:
            return WriteResult(content=content, quality_score=3.0, final=True)

        current_content = content
        all_issues: List[str] = []
        final_score = 0.0
        rewrote = False

        for round_num in range(self.MAX_ROUNDS):
            # Review
            review = await self._review(current_content)
            final_score = review.get("overall", 3.0)
            issues = review.get("issues", [])
            all_issues.extend(issues)

            needs_rewrite = review.get("needs_rewrite", False)

            if not needs_rewrite or final_score >= threshold or round_num >= self.MAX_ROUNDS - 1:
                # 质量达标 或 已达最大轮次 — 结束
                break

            # Rewrite
            instructions = review.get("rewrite_instructions", "; ".join(issues))
            current_content = await self._rewrite(current_content, issues, instructions)
            rewrote = True

        return WriteResult(
            content=current_content,
            quality_score=final_score,
            issues=all_issues,
            rounds=round_num + 1,
            final=True,
            rewrote=rewrote,
        )

    async def _review(self, content: str) -> Dict[str, Any]:
        """审查内容"""
        import json as _json
        prompt = self.REVIEW_PROMPT.format(content=content[:3000])
        try:
            result = await self._llm.generate(
                system_prompt="你是一位挑剔的资深编辑。你的审查精准、直接，不拐弯抹角。",
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=800,
            )
            text = result.text if hasattr(result, 'text') else str(result)
            # 提取 JSON
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return _json.loads(text[start:end])
        except Exception as e:
            logger.warning(f"[IterativeWriter] 审查失败: {e}")
        return {"overall": 3.0, "issues": [], "needs_rewrite": False}

    async def _rewrite(self, content: str, issues: List[str], instructions: str) -> str:
        """重写内容"""
        prompt = self.REWRITE_PROMPT.format(
            content=content,
            issues="\n".join(f"- {i}" for i in issues),
            instructions=instructions,
        )
        try:
            result = await self._llm.generate(
                system_prompt="你是一位经验丰富的作家。你能精准地根据反馈修改文字，而不改变原作的核心。",
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=3000,
            )
            return result.text if hasattr(result, 'text') else str(result)
        except Exception as e:
            logger.warning(f"[IterativeWriter] 重写失败: {e}")
            return content
