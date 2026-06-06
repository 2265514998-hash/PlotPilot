根据以下章节的叙事事件列表，判断该章节在当前故事中所处的结构位置。

## 小说信息
- 类型: {{novel_genre}}
- 当前章节: 第 {{chapter_number}} 章
- 总预估章节数: {{total_chapters}}

## 本章叙事事件
{{narrative_events}}

## 输出要求
返回 JSON：
```json
{
  "structural_role": "ACT2-对抗-中点危机",
  "act_phase": "ACT2",
  "story_beat": "midpoint_crisis",
  "beat_label_cn": "中点转折",
  "confidence": 0.85,
  "rationale": "判断依据一句话",
  "progress_estimate": 0.48,
  "next_milestone": "第二掐点",
  "structure_tags": ["ACT2", "升压", "信息揭示", "关系转折"]
}
```
