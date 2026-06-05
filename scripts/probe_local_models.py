#!/usr/bin/env python3
"""探测本机模型与后端连通性。用法: python scripts/probe_local_models.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from application.workspace.local_workspace_service import LocalWorkspaceService
from interfaces.api.dependencies import get_novel_service


def main() -> int:
    report = LocalWorkspaceService(get_novel_service()).probe_local_models()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    s = report["summary"]
    if s.get("local_llm_runtime") or s.get("local_embedding_ready") or s.get("cloud_llm_configured"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
