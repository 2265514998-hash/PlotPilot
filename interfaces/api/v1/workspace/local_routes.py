"""本地扫描与快速连接 API。"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from application.workspace.local_workspace_service import LocalWorkspaceService, ScanResult
from interfaces.api.dependencies import get_novel_service
from application.core.services.novel_service import NovelService

router = APIRouter(prefix="/local", tags=["local-workspace"])


def get_local_workspace_service(
    novel_service: NovelService = Depends(get_novel_service),
) -> LocalWorkspaceService:
    return LocalWorkspaceService(novel_service)


class LocalScanRequest(BaseModel):
    roots: List[str] = Field(..., min_length=1, description="要扫描的目录绝对路径列表")
    depth: int = Field(4, ge=1, le=6)
    include_patterns: Optional[List[str]] = Field(
        None, description="保留字段；当前实现按 .txt/.md/.docx 识别"
    )
    detect_plotpilot_db: bool = True


class ChapterPreviewItem(BaseModel):
    number: int
    title: str
    path: str
    words: int = 0


class ScanCandidateResponse(BaseModel):
    kind: str
    path: str
    title_guess: str
    chapter_files: int
    total_words_estimate: int
    confidence: float
    chapter_preview: List[ChapterPreviewItem] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)


class LocalScanResponse(BaseModel):
    scan_id: str
    roots: List[str]
    candidates: List[ScanCandidateResponse]
    warnings: List[str] = Field(default_factory=list)


class LocalConnectRequest(BaseModel):
    mode: Literal["import_manuscript", "open_novel"] = "import_manuscript"
    source_path: str
    novel_title: Optional[str] = None
    author: str = "本地导入"
    target_words_per_chapter: int = Field(2500, ge=500, le=15000)


class LocalConnectResponse(BaseModel):
    novel_id: str
    title: str
    imported_chapters: int
    total_words: int
    skipped_files: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)


class HealthProbeResponse(BaseModel):
    probes: List[Dict[str, Any]]


class LocalModelProbeResponse(BaseModel):
    services: List[Dict[str, Any]]
    embedding: Dict[str, Any]
    llm_env: Dict[str, Any]
    summary: Dict[str, Any]


class ConnectLocalLlmRequest(BaseModel):
    service_id: str = Field(..., description="ollama | lm_studio | localai")
    model: Optional[str] = Field(
        None,
        description="留空则自动匹配：优先 Ollama 正在运行的模型，再选聊天模型（跳过 embed/rerank）",
    )
    base_url: Optional[str] = Field(
        None,
        description="手动指定 OpenAI 兼容地址（如 http://127.0.0.1:11434/v1），跳过可达性探测",
    )


class ConnectLocalLlmResponse(BaseModel):
    profile_id: str
    service_id: str
    label: Optional[str] = None
    base_url: str
    model: str
    runtime: Dict[str, Any] = Field(default_factory=dict)


class AutoConnectLocalLlmResponse(BaseModel):
    connected: bool
    skipped: bool = False
    method: str = "none"
    reason: Optional[str] = None
    profile_id: Optional[str] = None
    service_id: Optional[str] = None
    label: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    runtime: Dict[str, Any] = Field(default_factory=dict)
    services: List[Dict[str, Any]] = Field(default_factory=list)


def _scan_to_response(result: ScanResult) -> LocalScanResponse:
    candidates = [
        ScanCandidateResponse(
            kind=c.kind,
            path=c.path,
            title_guess=c.title_guess,
            chapter_files=c.chapter_files,
            total_words_estimate=c.total_words_estimate,
            confidence=c.confidence,
            chapter_preview=[
                ChapterPreviewItem(**p) for p in c.chapter_preview
            ],
            extra=c.extra,
        )
        for c in result.candidates
    ]
    return LocalScanResponse(
        scan_id=result.scan_id,
        roots=result.roots,
        candidates=candidates,
        warnings=result.warnings,
    )


@router.post("/scan", response_model=LocalScanResponse)
async def scan_local(
    body: LocalScanRequest,
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    """扫描本地目录，识别书稿文件夹或 PlotPilot 数据目录。"""
    try:
        result = service.scan(
            roots=body.roots,
            depth=body.depth,
            include_patterns=body.include_patterns,
            detect_plotpilot_db=body.detect_plotpilot_db,
        )
        return _scan_to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/scan/{scan_id}", response_model=LocalScanResponse)
async def get_scan_result(
    scan_id: str,
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    result = service.get_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="扫描结果不存在或已过期")
    return _scan_to_response(result)


@router.post("/connect", response_model=LocalConnectResponse)
async def connect_local(
    body: LocalConnectRequest,
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    """将本地书稿目录导入为 PlotPilot 小说（连续章号 1..n）。"""
    if body.mode != "import_manuscript":
        raise HTTPException(
            status_code=400,
            detail="当前仅支持 mode=import_manuscript",
        )
    try:
        payload = service.connect_import_manuscript(
            source_path=body.source_path,
            novel_title=body.novel_title,
            author=body.author,
            target_words_per_chapter=body.target_words_per_chapter,
        )
        return LocalConnectResponse(**payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/model-probe", response_model=LocalModelProbeResponse)
async def model_probe(
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    """探测本机 Ollama / LM Studio / LocalAI 与本地嵌入模型是否可用。"""
    return service.probe_local_models()


@router.post("/connect-llm", response_model=ConnectLocalLlmResponse)
async def connect_local_llm(
    body: ConnectLocalLlmRequest,
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    """一键将本机 LLM 写入 AI 控制台并激活（含占位 API Key 与模型名）。"""
    try:
        payload = service.connect_local_llm_profile(
            body.service_id,
            body.model,
            base_url_override=body.base_url,
        )
        from application.ai.llm_control_service import LLMControlService
        from infrastructure.ai.provider_factory import (
            LLMProviderFactory,
            invalidate_dynamic_llm_cache,
        )
        from interfaces.api.v1.workbench.llm_control import _invalidate_llm_panel_cache

        _invalidate_llm_panel_cache()
        invalidate_dynamic_llm_cache()

        runtime = dict(payload.get("runtime") or {})
        control = LLMControlService()
        profile = control.resolve_active_profile()
        if profile is not None:
            factory = LLMProviderFactory(control)
            test = await control.test_profile_model(
                profile,
                lambda p: factory.create_from_profile(p),
            )
            runtime["verified"] = test.ok
            runtime["verify_preview"] = (test.preview or "")[:120]
            if not test.ok:
                runtime["verify_error"] = test.error or "试跑失败"
        payload["runtime"] = runtime
        return ConnectLocalLlmResponse(**payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/auto-connect-llm", response_model=AutoConnectLocalLlmResponse)
async def auto_connect_local_llm(
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    """探测并自动连接本机 LLM（含默认地址回退），供前端启动时调用。"""
    from infrastructure.ai.provider_factory import invalidate_dynamic_llm_cache
    from interfaces.api.v1.workbench.llm_control import _invalidate_llm_panel_cache

    payload = service.auto_connect_local_llm()
    if payload.get("connected") and not payload.get("skipped"):
        _invalidate_llm_panel_cache()
        invalidate_dynamic_llm_cache()
        profile = None
        if payload.get("profile_id"):
            from application.ai.llm_control_service import LLMControlService
            from infrastructure.ai.provider_factory import LLMProviderFactory

            control = LLMControlService()
            profile = control.resolve_active_profile()
            if profile:
                factory = LLMProviderFactory(control)
                test = await control.test_profile_model(
                    profile,
                    lambda p: factory.create_from_profile(p),
                )
                rt = dict(payload.get("runtime") or {})
                rt["verified"] = test.ok
                if not test.ok:
                    rt["verify_error"] = test.error
                else:
                    rt["verify_preview"] = (test.preview or "")[:120]
                payload["runtime"] = rt
    return AutoConnectLocalLlmResponse(
        connected=bool(payload.get("connected")),
        skipped=bool(payload.get("skipped")),
        method=str(payload.get("method") or "none"),
        reason=payload.get("reason"),
        profile_id=payload.get("profile_id"),
        service_id=payload.get("service_id"),
        label=payload.get("label"),
        base_url=payload.get("base_url"),
        model=payload.get("model"),
        runtime=payload.get("runtime") or {},
        services=payload.get("services") or [],
    )


@router.get("/health-probe", response_model=HealthProbeResponse)
async def health_probe(
    hosts: str = "127.0.0.1",
    ports: str = "8005",
    service: LocalWorkspaceService = Depends(get_local_workspace_service),
):
    # 限制探针范围，防止 SSRF 放大攻击
    _ALLOWED_HOST_PREFIXES = ("127.0.0.1", "localhost", "0.0.0.0", "::1", "192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.")
    host_list = [h.strip() for h in hosts.split(",") if h.strip()][:5]  # 最多 5 个主机
    # 只允许本地/内网地址
    host_list = [h for h in host_list if any(h.startswith(p) for p in _ALLOWED_HOST_PREFIXES)]
    port_list = []
    for p in ports.split(",")[:10]:  # 最多 10 个端口
        p = p.strip()
        if p.isdigit():
            port_num = int(p)
            if 1 <= port_num <= 65535:
                port_list.append(port_num)
    probes = service.health_probe(host_list or None, port_list or None)
    return HealthProbeResponse(probes=probes)
