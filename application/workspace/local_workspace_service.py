"""本地目录扫描与书稿快速导入。"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from application.core.services.novel_service import NovelService
from application.paths import DATA_DIR, get_db_path

logger = logging.getLogger(__name__)

SCAN_TTL_SEC = 3600
MAX_DEPTH = 6
MAX_FILES = 800
MAX_FILE_BYTES = 4 * 1024 * 1024
TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
DOCX_SUFFIX = ".docx"

CHAPTER_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"第\s*([0-9一二三四五六七八九十百千]+)\s*章", re.I),
    re.compile(r"chapter\s*([0-9]+)", re.I),
    re.compile(r"^([0-9]{1,4})[.\s_\-、]"),
]

_CN_NUM = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _parse_chinese_numeral(token: str) -> Optional[int]:
    token = (token or "").strip()
    if not token:
        return None
    if token.isdigit():
        n = int(token)
        return n if n > 0 else None
    if token == "十":
        return 10
    if "十" in token:
        parts = token.split("十", 1)
        hi = _CN_NUM.get(parts[0], 1) if parts[0] else 1
        lo = _CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return hi * 10 + lo
    total = 0
    for ch in token:
        if ch in _CN_NUM:
            total = total * 10 + _CN_NUM[ch]
        elif ch == "百":
            total = max(total, 1) * 100
        elif ch == "千":
            total = max(total, 1) * 1000
    return total if total > 0 else None


_SENSITIVE_PREFIXES_WINDOWS = (
    "c:\\windows", "c:\\program files", "c:\\programdata",
    "/etc", "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/boot", "/dev", "/proc", "/sys",
)


def _safe_resolve(path_str: str) -> Path:
    raw = (path_str or "").strip()
    if not raw:
        raise ValueError("路径不能为空")
    p = Path(raw).expanduser()
    try:
        resolved = p.resolve()
    except OSError as e:
        raise ValueError(f"无法解析路径: {path_str}") from e
    if not resolved.exists():
        raise ValueError(f"路径不存在: {resolved}")
    # 拒绝系统敏感目录
    resolved_lower = str(resolved).lower()
    for prefix in _SENSITIVE_PREFIXES_WINDOWS:
        if resolved_lower.startswith(prefix):
            raise ValueError(f"不允许访问系统目录: {resolved}")
    return resolved


def _read_text_file(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _read_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


@contextlib.contextmanager
def _direct_sqlite_import_writes():
    """批量导入时同步写库，避免持久化队列异步导致章号校验读到旧快照。"""
    key = "PLOTPILOT_ALLOW_DIRECT_SQLITE_WRITES"
    old = os.environ.get(key)
    os.environ[key] = "1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old


def _word_count(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", t))
    if cjk >= len(t) * 0.3:
        return cjk
    return len(t.split())


def _guess_chapter_number(name: str, fallback: int) -> int:
    base = Path(name).stem
    for pat in CHAPTER_PATTERNS:
        m = pat.search(base)
        if not m:
            continue
        raw = m.group(1)
        n = _parse_chinese_numeral(raw) if not raw.isdigit() else int(raw)
        if n and n > 0:
            return n
    return fallback


@dataclass
class ScannedChapterFile:
    path: str
    number: int
    title: str
    words: int


@dataclass
class ScanCandidate:
    kind: str
    path: str
    title_guess: str
    chapter_files: int
    total_words_estimate: int
    confidence: float
    chapter_preview: List[Dict[str, Any]] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    scan_id: str
    roots: List[str]
    candidates: List[ScanCandidate]
    scanned_at: float
    warnings: List[str] = field(default_factory=list)


_scan_cache: Dict[str, ScanResult] = {}


class LocalWorkspaceService:
    """扫描本地书稿 / 数据目录，并导入为 PlotPilot 小说。"""

    def __init__(self, novel_service: NovelService):
        self._novel_service = novel_service

    def scan(
        self,
        roots: List[str],
        depth: int = 4,
        include_patterns: Optional[List[str]] = None,
        detect_plotpilot_db: bool = True,
    ) -> ScanResult:
        depth = max(1, min(depth, MAX_DEPTH))
        warnings: List[str] = []
        resolved_roots: List[Path] = []
        for r in roots:
            try:
                resolved_roots.append(_safe_resolve(r))
            except ValueError as e:
                warnings.append(str(e))

        if not resolved_roots:
            raise ValueError("没有有效的扫描根路径")

        candidates: List[ScanCandidate] = []
        for root in resolved_roots:
            if root.is_file():
                warnings.append(f"跳过文件（需目录）: {root}")
                continue
            manuscript = self._scan_manuscript_folder(root, depth, warnings)
            if manuscript:
                candidates.append(manuscript)
            if detect_plotpilot_db:
                db_hit = self._detect_plotpilot_db(root)
                if db_hit:
                    candidates.append(db_hit)

        scan_id = f"scan_{uuid.uuid4().hex[:12]}"
        result = ScanResult(
            scan_id=scan_id,
            roots=[str(p) for p in resolved_roots],
            candidates=candidates,
            scanned_at=time.time(),
            warnings=warnings,
        )
        _scan_cache[scan_id] = result
        self._prune_scan_cache()
        return result

    def get_scan(self, scan_id: str) -> Optional[ScanResult]:
        return _scan_cache.get(scan_id)

    def connect_import_manuscript(
        self,
        source_path: str,
        novel_title: Optional[str] = None,
        author: str = "本地导入",
        target_words_per_chapter: int = 2500,
    ) -> Dict[str, Any]:
        root = _safe_resolve(source_path)
        if not root.is_dir():
            raise ValueError("书稿导入需要目录路径")

        warnings: List[str] = []
        files = self._collect_chapter_files(root, 4, warnings)
        if not files:
            raise ValueError("目录下未找到可导入的章节文件（.txt / .md / .docx）")

        files.sort(key=lambda f: (f.number, f.path.lower()))
        # 导入时强制连续章号 1..n，避免 add_chapter 校验失败
        chapters_to_import: List[Tuple[ScannedChapterFile, str]] = []
        for idx, item in enumerate(files, start=1):
            content = self._load_file_content(Path(item.path))
            meta = ScannedChapterFile(
                path=item.path,
                number=idx,
                title=item.title or f"第{idx}章",
                words=_word_count(content),
            )
            chapters_to_import.append((meta, content))

        total_words = sum(m.words for m, _ in chapters_to_import)
        title = (novel_title or root.name).strip() or "未命名书稿"
        novel_id = f"novel-local-{int(time.time() * 1000)}"
        target_chapters = max(len(chapters_to_import), 10)

        premise = f"【本地书稿导入】\n\n来源目录：{root}"
        imported = 0
        skipped: List[str] = []

        with _direct_sqlite_import_writes():
            self._novel_service.create_novel(
                novel_id=novel_id,
                title=title,
                author=author,
                target_chapters=target_chapters,
                premise=premise,
                genre="本地导入",
                world_preset="",
                target_words_per_chapter=target_words_per_chapter,
            )
            self._novel_service.ensure_default_act_for_chapters(novel_id)

            for ch, content in chapters_to_import:
                if not (content or "").strip():
                    skipped.append(ch.path)
                    continue
                chapter_id = f"chapter-{novel_id}-{ch.number}"
                try:
                    self._novel_service.add_chapter(
                        novel_id=novel_id,
                        chapter_id=chapter_id,
                        number=ch.number,
                        title=ch.title,
                        content=content.strip(),
                    )
                    imported += 1
                except Exception as e:
                    logger.warning("import chapter failed %s: %s", ch.path, e)
                    skipped.append(ch.path)

        return {
            "novel_id": novel_id,
            "title": title,
            "imported_chapters": imported,
            "total_words": total_words,
            "skipped_files": skipped,
            "warnings": warnings,
            "next_actions": ["open_workbench", "start_autopilot"],
        }

    def health_probe(
        self,
        hosts: Optional[List[str]] = None,
        ports: Optional[List[int]] = None,
        timeout_sec: float = 1.5,
    ) -> List[Dict[str, Any]]:
        hosts = hosts or ["127.0.0.1"]
        ports = ports or [8005]
        results: List[Dict[str, Any]] = []
        paths = ("/api/stats/global", "/docs")
        with httpx.Client(timeout=timeout_sec) as client:
            for host in hosts:
                for port in ports:
                    base = f"http://{host}:{port}"
                    ok = False
                    detail = ""
                    for path in paths:
                        url = f"{base}{path}"
                        try:
                            r = client.get(url)
                            if r.status_code < 500:
                                ok = True
                                detail = f"{path} → {r.status_code}"
                                break
                        except Exception as e:
                            detail = str(e)
                    results.append(
                        {
                            "host": host,
                            "port": port,
                            "reachable": ok,
                            "base_url": base,
                            "detail": detail,
                        }
                    )
        return results

    @staticmethod
    def _openai_compatible_models_base(base_url: str) -> str:
        from urllib.parse import urlparse, urlunparse

        raw = (base_url or "").strip() or "http://127.0.0.1:11434/v1"
        if "://" not in raw:
            raw = f"http://{raw}"
        parsed = urlparse(raw)
        path = (parsed.path or "").rstrip("/") or "/v1"
        if not path.startswith("/"):
            path = "/" + path
        return urlunparse(
            (parsed.scheme or "http", parsed.netloc, path, "", "", "")
        ).rstrip("/")

    _NON_CHAT_MODEL_HINTS = (
        "embed",
        "rerank",
        "nomic-embed",
        "bge-",
        "mxbai-embed",
        "e5-",
        "minilm",
        "snowflake-arctic-embed",
    )
    _CHAT_MODEL_HINTS = (
        "qwen",
        "llama",
        "mistral",
        "gemma",
        "deepseek",
        "phi",
        "chatglm",
        "gpt-oss",
        "command",
        "granite",
        "vicuna",
        "mixtral",
        "internlm",
        "yi-",
    )

    @classmethod
    def _is_non_chat_model(cls, name: str) -> bool:
        n = (name or "").lower()
        return any(h in n for h in cls._NON_CHAT_MODEL_HINTS)

    @classmethod
    def _chat_model_score(cls, name: str) -> int:
        n = (name or "").lower()
        if cls._is_non_chat_model(n):
            return -100
        score = 0
        for i, hint in enumerate(cls._CHAT_MODEL_HINTS):
            if hint in n:
                score += 80 - i
        if ":" in name:
            score += 8
        return score

    def _fetch_openai_compatible_models(
        self, base_url: str, timeout_sec: float = 3.0
    ) -> List[str]:
        """从本机 OpenAI 兼容 /v1/models 拉取模型 id 列表。"""
        from application.ai.local_llm_utils import LOCAL_LLM_PLACEHOLDER_API_KEY

        openai_base = self._openai_compatible_models_base(base_url)
        url = f"{openai_base}/models"
        try:
            with httpx.Client(timeout=timeout_sec, trust_env=False) as client:
                r = client.get(
                    url,
                    headers={"Authorization": f"Bearer {LOCAL_LLM_PLACEHOLDER_API_KEY}"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.debug("fetch local models failed %s: %s", url, e)
            return []
        items = data.get("data") or data.get("models") or []
        if not isinstance(items, list):
            return []
        out: List[str] = []
        seen: set[str] = set()
        for item in items:
            mid = ""
            if isinstance(item, dict):
                mid = (item.get("id") or item.get("name") or "").strip()
            elif isinstance(item, str):
                mid = item.strip()
            if mid and mid not in seen:
                seen.add(mid)
                out.append(mid)
        return out

    def _fetch_first_openai_compatible_model(
        self, base_url: str, timeout_sec: float = 3.0
    ) -> Optional[str]:
        picked = self._pick_best_local_model(
            [], "custom", base_url, manage_url=None, timeout_sec=timeout_sec
        )
        return picked or None

    @staticmethod
    def _manage_url_from_openai_base(base_url: str, service_id: str) -> Optional[str]:
        raw = (base_url or "").strip().rstrip("/")
        if service_id == "ollama":
            if raw.endswith("/v1"):
                return raw[:-3] or "http://127.0.0.1:11434"
            if ":11434" in raw:
                return raw.split("/v1")[0] or raw
            return "http://127.0.0.1:11434"
        return None

    def _fetch_ollama_running_model(
        self, manage_url: str, timeout_sec: float = 3.0
    ) -> Optional[str]:
        """Ollama 当前内存中正在服务的模型（/api/ps）。"""
        base = (manage_url or "").strip().rstrip("/")
        if not base:
            return None
        url = f"{base}/api/ps"
        try:
            with httpx.Client(timeout=timeout_sec, trust_env=False) as client:
                r = client.get(url)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.debug("ollama ps failed %s: %s", url, e)
            return None
        models = data.get("models") or []
        if not isinstance(models, list):
            return None
        for item in models:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or item.get("model") or "").strip()
            if name:
                return name
        return None

    def _pick_best_local_model(
        self,
        previews: List[str],
        service_id: str,
        base_url: str,
        manage_url: Optional[str] = None,
        timeout_sec: float = 3.0,
    ) -> str:
        """在探测列表与 /v1/models 中自动匹配最合适的聊天模型。"""
        candidates: List[str] = []
        seen: set[str] = set()

        def add(name: str, front: bool = False) -> None:
            n = (name or "").strip()
            if not n or n in seen:
                return
            seen.add(n)
            if front:
                candidates.insert(0, n)
            else:
                candidates.append(n)

        manage = (manage_url or "").strip() or self._manage_url_from_openai_base(
            base_url, service_id
        )
        if service_id == "ollama" and manage:
            running = self._fetch_ollama_running_model(manage, timeout_sec=timeout_sec)
            if running:
                add(running, front=True)

        for p in previews:
            add(p)

        for mid in self._fetch_openai_compatible_models(base_url, timeout_sec=timeout_sec):
            add(mid)

        if not candidates:
            return ""

        ranked = sorted(candidates, key=lambda n: self._chat_model_score(n), reverse=True)
        best = ranked[0]
        if self._chat_model_score(best) < 0:
            return candidates[0]
        return best

    @staticmethod
    def _discover_local_embedding_path() -> Tuple[str, bool, bool]:
        """
        自动解析本地嵌入模型目录。
        返回 (path, exists, auto_matched)。
        """
        from application.paths import PLOTPILOT_ROOT

        env_keys = ("EMBEDDING_MODEL_PATH", "LOCAL_EMBEDDING_MODEL_PATH")
        for key in env_keys:
            raw = (os.getenv(key) or "").strip()
            if not raw:
                continue
            p = Path(raw)
            if not p.is_absolute():
                p = (PLOTPILOT_ROOT / p).resolve()
            if p.is_dir() and any(p.iterdir()):
                return str(p), True, False

        models_root = (PLOTPILOT_ROOT / ".models").resolve()
        preferred = (
            "bge-small-zh-v1.5",
            "bge-m3",
            "bge-large-zh-v1.5",
            "multilingual-e5-small",
        )
        for name in preferred:
            cand = models_root / name
            if cand.is_dir() and any(cand.iterdir()):
                return str(cand), True, True

        if models_root.is_dir():
            for child in sorted(models_root.iterdir()):
                if child.is_dir() and any(child.iterdir()):
                    return str(child.resolve()), True, True

        fallback = models_root / "bge-small-zh-v1.5"
        return str(fallback.resolve()), fallback.is_dir() and any(fallback.iterdir()), True

    @staticmethod
    def _normalize_openai_v1_base(base_url: str) -> str:
        raw = (base_url or "").strip().rstrip("/")
        if not raw:
            return ""
        if "://" not in raw:
            raw = f"http://{raw}"
        if raw.endswith("/v1"):
            return raw
        if raw.endswith("/api"):
            return f"{raw}/v1"
        return f"{raw}/v1"

    def connect_local_llm_profile(
        self,
        service_id: str,
        model: Optional[str] = None,
        base_url_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将本机 LLM 写入 llm_profiles 并设为激活。base_url_override 可跳过自动探测。"""
        from application.ai.llm_control_service import LLMControlConfig, LLMControlService, LLMProfile
        from application.ai.local_llm_utils import LOCAL_LLM_PLACEHOLDER_API_KEY

        label = service_id
        previews: List[str] = []
        manage_url: Optional[str] = None

        if (base_url_override or "").strip():
            base_url = self._normalize_openai_v1_base(base_url_override)
            if not base_url:
                raise ValueError("Base URL 无效")
            preset = {
                "ollama": "Ollama",
                "lm_studio": "LM Studio",
                "localai": "LocalAI",
            }
            label = preset.get(service_id, service_id)
            manage_url = self._manage_url_from_openai_base(base_url, service_id)
        else:
            probe = self.probe_local_models()
            svc = next((s for s in probe["services"] if s.get("id") == service_id), None)
            if not svc:
                raise ValueError(f"未知服务: {service_id}")
            if svc.get("kind") != "llm":
                raise ValueError("仅支持连接 LLM 运行时（Ollama / LM Studio 等）")
            if not svc.get("reachable"):
                hint = (svc.get("detail") or "").strip()
                extra = f"（{hint}）" if hint else ""
                raise ValueError(
                    f"{svc.get('label', service_id)} 从 PlotPilot 后端不可达{extra}。"
                    "若浏览器能打开 Ollama，请在下方「手动填写地址」连接，或关闭系统 HTTP 代理。"
                )
            base_url = (svc.get("suggested_base_url") or "").strip()
            if not base_url:
                raise ValueError("缺少建议 Base URL")
            label = str(svc.get("label") or service_id)
            previews = list(svc.get("models_preview") or [])
            manage_url = svc.get("manage_url")

        model_name = (model or "").strip()
        if not model_name:
            model_name = self._pick_best_local_model(
                previews,
                service_id,
                base_url,
                manage_url=manage_url,
            )

        if not model_name:
            raise ValueError(
                f"无法从 {label} 获取模型名，请填写模型名。"
                "Ollama：ollama pull 后填如 qwen2.5:7b；LM Studio：先加载模型。"
            )

        control = LLMControlService()
        config = control.get_config()
        norm_base = base_url.rstrip("/")
        existing = next(
            (
                p
                for p in config.profiles
                if (p.base_url or "").rstrip("/") == norm_base
            ),
            None,
        )
        profile_id = existing.id if existing else f"local-{service_id}-{uuid.uuid4().hex[:8]}"
        profile = LLMProfile(
            id=profile_id,
            name=f"本地 · {label}",
            preset_key="custom-openai-compatible",
            protocol="openai",
            base_url=base_url,
            api_key=LOCAL_LLM_PLACEHOLDER_API_KEY,
            model=model_name,
            temperature=existing.temperature if existing else 0.7,
            max_tokens=existing.max_tokens if existing else 4096,
            timeout_seconds=existing.timeout_seconds if existing else 300,
            extra_headers=existing.extra_headers if existing else {},
            extra_query=existing.extra_query if existing else {},
            extra_body=existing.extra_body if existing else {},
            notes=f"本地模型连接（{service_id}）",
            use_legacy_chat_completions=existing.use_legacy_chat_completions if existing else True,
        )
        others = [p for p in config.profiles if p.id != profile_id]
        others.append(profile)
        saved = control.save_config(
            LLMControlConfig(
                version=config.version,
                active_profile_id=profile_id,
                endpoint_mode=config.endpoint_mode,
                profiles=others,
            )
        )
        runtime = control.get_runtime_summary(saved)
        return {
            "profile_id": profile_id,
            "service_id": service_id,
            "label": label,
            "base_url": base_url,
            "model": model_name,
            "runtime": runtime.model_dump(),
        }

    def auto_connect_local_llm(self) -> Dict[str, Any]:
        """探测本机 LLM 并自动写入激活档案；探测失败时尝试常见默认地址。"""
        from application.ai.llm_control_service import LLMControlService
        from application.ai.local_llm_utils import is_local_openai_compatible_base_url

        control = LLMControlService()
        runtime = control.get_runtime_summary()
        if (
            not runtime.using_mock
            and (runtime.base_url or "").strip()
            and is_local_openai_compatible_base_url(runtime.base_url or "")
        ):
            return {
                "connected": True,
                "skipped": True,
                "method": "already_active",
                "label": runtime.active_profile_name,
                "model": runtime.model,
                "base_url": runtime.base_url,
                "service_id": None,
                "profile_id": runtime.active_profile_id,
                "runtime": runtime.model_dump(),
            }

        probe = self.probe_local_models(timeout_sec=4.0)
        for sid in ("ollama", "lm_studio", "localai"):
            svc = next((s for s in probe["services"] if s.get("id") == sid), None)
            if not svc or not svc.get("reachable"):
                continue
            try:
                payload = self.connect_local_llm_profile(sid, None)
                rt = payload.get("runtime") or {}
                connected = not rt.get("using_mock", True)
                return {
                    **payload,
                    "connected": connected,
                    "skipped": False,
                    "method": "probe",
                    "services": probe["services"],
                }
            except ValueError as e:
                logger.info("auto_connect probe path failed %s: %s", sid, e)

        fallbacks: List[tuple[str, str]] = []
        for url in self._ollama_probe_urls():
            base = url.replace("/api/tags", "").rstrip("/") + "/v1"
            fallbacks.append(("ollama", base))
        fallbacks.extend(
            [
                ("lm_studio", "http://127.0.0.1:1234/v1"),
                ("lm_studio", "http://localhost:1234/v1"),
                ("localai", "http://127.0.0.1:8080/v1"),
            ]
        )
        seen_bases: set[str] = set()
        for sid, base in fallbacks:
            norm = base.rstrip("/")
            if norm in seen_bases:
                continue
            seen_bases.add(norm)
            model = self._pick_best_local_model([], sid, base, timeout_sec=5.0)
            if not model:
                continue
            try:
                payload = self.connect_local_llm_profile(
                    sid, model, base_url_override=base
                )
                rt = payload.get("runtime") or {}
                connected = not rt.get("using_mock", True)
                return {
                    **payload,
                    "connected": connected,
                    "skipped": False,
                    "method": "fallback",
                    "services": probe["services"],
                }
            except ValueError as e:
                logger.debug("auto_connect fallback %s %s: %s", sid, base, e)

        return {
            "connected": False,
            "skipped": False,
            "method": "none",
            "reason": "未能连接本机 LLM；请确认 Ollama/LM Studio 已启动且已加载模型",
            "services": probe["services"],
            "summary": probe.get("summary"),
        }

    def _probe_http(
        self,
        urls: List[str],
        timeout_sec: float = 3.0,
    ) -> tuple[bool, str, Optional[dict]]:
        """探测 URL 列表；trust_env=False 避免 Windows 系统代理劫持 localhost。"""
        last_err = ""
        with httpx.Client(timeout=timeout_sec, trust_env=False) as client:
            for url in urls:
                try:
                    r = client.get(url)
                    if r.status_code < 500:
                        detail = f"{url} → HTTP {r.status_code}"
                        data = None
                        if "application/json" in (r.headers.get("content-type") or ""):
                            try:
                                data = r.json()
                            except Exception:
                                data = None
                        return True, detail, data
                    last_err = f"{url} → HTTP {r.status_code}"
                except Exception as e:
                    last_err = f"{url} → {e}"
        return False, last_err[:240], None

    @staticmethod
    def _ollama_probe_urls() -> List[str]:
        urls: List[str] = []
        raw = (os.getenv("OLLAMA_HOST") or "").strip()
        if raw:
            base = raw if "://" in raw else f"http://{raw}"
            base = base.rstrip("/")
            urls.append(f"{base}/api/tags")
            if not base.endswith("/api"):
                urls.append(f"{base}/api/tags")
        for host in ("127.0.0.1", "localhost"):
            urls.append(f"http://{host}:11434/api/tags")
        seen: set[str] = set()
        out: List[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    @staticmethod
    def _plotpilot_api_probe_urls() -> List[str]:
        ports: List[int] = []
        for raw in (os.getenv("PORT"), "8010", "8005"):
            if raw and str(raw).strip().isdigit():
                p = int(str(raw).strip())
                if p not in ports:
                    ports.append(p)
        urls: List[str] = []
        for port in ports:
            for host in ("127.0.0.1", "localhost"):
                urls.append(f"http://{host}:{port}/api/stats/global")
        return urls or ["http://127.0.0.1:8010/api/stats/global"]

    def _parse_llm_models_from_json(
        self, data: Optional[dict], service_id: str
    ) -> List[str]:
        if not data:
            return []
        models_preview: List[str] = []
        items = data.get("data") or data.get("models") or []
        if isinstance(items, list):
            for item in items[:8]:
                if isinstance(item, dict):
                    mid = (
                        item.get("id")
                        or item.get("model")
                        or item.get("name")
                        or ""
                    )
                    if mid:
                        models_preview.append(str(mid).strip())
                elif isinstance(item, str) and item.strip():
                    models_preview.append(item.strip())
        if not models_preview and service_id == "ollama":
            for m in (data.get("models") or [])[:8]:
                if isinstance(m, dict):
                    mid = (m.get("model") or m.get("name") or "").strip()
                    if mid:
                        models_preview.append(mid)
        return models_preview

    def probe_local_models(self, timeout_sec: float = 3.0) -> Dict[str, Any]:
        """探测本机常见 LLM / 嵌入服务是否可达（由 PlotPilot 后端进程发起）。"""
        from application.paths import PLOTPILOT_ROOT

        llm_targets = [
            {
                "id": "ollama",
                "label": "Ollama",
                "probe_urls": self._ollama_probe_urls(),
                "kind": "llm",
                "suggested_base_url": "http://127.0.0.1:11434/v1",
                "manage_url": "http://127.0.0.1:11434",
            },
            {
                "id": "lm_studio",
                "label": "LM Studio",
                "probe_urls": [
                    "http://127.0.0.1:1234/v1/models",
                    "http://localhost:1234/v1/models",
                ],
                "kind": "llm",
                "suggested_base_url": "http://127.0.0.1:1234/v1",
                "manage_url": "http://127.0.0.1:1234",
            },
            {
                "id": "localai",
                "label": "LocalAI",
                "probe_urls": [
                    "http://127.0.0.1:8080/v1/models",
                    "http://localhost:8080/v1/models",
                ],
                "kind": "llm",
                "suggested_base_url": "http://127.0.0.1:8080/v1",
                "manage_url": "http://127.0.0.1:8080",
            },
        ]

        services: List[Dict[str, Any]] = []
        pp_ok, pp_detail, _ = self._probe_http(
            self._plotpilot_api_probe_urls(), timeout_sec
        )
        services.append(
            {
                "id": "plotpilot_api",
                "label": "PlotPilot 后端",
                "kind": "api",
                "reachable": pp_ok,
                "detail": pp_detail,
                "models_preview": [],
            }
        )

        for t in llm_targets:
            ok, detail, data = self._probe_http(t["probe_urls"], timeout_sec)
            models_preview = self._parse_llm_models_from_json(data, t["id"]) if ok else []
            if ok and t["id"] == "ollama" and detail.startswith("http"):
                hit = detail.split(" → ")[0].replace("/api/tags", "")
                suggested = f"{hit.rstrip('/')}/v1"
                manage = hit.rstrip("/")
            else:
                suggested = t["suggested_base_url"]
                manage = t.get("manage_url")
            suggested_model = ""
            if ok:
                suggested_model = self._pick_best_local_model(
                    models_preview,
                    t["id"],
                    suggested,
                    manage_url=manage,
                    timeout_sec=timeout_sec,
                )
            services.append(
                {
                    "id": t["id"],
                    "label": t["label"],
                    "kind": t["kind"],
                    "reachable": ok,
                    "detail": detail,
                    "models_preview": models_preview,
                    "suggested_model": suggested_model,
                    "suggested_base_url": suggested,
                    "manage_url": manage,
                }
            )

        emb_path_str, emb_exists, emb_auto = self._discover_local_embedding_path()
        emb_path = Path(emb_path_str)

        ext_ok = False
        ext_detail = ""
        try:
            import torch  # noqa: F401
            import sentence_transformers  # noqa: F401

            ext_ok = True
            ext_detail = "sentence-transformers / torch 已安装"
        except ImportError as e:
            ext_detail = str(e)[:160]

        embedding = {
            "mode_env": os.getenv("EMBEDDING_SERVICE", "openai"),
            "model_path": str(emb_path),
            "suggested_model_path": str(emb_path),
            "model_path_auto_matched": emb_auto,
            "model_path_exists": emb_exists,
            "extensions_installed": ext_ok,
            "extensions_detail": ext_detail,
            "ready": ext_ok and emb_exists,
        }

        llm_env = {
            "ark_api_key_set": bool((os.getenv("ARK_API_KEY") or "").strip()),
            "anthropic_key_set": bool(
                (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or "").strip()
            ),
        }

        any_llm = any(s["reachable"] for s in services if s.get("kind") == "llm")
        plot_api = next((s for s in services if s["id"] == "plotpilot_api"), None)
        return {
            "services": services,
            "embedding": embedding,
            "llm_env": llm_env,
            "summary": {
                "plotpilot_backend": bool(plot_api and plot_api.get("reachable")),
                "local_llm_runtime": any_llm,
                "local_embedding_ready": embedding["ready"],
                "cloud_llm_configured": llm_env["ark_api_key_set"] or llm_env["anthropic_key_set"],
            },
        }

    def _prune_scan_cache(self) -> None:
        now = time.time()
        stale = [k for k, v in _scan_cache.items() if now - v.scanned_at > SCAN_TTL_SEC]
        for k in stale:
            _scan_cache.pop(k, None)

    def _scan_manuscript_folder(
        self, root: Path, depth: int, warnings: List[str]
    ) -> Optional[ScanCandidate]:
        files = self._collect_chapter_files(root, depth, warnings)
        if not files:
            return None
        files.sort(key=lambda f: f.number)
        total_words = 0
        preview: List[Dict[str, Any]] = []
        for f in files[:12]:
            try:
                content = self._load_file_content(Path(f.path))
                w = _word_count(content)
            except Exception:
                w = 0
            total_words += w
            preview.append(
                {
                    "number": f.number,
                    "title": f.title,
                    "path": f.path,
                    "words": w,
                }
            )
        if len(files) > 12:
            for f in files[12:]:
                try:
                    total_words += _word_count(self._load_file_content(Path(f.path)))
                except Exception:
                    pass

        confidence = 0.5
        if len(files) >= 3:
            confidence += 0.25
        if any(re.search(r"第\s*\d+\s*章", f.title, re.I) for f in files[:5]):
            confidence += 0.15
        confidence = min(confidence, 0.98)

        return ScanCandidate(
            kind="manuscript_folder",
            path=str(root),
            title_guess=root.name,
            chapter_files=len(files),
            total_words_estimate=total_words,
            confidence=round(confidence, 2),
            chapter_preview=preview,
        )

    def _detect_plotpilot_db(self, root: Path) -> Optional[ScanCandidate]:
        candidates = [root / "plotpilot.db", root / "aitext.db", root / "data" / "plotpilot.db"]
        data_dir = DATA_DIR.resolve()
        for db_path in candidates:
            if not db_path.is_file():
                continue
            try:
                if db_path.resolve() == Path(get_db_path()).resolve():
                    extra = {"note": "当前运行中的数据库，无需重复导入"}
                else:
                    extra = {"note": "检测到独立数据库文件，当前版本请使用「书稿目录导入」"}
            except Exception:
                extra = {}
            return ScanCandidate(
                kind="plotpilot_data_dir",
                path=str(root),
                title_guess=root.name,
                chapter_files=0,
                total_words_estimate=0,
                confidence=0.7,
                extra={"db_path": str(db_path), **extra},
            )
        if root.resolve() == data_dir:
            db = data_dir / "plotpilot.db"
            if db.is_file():
                return ScanCandidate(
                    kind="plotpilot_data_dir",
                    path=str(data_dir),
                    title_guess="PlotPilot 数据目录",
                    chapter_files=0,
                    total_words_estimate=0,
                    confidence=0.85,
                    extra={"db_path": str(db), "note": "开发环境默认 data 目录"},
                )
        return None

    def _collect_chapter_files(
        self, root: Path, depth: int, warnings: List[str]
    ) -> List[ScannedChapterFile]:
        found: List[ScannedChapterFile] = []
        count = 0

        def walk(dir_path: Path, level: int) -> None:
            nonlocal count
            if level > depth:
                return
            try:
                entries = sorted(dir_path.iterdir(), key=lambda p: p.name.lower())
            except OSError as e:
                warnings.append(f"无法读取目录 {dir_path}: {e}")
                return
            for entry in entries:
                if count >= MAX_FILES:
                    warnings.append(f"已达文件上限 {MAX_FILES}，其余已忽略")
                    return
                if entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    walk(entry, level + 1)
                    continue
                suffix = entry.suffix.lower()
                if suffix not in TEXT_SUFFIXES and suffix != DOCX_SUFFIX:
                    continue
                try:
                    if entry.stat().st_size > MAX_FILE_BYTES:
                        warnings.append(f"跳过大文件: {entry}")
                        continue
                except OSError:
                    continue
                count += 1
                num = _guess_chapter_number(entry.name, len(found) + 1)
                title = entry.stem
                found.append(
                    ScannedChapterFile(
                        path=str(entry),
                        number=num,
                        title=title,
                        words=0,
                    )
                )

        walk(root, 0)
        return found

    def _load_file_content(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES:
            return _read_text_file(path)
        if suffix == DOCX_SUFFIX:
            return _read_docx(path)
        raise ValueError(f"不支持的文件类型: {path.suffix}")
