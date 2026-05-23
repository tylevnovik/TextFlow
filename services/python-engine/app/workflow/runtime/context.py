from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ...defaults import empty_result_bundle, utc_now_iso
from .previews import _compact_runtime_preview_scalar, _compact_runtime_preview_row, _preview_runtime_outputs
from .support import (
    dispatch_progress_callback,
    update_log,
)

@dataclass
class NodeExecutionState:
    outputs: dict[str, Any]
    output_hashes: dict[str, str]
    cache_hit: bool
    cache_key: str | None = None
    cache_path: str | None = None


@dataclass
class PreparedNodeExecution:
    node: dict[str, Any]
    node_index: int
    node_id: str
    node_type: str
    definition: dict[str, Any]
    executor: Any
    input_payload: dict[str, Any]
    cache_key: str | None
    cached: tuple[dict[str, Any], dict[str, str], str] | None


@dataclass
class ExecutedNodeResult:
    prepared: PreparedNodeExecution
    state: NodeExecutionState
    started_at: str
    start_clock: float
    error: BaseException | None = None


def _copy_corpus_rows(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) if isinstance(item, dict) else item for item in corpus]


def _truncate_runtime_text(value: Any, limit: int = 72) -> str:
    text = str(value or "").strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _sample_runtime_row(row: dict[str, Any]) -> str:
    candidate_keys = (
        "term",
        "keyword",
        "topic_label",
        "institution",
        "title",
        "doc_id",
        "source_term",
        "target_term",
        "term_a",
        "term_b",
        "year",
        "action",
    )
    parts = [
        _truncate_runtime_text(row.get(key))
        for key in candidate_keys
        if row.get(key) not in (None, "")
    ]
    return " · ".join(parts[:2])


def _summarize_runtime_value(value: Any) -> tuple[str, list[str]]:
    if isinstance(value, list):
        if not value:
            return "0 项", []
        if all(isinstance(item, dict) for item in value):
            samples = [
                _sample_runtime_row(item)
                for item in value[:3]
                if isinstance(item, dict) and _sample_runtime_row(item)
            ]
            return f"{len(value)} 条记录", samples
        samples = [_truncate_runtime_text(item) for item in value[:3] if str(item).strip()]
        return f"{len(value)} 项", samples
    if isinstance(value, dict):
        keys = [str(key) for key in list(value.keys())[:3]]
        return f"{len(value)} 个键", keys
    if isinstance(value, str):
        return f"{len(value)} 字", [_truncate_runtime_text(value)]
    if value is None:
        return "空结果", []
    return (_truncate_runtime_text(value), [])


def _summarize_runtime_outputs(outputs: dict[str, Any]) -> tuple[str, list[str]]:
    if not outputs:
        return "无输出", []
    summaries: list[str] = []
    samples: list[str] = []
    for port_id, value in outputs.items():
        summary, port_samples = _summarize_runtime_value(value)
        summaries.append(f"{port_id}：{summary}")
        samples.extend(
            f"{port_id} · {_truncate_runtime_text(sample)}"
            for sample in port_samples[:2]
            if str(sample).strip()
        )
    return "；".join(summaries[:3]), samples[:5]


