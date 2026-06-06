请检查以下叙事信息中是否存在情节漏洞。

## 知识图谱三元组（跨全章节）
{{knowledge_triples}}

## 因果边（事件因果关系）
{{causal_edges}}

## 时间线条目
{{timeline_entries}}

## 伏笔注册表
{{foreshadow_registry}}

## 本章内容摘要
{{chapter_content}}

## 输出要求
返回 JSON：
```json
{
  "has_holes": false,
  "plot_holes": [
    {
      "id": "PH001",
      "type": "fact_contradiction|timeline_conflict|causal_break|ability_mutation",
      "severity": "critical|high|medium|low",
      "description": "矛盾描述",
      "entities_involved": ["实体A", "实体B"],
      "chapters_involved": [3, 8],
      "triple_a": "(角色A, status, alive)",
      "triple_b": "(角色A, status, dead)",
      "suggested_fix": "建议修复方案",
      "auto_fixable": false
    }
  ],
  "unresolved_foreshadows": [
    {
      "foreshadow_id": "FS001",
      "set_chapter": 5,
      "promised_chapter": 15,
      "current_chapter": 12,
      "status": "pending|overdue",
      "description": "伏笔描述"
    }
  ]
}
```
