请分析以下章节中每个主要角色的情感状态。

## 本章叙事事件
{{narrative_events}}

## 需追踪的角色
{{character_names}}

## 前序情感弧线（如已有）
{{previous_arc}}

## 当前章节号
第 {{chapter_number}} 章

## 输出要求
返回 JSON：
```json
{
  "chapter_emotions": {
    "角色名": {
      "primary_emotion": "hope",
      "primary_intensity": 6,
      "secondary_emotions": ["fear", "determination"],
      "complexity": "mixed",
      "trigger_event": "触发该情感的关键事件",
      "emotional_shift": {
        "from": "despair",
        "to": "hope",
        "magnitude": 4,
        "direction": "rising"
      }
    }
  },
  "chapter_emotional_tone": "dark_hope",
  "flat_segment_alert": {
    "character_name": "角色名",
    "flat_chapters": 3,
    "current_dominant_emotion": "anger",
    "suggestion": "建议增加情感变化或转折"
  },
  "arc_deviations": [
    {
      "character_name": "角色名",
      "expected_arc_type": "rising",
      "actual_trend": "flat",
      "deviation_level": "medium"
    }
  ]
}
```
