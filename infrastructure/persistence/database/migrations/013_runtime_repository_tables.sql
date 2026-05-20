-- 013: 原仓储 __init__ 内联 DDL 收敛到迁移（避免每次启动重复入队）

CREATE TABLE IF NOT EXISTS timeline_registries (
    novel_id TEXT PRIMARY KEY,
    data JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confluence_points (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    source_storyline_id TEXT NOT NULL,
    target_storyline_id TEXT NOT NULL,
    target_chapter INTEGER NOT NULL,
    merge_type TEXT NOT NULL,
    context_summary TEXT DEFAULT '',
    pre_reveal_hint TEXT DEFAULT '',
    behavior_guards TEXT DEFAULT '[]',
    resolved INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS cast_snapshots (
    novel_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapter_guardrail_snapshots (
    novel_id TEXT NOT NULL,
    chapter_number INTEGER NOT NULL,
    report_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (novel_id, chapter_number)
);

CREATE TABLE IF NOT EXISTS custom_theme_skills (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    skill_key TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    skill_description TEXT DEFAULT '',
    compatible_genres TEXT DEFAULT '[]',
    context_prompt TEXT DEFAULT '',
    beat_prompt TEXT DEFAULT '',
    beat_triggers TEXT DEFAULT '',
    audit_checks TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(novel_id, skill_key)
);
