请检查以下章节内容中的角色一致性。

## 角色档案（已知设定）
{{character_states}}

## 本章内容
{{chapter_content}}

## 本章涉及角色
{{chapter_characters}}

## 输出要求
返回 JSON：
```json
{
  "overall_ooc_score": 0.15,
  "violations": [
    {
      "character_name": "角色名",
      "dimension": "personality|knowledge|ability|relationship|timeline",
      "severity": "critical|high|medium|low",
      "expected_behavior": "根据设定，角色应该...",
      "actual_behavior": "但在章节中，角色...",
      "location_hint": "问题出现在第一节对话中",
      "suggestion": "建议修改为..."
    }
  ],
  "chapter_arc_progression": {
    "character_name": "角色名",
    "arc_advancement": 0.3,
    "note": "角色在本章中完成了从X到Y的转变"
  }
}
```
仅在确实存在问题时输出 violations，不要虚构问题。
