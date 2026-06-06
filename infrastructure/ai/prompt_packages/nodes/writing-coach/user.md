请审阅以下章节内容，作为写作教练给出建议。

## 当前章节
第 {{chapter_number}} 章

## 章节内容
{{chapter_content}}

## 写作质量数据
- 张力综合分: {{tension_scores}}
- 风格漂移分: {{drift_score}}
- 当前节拍焦点: {{beat_focus}}

## 涉及角色状态
{{character_states}}

## 输出要求
返回 JSON（教练语气，不超过 3 条建议）：
```json
{
  "encouragement": "一句话肯定（如'这章的对话节奏很好'）",
  "suggestions": [
    {
      "priority": 1,
      "tag": "sensory|pacing|character|conflict|show_dont_tell",
      "question": "以提问方式给出（如'在主角推开那扇门的瞬间，你是否考虑过加入一两个声音细节——比如门轴生锈的吱呀声？'）",
      "context_hint": "指向的段落位置",
      "actionable": true
    }
  ],
  "top_strength": "本章最突出的优点"
}
```
