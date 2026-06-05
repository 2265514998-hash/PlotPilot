#!/usr/bin/env python3
"""一次性测试：本地书稿扫描 + 导入。用法: python scripts/test_local_import.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.engine.services.persistence_queue import (
    get_persistence_queue,
    initialize_persistence_queue,
    register_persistence_handlers,
)
from application.workspace.local_workspace_service import LocalWorkspaceService
from domain.novel.value_objects.novel_id import NovelId
from interfaces.api.dependencies import get_novel_service

TEST_DIR = ROOT / "data" / "test_import_manuscript"


def _boot_persistence() -> None:
    initialize_persistence_queue()
    register_persistence_handlers()
    get_persistence_queue().start_consumer()


def main() -> int:
    if not TEST_DIR.is_dir():
        print(f"缺少测试目录: {TEST_DIR}")
        return 1

    _boot_persistence()
    svc = LocalWorkspaceService(get_novel_service())
    novel_svc = get_novel_service()

    print("=== SCAN ===")
    scan = svc.scan([str(TEST_DIR)], depth=4)
    print("scan_id:", scan.scan_id)
    if scan.warnings:
        print("warnings:", scan.warnings)
    manuscripts = [c for c in scan.candidates if c.kind == "manuscript_folder"]
    if not manuscripts:
        print("未发现书稿候选")
        return 1
    hit = manuscripts[0]
    print(
        f"candidate: {hit.title_guess} | files={hit.chapter_files} "
        f"| words~={hit.total_words_estimate} | confidence={hit.confidence}"
    )

    print("\n=== CONNECT ===")
    result = svc.connect_import_manuscript(
        hit.path,
        novel_title="导入测试-山门篇",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    get_persistence_queue().wait_until_idle(timeout=15.0)

    print("\n=== VERIFY ===")
    novel_id = result["novel_id"]
    novel = novel_svc.get_novel(novel_id)
    print("novel:", novel_id, novel.title if novel else "?")
    chapters = novel_svc.chapter_repository.list_by_novel(NovelId(novel_id))
    for ch in sorted(chapters, key=lambda x: x.number):
        wc = ch.word_count.value if hasattr(ch.word_count, "value") else ch.word_count
        print(f"  第{ch.number}章 {ch.title!r} | words={wc} | content_len={len(ch.content or '')}")

    ok = result["imported_chapters"] == len(chapters) == 3
    print("\nRESULT:", "PASS" if ok else "FAIL")
    get_persistence_queue().stop_consumer()
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
