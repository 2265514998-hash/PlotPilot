"""DAG 核心领域模型 — 领域层零外部依赖

仅包含 Repository 接口和基础设施层需要的核心数据结构。
应用层的扩展模型（NodeRegistry 校验、默认 DAG 等）保留在
``application.engine.dag.models`` 并从这里 re-export 基础类型。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


# ─── 枚举 ───


class NodeCategory(str, Enum):
    """节点分类"""
    CONTEXT = "context"
    EXECUTION = "execution"
    VALIDATION = "validation"
    GATEWAY = "gateway"
    WORLD = "world"
    REVIEW = "review"
    ANTI_AI = "anti-ai"
    PLANNING = "planning"
    PROP = "prop"


class NodeStatus(str, Enum):
    """节点运行时状态"""
    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    BYPASSED = "bypassed"
    DISABLED = "disabled"
    COMPLETED = "completed"


class EdgeCondition(str, Enum):
    """边条件表达式"""
    ON_SUCCESS = "on_success"
    ON_ERROR = "on_error"
    ON_DRIFT_ALERT = "on_drift_alert"
    ON_NO_DRIFT = "on_no_drift"
    ON_BREAKER_OPEN = "on_breaker_open"
    ON_BREAKER_CLOSED = "on_breaker_closed"
    ON_REVIEW_APPROVED = "on_review_approved"
    ON_REVIEW_REJECTED = "on_review_rejected"
    ALWAYS = "always"


class PortDataType(str, Enum):
    """端口数据类型"""
    TEXT = "text"
    JSON = "json"
    SCORE = "score"
    BOOLEAN = "boolean"
    LIST = "list"
    PROMPT = "prompt"
    OBJECT = "object"


# ─── 端口 ───


class NodePort(BaseModel):
    """节点的输入/输出端口"""
    name: str
    data_type: PortDataType = PortDataType.TEXT
    required: bool = True
    default: Any = None
    description: str = ""


# ─── 节点配置 ───


class NodeConfig(BaseModel):
    """节点运行时配置（可被用户覆盖）"""
    prompt_template: Optional[str] = None
    prompt_variables: Dict[str, str] = Field(default_factory=dict)
    thresholds: Dict[str, float] = Field(default_factory=dict)
    model_override: Optional[str] = None
    max_retries: int = Field(default=1, ge=0, le=5)
    timeout_seconds: int = Field(default=60, ge=10, le=600)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=100, le=16000)


# ─── DAG 定义模型 ───


class NodeDefinition(BaseModel):
    """DAG 中的节点实例定义"""
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    type: str
    label: str = ""
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})
    enabled: bool = True
    config: NodeConfig = Field(default_factory=NodeConfig)

    # 注意：NodeRegistry 动态校验在 application 层模型中覆写
    # 领域层不做运行时注册表查询，保持零外部依赖


class EdgeDefinition(BaseModel):
    """DAG 中的边定义"""
    id: str = Field(pattern=r"^edge_[a-z0-9_]+$")
    source: str
    source_port: str = ""
    target: str
    target_port: str = ""
    condition: EdgeCondition = EdgeCondition.ALWAYS
    animated: bool = False


class DAGMetadata(BaseModel):
    """DAG 元数据"""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"


class DAGDefinition(BaseModel):
    """DAG 完整定义 — 前后端共享核心模型"""
    id: str
    name: str
    version: int = Field(default=1, ge=1)
    description: str = ""
    nodes: List[NodeDefinition] = Field(default_factory=list)
    edges: List[EdgeDefinition] = Field(default_factory=list)
    metadata: DAGMetadata = Field(default_factory=DAGMetadata)

    def fingerprint(self) -> str:
        """计算 DAG 结构指纹（用于缓存编译结果）"""
        data = {
            "nodes": [{"id": n.id, "type": n.type, "enabled": n.enabled} for n in sorted(self.nodes, key=lambda n: n.id)],
            "edges": [{"id": e.id, "source": e.source, "target": e.target, "condition": e.condition.value}
                      for e in sorted(self.edges, key=lambda e: e.id)],
        }
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_node(self, node_id: str) -> Optional[NodeDefinition]:
        """按 ID 查找节点"""
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_entry_nodes(self) -> List[NodeDefinition]:
        """获取入口节点（无入边的节点）"""
        targets = {e.target for e in self.edges}
        return [n for n in self.nodes if n.id not in targets and n.enabled]

    def get_successors(self, node_id: str) -> List[str]:
        """获取直接后继节点 ID"""
        return [e.target for e in self.edges if e.source == node_id]

    def get_predecessors(self, node_id: str) -> List[str]:
        """获取直接前驱节点 ID"""
        return [e.source for e in self.edges if e.target == node_id]


# ─── 节点执行结果 ───


class NodeResult(BaseModel):
    """节点执行结果"""
    outputs: Dict[str, Any] = Field(default_factory=dict)
    status: NodeStatus = NodeStatus.SUCCESS
    metrics: Dict[str, float] = Field(default_factory=dict)
    duration_ms: int = 0
    error: Optional[str] = None


# ─── 节点运行时状态 ───


class NodeRunState(BaseModel):
    """节点运行时状态（前端 SSE 更新用）"""
    node_id: str
    status: NodeStatus = NodeStatus.IDLE
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: int = 0
    outputs: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    error: Optional[str] = None
    progress: float = 0.0


# ─── DAG 运行结果 ───


class DAGRunResult(BaseModel):
    """DAG 一次运行的结果"""
    dag_run_id: str
    novel_id: str
    status: str = "completed"
    node_results: Dict[str, NodeResult] = Field(default_factory=dict)
    total_duration_ms: int = 0
    error_count: int = 0
    started_at: str = ""
    completed_at: str = ""


# ─── LangGraph 全局状态 ───


class NovelWorkflowState(BaseModel):
    """整个 DAG 运行期间的全局状态 — 映射到 LangGraph StateGraph"""
    novel_id: str = ""
    chapter_number: int = 0
    dag_run_id: str = ""

    # Context 节点输出
    world_rules: str = ""
    fact_lock: str = ""
    foreshadowing_block: str = ""
    voice_block: str = ""
    debt_due_block: str = ""

    # Execution 节点输出
    outline: str = ""
    chapter_plan_json: Optional[Dict[str, Any]] = None
    beats: List[Dict[str, Any]] = Field(default_factory=list)
    content: str = ""
    word_count: int = 0

    # Validation 节点输出
    drift_score: float = 0.0
    drift_alert: bool = False
    tension_composite: float = 0.0
    tension_dimensions: Dict[str, float] = Field(default_factory=dict)
    anti_ai_severity: float = 0.0
    anti_ai_hits: List[Dict[str, Any]] = Field(default_factory=list)
    narrative_summary: str = ""
    narrative_events: List[Dict[str, Any]] = Field(default_factory=list)
    narrative_triples: List[Dict[str, Any]] = Field(default_factory=list)
    foreshadow_recovered: int = 0
    foreshadow_pending: int = 0
    inferred_triples: List[Dict[str, Any]] = Field(default_factory=list)

    # Gateway 输出
    breaker_status: str = "closed"
    review_approved: bool = False
    retry_count: int = 0

    # DAG 配置（用户覆盖）
    node_configs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    disabled_nodes: List[str] = Field(default_factory=list)

    # 内部状态
    current_node: str = ""
    current_stage: str = ""
    completed_nodes: Set[str] = Field(default_factory=set, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


# ─── SSE 事件模型 ───


class NodeEvent(BaseModel):
    """SSE 节点事件"""
    type: str
    novel_id: str
    node_id: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: Optional[NodeStatus] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    error: Optional[str] = None
    source_node: str = ""
    target_node: str = ""
    port: str = ""
    data_type: str = ""
    data_size: int = 0