class WorkflowExecutionContext:
    def __init__(
        self,
        *,
        project_dir: Path,
        manifest: dict[str, Any],
        workflow_definition: dict[str, Any],
        runtime_profile: dict[str, Any],
        full_corpus: list[dict[str, Any]],
        logs: list[dict[str, Any]],
        warnings: list[str],
        errors: list[str],
        run_id: str,
        progress_callback: Any = None,
        total_nodes: int = 1,
        audit_enabled: bool = True,
    ) -> None:
        self.project_dir = project_dir
        self.manifest = manifest
        self.workflow_definition = workflow_definition
        self.runtime_profile = runtime_profile
        self.full_corpus = full_corpus
        self.logs = logs
        self.warnings = warnings
        self.errors = errors
        self.run_id = run_id
        self.progress_callback = progress_callback
        self.total_nodes = max(total_nodes, 1)
        self.audit_enabled = audit_enabled
        self.current_node_index = 1
        self.current_node_id: str | None = None
        self.last_completed_node_id: str | None = None
        self.shared: dict[str, Any] = {}
        self.result_bundle = empty_result_bundle()
        self.node_runs: list[dict[str, Any]] = []
        self.node_runtime_states: dict[str, dict[str, Any]] = {}
        self._node_started_clocks: dict[str, float] = {}
        self._active_node_ids: set[str] = set()
        self._dirty_node_ids: set[str] = set()
        self._lock = threading.RLock()
        self.workflow_id = str(workflow_definition.get("workflow_id") or "")
        self.workflow_name = str(workflow_definition.get("name") or manifest.get("name") or "当前工作流")
        self.run_started_at = utc_now_iso()
        self.run_started_clock = perf_counter()
        self._last_runtime_emit_at = 0.0
        self._full_corpus_lookup = {
            str(item.get("doc_id") or item.get("id") or ""): item
            for item in self.full_corpus
            if isinstance(item, dict)
        }

    def log(self, node: dict[str, Any], message: str, level: str = "info") -> None:
        definition_step = str(((node.get("runtime_meta") or {}).get("step_id")) or "system")
        step = definition_step if definition_step in {"cleaning", "normalization", "tokenization", "dictionary_application", "filtering", "analysis", "export", "ingestion"} else "system"
        with self._lock:
            update_log(self.logs, step, message, level)

    def warning(self, message: str, node: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.warnings.append(message)
        self.log(node or {}, message, "warning")

    def add_audits(self, rows: list[dict[str, Any]]) -> None:
        if not self.audit_enabled or not rows:
            return
        with self._lock:
            self.result_bundle["audit_table"] = [*self.result_bundle["audit_table"], *rows]

    def get_shared_value(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.shared.get(key, default)

    def set_shared_value(self, key: str, value: Any) -> Any:
        with self._lock:
            self.shared[key] = value
        return value

    def get_shared_cache_value(self, bucket: str, cache_key: Any) -> Any:
        with self._lock:
            cache = self.shared.get(bucket)
            if not isinstance(cache, dict):
                return None
            return cache.get(cache_key)

    def set_shared_cache_value(self, bucket: str, cache_key: Any, value: Any) -> Any:
        with self._lock:
            cache = self.shared.get(bucket)
            if not isinstance(cache, dict):
                cache = {}
                self.shared[bucket] = cache
            cache[cache_key] = value
        return value

    def graph_progress(self) -> float:
        with self._lock:
            aggregate_fraction = sum(
                min(max(float(state.get("progress") or 0.0), 0.0), 1.0)
                for state in self.node_runtime_states.values()
            )
        return min(0.9, 0.08 + aggregate_fraction / self.total_nodes * 0.78)

    def completed_node_count(self) -> int:
        with self._lock:
            return sum(
                1
                for state in self.node_runtime_states.values()
                if str(state.get("status") or "") in {"completed", "cached", "failed", "skipped"}
            )

    def runtime_detail(
        self,
        *,
        stage: str,
        detail: str | None = None,
        full_node_state_sync: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            current_state = self.node_runtime_states.get(self.current_node_id or "") if self.current_node_id else None
            completed_nodes = sum(
                1
                for state in self.node_runtime_states.values()
                if str(state.get("status") or "") in {"completed", "cached", "failed", "skipped"}
            )
            if full_node_state_sync:
                node_states = deepcopy(self.node_runtime_states)
                node_state_delta = deepcopy(self.node_runtime_states)
            else:
                dirty_node_ids = set(self._dirty_node_ids)
                node_state_delta = {
                    node_id: deepcopy(self.node_runtime_states[node_id])
                    for node_id in dirty_node_ids
                    if node_id in self.node_runtime_states
                }
                node_states = {}
            self._dirty_node_ids.clear()
            current_node_id = self.current_node_id
            last_completed_node_id = self.last_completed_node_id
        return {
            "kind": "workflow_run",
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "stage": stage,
            "total_nodes": self.total_nodes,
            "completed_nodes": completed_nodes,
            "current_node_id": current_node_id,
            "current_node_label": current_state.get("label") if isinstance(current_state, dict) else None,
            "current_node_index": current_state.get("node_index") if isinstance(current_state, dict) else None,
            "last_completed_node_id": last_completed_node_id,
            "elapsed_ms": round((perf_counter() - self.run_started_clock) * 1000, 3),
            "detail": detail,
            "node_states": node_states,
            "node_state_delta": node_state_delta,
            "full_node_state_sync": full_node_state_sync,
        }

    def emit_runtime_progress(
        self,
        progress: float,
        message: str,
        *,
        stage: str,
        detail: str | None = None,
        force: bool = False,
        full_node_state_sync: bool = False,
    ) -> None:
        if self.progress_callback is None:
            return

        with self._lock:
            now = perf_counter()
            if not force and now - self._last_runtime_emit_at < 0.2:
                return
            self._last_runtime_emit_at = now
            detail_payload = self.runtime_detail(
                stage=stage,
                detail=detail or message,
                full_node_state_sync=True,
            )
        dispatch_progress_callback(
            self.progress_callback,
            progress,
            message,
            detail_payload,
        )

    def begin_node(self, node: dict[str, Any], node_index: int) -> tuple[str, str]:
        node_id = str(node.get("node_id") or "")
        label = str(node.get("label") or node.get("node_type") or "节点")
        started_at = utc_now_iso()
        with self._lock:
            self.current_node_index = node_index
            self.current_node_id = node_id
            self._active_node_ids.add(node_id)
            self.node_runtime_states[node_id] = {
                "node_id": node_id,
                "node_type": str(node.get("node_type") or ""),
                "label": label,
                "status": "running",
                "node_index": node_index,
                "total_nodes": self.total_nodes,
                "progress": 0.0,
                "started_at": started_at,
                "detail": f"正在执行节点：{label}",
            }
            self._node_started_clocks[node_id] = perf_counter()
            self._dirty_node_ids.add(node_id)
        self.emit_runtime_progress(
            self.graph_progress(),
            f"正在执行节点：{label}",
            stage="running",
            detail=f"正在执行节点：{label}",
            force=True,
        )
        return node_id, started_at

    def node_progress(self, node: dict[str, Any], fraction: float, detail: str | None = None) -> None:
        if self.progress_callback is None:
            return
        node_id = str(node.get("node_id") or "")
        bounded_fraction = min(max(float(fraction), 0.0), 0.995)
        label = str(node.get("label") or node.get("node_type") or "节点")
        next_detail = detail or f"正在执行节点：{label}"
        with self._lock:
            state = self.node_runtime_states.get(node_id)
            if state is None:
                self.current_node_index = max(self.current_node_index, 1)
                self.current_node_id = node_id
                self._active_node_ids.add(node_id)
                self.node_runtime_states[node_id] = {
                    "node_id": node_id,
                    "node_type": str(node.get("node_type") or ""),
                    "label": label,
                    "status": "running",
                    "node_index": self.current_node_index,
                    "total_nodes": self.total_nodes,
                    "progress": 0.0,
                    "started_at": utc_now_iso(),
                    "detail": next_detail,
                }
                self._node_started_clocks[node_id] = perf_counter()
                state = self.node_runtime_states[node_id]
            previous_fraction = float(state.get("progress") or 0.0)
            bounded_fraction = max(bounded_fraction, previous_fraction)
            previous_detail = str(state.get("detail") or "")
            started_clock = self._node_started_clocks.get(node_id)
            duration_ms = round((perf_counter() - float(started_clock)) * 1000, 3) if isinstance(started_clock, (int, float)) else None
            state.update({
                "status": "running",
                "progress": bounded_fraction,
                "detail": next_detail,
                "duration_ms": duration_ms,
            })
            self.current_node_id = node_id
            progress_changed = abs(bounded_fraction - previous_fraction) >= 0.08
            detail_changed = previous_detail != next_detail
            if progress_changed or detail_changed:
                self._dirty_node_ids.add(node_id)
        if progress_changed or detail_changed:
            self.emit_runtime_progress(
                self.graph_progress(),
                next_detail,
                stage="running",
                detail=next_detail,
            )

    def finish_node(
        self,
        node: dict[str, Any],
        *,
        node_index: int,
        state: NodeExecutionState,
        started_at: str,
        start_clock: float,
        status: str,
        error: str | None = None,
    ) -> None:
        node_id = str(node.get("node_id") or "")
        ended_at = utc_now_iso()
        duration_ms = round((perf_counter() - start_clock) * 1000, 3)
        output_summary, sample_outputs = _summarize_runtime_outputs(state.outputs)
        output_previews = _preview_runtime_outputs(state.outputs)
        with self._lock:
            runtime_state = self.node_runtime_states.get(node_id) or {
                "node_id": node_id,
                "node_type": str(node.get("node_type") or ""),
                "label": str(node.get("label") or node.get("node_type") or "节点"),
                "node_index": node_index,
                "total_nodes": self.total_nodes,
            }
            runtime_state.update({
                "status": status,
                "progress": 1.0,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "cache_hit": bool(state.cache_hit),
                "cache_key": state.cache_key,
                "cache_path": state.cache_path,
                "output_ports": list(state.outputs.keys()),
                "output_summary": output_summary,
                "sample_outputs": sample_outputs,
                "output_previews": output_previews,
                "detail": output_summary,
                "error": error,
            })
            self.node_runtime_states[node_id] = runtime_state
            self._node_started_clocks.pop(node_id, None)
            self._active_node_ids.discard(node_id)
            self._dirty_node_ids.add(node_id)
            self.last_completed_node_id = node_id
            if self.current_node_id == node_id:
                if self._active_node_ids:
                    next_current_id = min(
                        self._active_node_ids,
                        key=lambda item: int((self.node_runtime_states.get(item) or {}).get("node_index") or 0),
                    )
                    self.current_node_id = next_current_id
                    self.current_node_index = int((self.node_runtime_states.get(next_current_id) or {}).get("node_index") or 1)
                else:
                    self.current_node_id = None
        self.emit_runtime_progress(
            self.graph_progress(),
            f"节点 {runtime_state['label']} 已{'命中缓存' if state.cache_hit else '执行完成'}",
            stage="running",
            detail=output_summary or f"节点 {runtime_state['label']} 已完成",
            force=True,
        )

    def sync_corpus(self, corpus_rows: Any) -> None:
        if not isinstance(corpus_rows, list):
            return
        with self._lock:
            for item in corpus_rows:
                if not isinstance(item, dict):
                    continue
                doc_id = str(item.get("doc_id") or item.get("id") or "")
                if not doc_id:
                    continue
                existing = self._full_corpus_lookup.get(doc_id)
                if existing is None:
                    self.full_corpus.append(item)
                    self._full_corpus_lookup[doc_id] = item
                    continue
                existing.clear()
                existing.update(item)
