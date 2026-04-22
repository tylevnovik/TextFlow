from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from .defaults import (
    compile_pipeline_from_workflow,
    empty_result_bundle,
    normalize_workflow_edges,
    utc_now_iso,
    workflow_active_node_ids_from_sinks,
    workflow_reachable_node_ids,
)
from .node_registry import NodeRegistry, build_node_registry
from .reporting import write_run_outputs

LEGACY_BRIDGE_NODE_TYPES = {"analyze_corpus", "export_results"}
UTILITY_NODE_TYPES = {"note", "group"}
CORPUS_PORT_TYPES = {
    "CorpusTable",
    "ProjectCorpus",
    "ScopedCorpus",
    "CleanCorpus",
    "NormalizedCorpus",
    "TokenCorpus",
    "FilteredTokenCorpus",
}


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return str(value)


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(_json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def _hash_port_value(port_type: str, value: Any) -> str:
    if port_type in CORPUS_PORT_TYPES and isinstance(value, list):
        normalized_rows: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            base = {
                "doc_id": item.get("doc_id"),
                "raw_hash": item.get("raw_hash"),
                "title": item.get("title"),
                "year": item.get("year"),
                "source": item.get("source"),
                "institution": item.get("institution"),
                "category_or_tag": item.get("category_or_tag"),
            }
            if port_type in {"CorpusTable", "ProjectCorpus", "ScopedCorpus"}:
                base["raw_text"] = item.get("raw_text")
            if port_type == "CleanCorpus":
                base["clean_text"] = item.get("clean_text")
            if port_type == "NormalizedCorpus":
                base["normalized_text"] = item.get("normalized_text")
            if port_type == "TokenCorpus":
                base["tokens"] = item.get("tokens")
                base["phrase_hits"] = item.get("phrase_hits")
            if port_type == "FilteredTokenCorpus":
                base["filtered_tokens"] = item.get("filtered_tokens")
            normalized_rows.append(base)
        return _stable_hash(normalized_rows)
    return _stable_hash(value)


def _cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.json"


def _legacy_cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.json.gz"


def _write_cache_payload(project_dir: Path, node_id: str, cache_key: str, outputs: dict[str, Any], output_hashes: dict[str, str]) -> str:
    cache_path = _cache_payload_path(project_dir, node_id, cache_key)
    payload = {
        "node_id": node_id,
        "cache_key": cache_key,
        "created_at": utc_now_iso(),
        "outputs": _json_ready(outputs),
        "output_hashes": output_hashes,
    }
    _write_json_file(cache_path, payload)
    return str(cache_path)


def _read_cache_payload(project_dir: Path, node_id: str, cache_key: str) -> tuple[dict[str, Any], dict[str, str], str] | None:
    cache_path = _cache_payload_path(project_dir, node_id, cache_key)
    if cache_path.exists():
        payload = _read_json_file(cache_path)
    else:
        legacy_cache_path = _legacy_cache_payload_path(project_dir, node_id, cache_key)
        if not legacy_cache_path.exists():
            return None
        with gzip.open(legacy_cache_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        cache_path = legacy_cache_path
    outputs = payload.get("outputs") if isinstance(payload, dict) else None
    output_hashes = payload.get("output_hashes") if isinstance(payload, dict) else None
    if not isinstance(outputs, dict) or not isinstance(output_hashes, dict):
        return None
    return outputs, {str(key): str(value) for key, value in output_hashes.items()}, str(cache_path)


def _node_cache_key(
    manifest: dict[str, Any],
    workflow_definition: dict[str, Any],
    node: dict[str, Any],
    executor_id: str,
    input_hashes: dict[str, Any],
) -> str:
    payload = {
        "project_id": manifest.get("id"),
        "workflow_id": workflow_definition.get("workflow_id"),
        "workflow_hash": manifest.get("pipeline", {}).get("workflow_hash"),
        "dictionary_version": ((manifest.get("dictionary_set") or {}).get("version")),
        "node_id": node.get("node_id"),
        "node_type": node.get("node_type"),
        "node_impl_version": ((node.get("runtime_meta") or {}).get("node_impl_version")),
        "executor_id": executor_id,
        "config": node.get("config") or {},
        "inputs": input_hashes,
    }
    return _stable_hash(payload)


def _artifact_step_for_node(definition: dict[str, Any]) -> str:
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    step_id = str(runtime.get("step_id") or "")
    if step_id in {"scope", "resource", "merge"}:
        return "ingestion"
    if step_id == "sink":
        return "export"
    if step_id == "utility":
        return "ingestion"
    return step_id or "analysis"


def supports_native_execution(workflow_definition: dict[str, Any] | None, registry: NodeRegistry | None = None) -> bool:
    if not isinstance(workflow_definition, dict):
        return False
    nodes = workflow_definition.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return False
    registry = registry or build_node_registry()
    definition_map = registry.definitions_by_type
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("node_type") or "")
        if not node_type or node_type in UTILITY_NODE_TYPES:
            continue
        if node_type in LEGACY_BRIDGE_NODE_TYPES:
            return False
        definition = definition_map.get(node_type)
        if not isinstance(definition, dict):
            return False
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        if executor_id not in registry.executors:
            return False
    return True


def _select_active_workflow(manifest: dict[str, Any]) -> dict[str, Any]:
    workflow_definitions = [
        workflow
        for workflow in manifest.get("workflow_definitions", [])
        if isinstance(workflow, dict) and workflow.get("workflow_id")
    ]
    active_workflow_id = str(manifest.get("active_workflow_id") or "")
    workflow_lookup = {str(workflow["workflow_id"]): workflow for workflow in workflow_definitions}
    return workflow_lookup.get(active_workflow_id) or (workflow_definitions[0] if workflow_definitions else {})


def _topological_active_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_lookup = {str(node.get("node_id") or ""): node for node in nodes}
    indegree = {node_id: 0 for node_id in node_lookup}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        from_node_id = str(edge.get("from_node") or "")
        to_node_id = str(edge.get("to_node") or "")
        if from_node_id not in node_lookup or to_node_id not in node_lookup:
            continue
        outgoing[from_node_id].append(to_node_id)
        indegree[to_node_id] += 1
    queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
    order: list[dict[str, Any]] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_lookup[node_id])
        for target_id in outgoing.get(node_id, []):
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                queue.append(target_id)
    if len(order) != len(node_lookup):
        raise ValueError("Workflow graph contains an unsupported cycle")
    return order


def _definition_output_ports(definition: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = definition.get("outputs")
    if not isinstance(outputs, list):
        return []
    return [output for output in outputs if isinstance(output, dict)]


def _definition_output_port(definition: dict[str, Any], port_id: str) -> dict[str, Any] | None:
    for output in _definition_output_ports(definition):
        if str(output.get("port_id") or "") == port_id:
            return output
    return None


def _result_key_for_output_port(definition: dict[str, Any], port_id: str) -> str | None:
    output_port = _definition_output_port(definition, port_id)
    if not isinstance(output_port, dict):
        return None
    result_key = str(output_port.get("result_bundle_key") or "").strip()
    return result_key or None


def _png_chart_ids_for_output_port(definition: dict[str, Any], port_id: str) -> set[str]:
    output_port = _definition_output_port(definition, port_id)
    if not isinstance(output_port, dict):
        return set()
    chart_ids = output_port.get("png_chart_ids")
    if not isinstance(chart_ids, list):
        return set()
    return {
        str(chart_id).strip()
        for chart_id in chart_ids
        if str(chart_id).strip()
    }


def _include_output_in_html_audit(definition: dict[str, Any], port_id: str) -> bool:
    output_port = _definition_output_port(definition, port_id)
    return bool(output_port and output_port.get("include_in_html_audit"))


def _result_bundle_bindings(definition: dict[str, Any]) -> list[tuple[str, str]]:
    bindings: list[tuple[str, str]] = []
    for output_port in _definition_output_ports(definition):
        port_id = str(output_port.get("port_id") or "")
        result_key = str(output_port.get("result_bundle_key") or "").strip()
        if port_id and result_key:
            bindings.append((port_id, result_key))
    return bindings


def _export_selection_from_active_graph(
    node_lookup: dict[str, dict[str, Any]],
    active_edges: list[dict[str, Any]],
    definitions_by_type: dict[str, dict[str, Any]],
) -> dict[str, set[str]]:
    selection = {
        "csv_tables": set(),
        "xlsx_tables": set(),
        "png_charts": set(),
        "html_result_keys": set(),
        "include_audit": set(),
    }
    for edge in active_edges:
        from_node = node_lookup.get(str(edge.get("from_node") or ""))
        to_node = node_lookup.get(str(edge.get("to_node") or ""))
        if not isinstance(from_node, dict) or not isinstance(to_node, dict):
            continue
        source_type = str(from_node.get("node_type") or "")
        sink_type = str(to_node.get("node_type") or "")
        source_port_id = str(edge.get("from_port") or "")
        source_definition = definitions_by_type.get(source_type) or {}
        result_key = _result_key_for_output_port(source_definition, source_port_id)
        if sink_type == "save_csv" and result_key:
            selection["csv_tables"].add(result_key)
        if sink_type == "save_xlsx" and result_key:
            selection["xlsx_tables"].add(result_key)
        if sink_type == "save_png":
            selection["png_charts"].update(_png_chart_ids_for_output_port(source_definition, source_port_id))
        if sink_type == "save_html_report":
            if result_key and not _include_output_in_html_audit(source_definition, source_port_id):
                selection["html_result_keys"].add(result_key)
            if _include_output_in_html_audit(source_definition, source_port_id):
                selection["include_audit"].add("audit")
    return selection


@dataclass
class NodeExecutionState:
    outputs: dict[str, Any]
    output_hashes: dict[str, str]
    cache_hit: bool
    cache_key: str | None = None
    cache_path: str | None = None


class WorkflowExecutionContext:
    def __init__(
        self,
        *,
        project_dir: Path,
        manifest: dict[str, Any],
        workflow_definition: dict[str, Any],
        compiled_pipeline: dict[str, Any],
        full_corpus: list[dict[str, Any]],
        logs: list[dict[str, Any]],
        warnings: list[str],
        errors: list[str],
        run_id: str,
        progress_callback: Any = None,
        total_nodes: int = 1,
    ) -> None:
        self.project_dir = project_dir
        self.manifest = manifest
        self.workflow_definition = workflow_definition
        self.compiled_pipeline = compiled_pipeline
        self.full_corpus = full_corpus
        self.logs = logs
        self.warnings = warnings
        self.errors = errors
        self.run_id = run_id
        self.progress_callback = progress_callback
        self.total_nodes = max(total_nodes, 1)
        self.current_node_index = 1
        self.current_node_id: str | None = None
        self.last_completed_node_id: str | None = None
        self.shared: dict[str, Any] = {}
        self.result_bundle = empty_result_bundle()
        self.node_runs: list[dict[str, Any]] = []
        self.node_runtime_states: dict[str, dict[str, Any]] = {}
        self._node_started_clocks: dict[str, float] = {}
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
        from .pipeline import update_log

        definition_step = str(((node.get("runtime_meta") or {}).get("step_id")) or "system")
        step = definition_step if definition_step in {"cleaning", "normalization", "tokenization", "dictionary_application", "filtering", "analysis", "export", "ingestion"} else "system"
        update_log(self.logs, step, message, level)

    def warning(self, message: str, node: dict[str, Any] | None = None) -> None:
        self.warnings.append(message)
        self.log(node or {}, message, "warning")

    def add_audits(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.result_bundle["audit_table"] = [*self.result_bundle["audit_table"], *rows]

    def graph_progress(self, fraction: float = 0.0) -> float:
        bounded_fraction = min(max(float(fraction), 0.0), 0.995)
        return min(0.9, 0.08 + ((self.current_node_index - 1) + bounded_fraction) / self.total_nodes * 0.78)

    def completed_node_count(self) -> int:
        return sum(
            1
            for state in self.node_runtime_states.values()
            if str(state.get("status") or "") in {"completed", "cached", "failed", "skipped"}
        )

    def runtime_detail(self, *, stage: str, detail: str | None = None) -> dict[str, Any]:
        current_state = self.node_runtime_states.get(self.current_node_id or "") if self.current_node_id else None
        return {
            "kind": "workflow_run",
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "stage": stage,
            "total_nodes": self.total_nodes,
            "completed_nodes": self.completed_node_count(),
            "current_node_id": self.current_node_id,
            "current_node_label": current_state.get("label") if isinstance(current_state, dict) else None,
            "current_node_index": current_state.get("node_index") if isinstance(current_state, dict) else None,
            "last_completed_node_id": self.last_completed_node_id,
            "elapsed_ms": round((perf_counter() - self.run_started_clock) * 1000, 3),
            "detail": detail,
            "node_states": deepcopy(self.node_runtime_states),
        }

    def emit_runtime_progress(
        self,
        progress: float,
        message: str,
        *,
        stage: str,
        detail: str | None = None,
        force: bool = False,
    ) -> None:
        if self.progress_callback is None:
            return
        now = perf_counter()
        if not force and now - self._last_runtime_emit_at < 0.12:
            return
        self._last_runtime_emit_at = now
        self.progress_callback(progress, message, self.runtime_detail(stage=stage, detail=detail or message))

    def begin_node(self, node: dict[str, Any], node_index: int) -> tuple[str, str]:
        node_id = str(node.get("node_id") or "")
        label = str(node.get("label") or node.get("node_type") or "节点")
        started_at = utc_now_iso()
        self.current_node_index = node_index
        self.current_node_id = node_id
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
        self.emit_runtime_progress(
            self.graph_progress(0.0),
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
        state = self.node_runtime_states.get(node_id)
        if state is None:
            _, _started_at = self.begin_node(node, self.current_node_index)
            state = self.node_runtime_states.get(node_id) or {}
        bounded_fraction = min(max(float(fraction), 0.0), 0.995)
        label = str(node.get("label") or node.get("node_type") or "节点")
        previous_fraction = float(state.get("progress") or 0.0)
        previous_detail = str(state.get("detail") or "")
        next_detail = detail or f"正在执行节点：{label}"
        started_clock = self._node_started_clocks.get(node_id)
        duration_ms = round((perf_counter() - float(started_clock)) * 1000, 3) if isinstance(started_clock, (int, float)) else None
        state.update({
            "status": "running",
            "progress": bounded_fraction,
            "detail": next_detail,
            "duration_ms": duration_ms,
        })
        progress_changed = abs(bounded_fraction - previous_fraction) >= 0.08
        detail_changed = previous_detail != next_detail
        if progress_changed or detail_changed:
            self.emit_runtime_progress(
                self.graph_progress(bounded_fraction),
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
            "detail": output_summary,
            "error": error,
        })
        self.node_runtime_states[node_id] = runtime_state
        self._node_started_clocks.pop(node_id, None)
        self.last_completed_node_id = node_id
        self.emit_runtime_progress(
            self.graph_progress(1.0),
            f"节点 {runtime_state['label']} 已{'命中缓存' if state.cache_hit else '执行完成'}",
            stage="running",
            detail=output_summary or f"节点 {runtime_state['label']} 已完成",
            force=True,
        )

    def sync_corpus(self, corpus_rows: Any) -> None:
        if not isinstance(corpus_rows, list):
            return
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


def run_project_workflow_native(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    progress_callback: Any = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    from .pipeline import build_run_record, describe_output_bundle, describe_run_scope, notify_progress, update_log

    full_corpus = _copy_corpus_rows(corpus)
    logs: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    registry = build_node_registry(manifest.get("pipeline"))
    active_workflow = _select_active_workflow(manifest)
    compiled_pipeline = compile_pipeline_from_workflow(active_workflow, manifest["pipeline"])
    compiled_pipeline["run_scope"] = deepcopy(compiled_pipeline.get("run_scope") or {})
    compiled_pipeline["recipe_id"] = compiled_pipeline.get("recipe_id", "standard_analysis")
    compiled_pipeline["output_bundle_id"] = compiled_pipeline.get("output_bundle_id", "full_report")
    manifest["pipeline"] = deepcopy(compiled_pipeline)

    active_nodes = [
        node
        for node in active_workflow.get("nodes", [])
        if isinstance(node, dict)
        and node.get("node_id")
        and str(node.get("node_type") or "") not in UTILITY_NODE_TYPES
        and not bool((node.get("ui_state") or {}).get("bypassed"))
    ]
    normalized_edges = normalize_workflow_edges(active_workflow, active_nodes)
    reachable_node_ids = workflow_reachable_node_ids(active_nodes, normalized_edges)
    active_node_ids = workflow_active_node_ids_from_sinks(active_nodes, normalized_edges, reachable_node_ids) or set(reachable_node_ids)
    selected_nodes = [node for node in active_nodes if str(node.get("node_id") or "") in active_node_ids]
    selected_node_lookup = {str(node["node_id"]): node for node in selected_nodes}
    definition_map = registry.definitions_by_type
    active_edges = [
        edge
        for edge in normalized_edges
        if str(edge.get("from_node") or "") in selected_node_lookup and str(edge.get("to_node") or "") in selected_node_lookup
    ]
    execution_order = _topological_active_nodes(selected_nodes, active_edges)
    export_selection = _export_selection_from_active_graph(selected_node_lookup, active_edges, definition_map)

    preliminary_scope = describe_run_scope(compiled_pipeline["run_scope"], len(full_corpus), len(full_corpus))
    run_record = build_run_record(
        manifest,
        logs,
        warnings,
        errors,
        len(full_corpus),
        preliminary_scope,
        compiled_pipeline["recipe_id"],
        compiled_pipeline["output_bundle_id"],
        describe_output_bundle(compiled_pipeline.get("export") or {}),
        active_workflow,
    )
    total_nodes = max(len(execution_order), 1)
    context = WorkflowExecutionContext(
        project_dir=project_dir,
        manifest=manifest,
        workflow_definition=active_workflow,
        compiled_pipeline=compiled_pipeline,
        full_corpus=full_corpus,
        logs=logs,
        warnings=warnings,
        errors=errors,
        run_id=run_record["run_id"],
        progress_callback=progress_callback,
        total_nodes=total_nodes,
    )

    incoming_by_port: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in active_edges:
        incoming_by_port[(str(edge.get("to_node") or ""), str(edge.get("to_port") or ""))].append(edge)

    update_log(logs, "system", f"本次执行节点：{', '.join(str(node.get('label') or node.get('node_type')) for node in execution_order)}")
    context.emit_runtime_progress(0.08, "正在准备原生 DAG 执行", stage="preparing", detail="正在准备原生 DAG 执行", force=True)
    notify_progress(progress_callback, 0.08, "正在准备原生 DAG 执行")

    node_states: dict[str, NodeExecutionState] = {}
    for index, node in enumerate(execution_order, start=1):
        node_id = str(node.get("node_id") or "")
        node_type = str(node.get("node_type") or "")
        definition = definition_map.get(node_type) or {}
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        executor = registry.executors.get(executor_id)
        if executor is None:
            raise ValueError(f"Missing executor for node type: {node_type}")

        input_payload: dict[str, Any] = {}
        input_hashes: dict[str, Any] = {}
        for port in node.get("inputs", []):
            if not isinstance(port, dict):
                continue
            port_id = str(port.get("port_id") or "")
            edges = incoming_by_port.get((node_id, port_id), [])
            if not edges:
                continue
            values = []
            source_hashes: list[str] = []
            for edge in edges:
                upstream_state = node_states.get(str(edge.get("from_node") or ""))
                if upstream_state is None:
                    continue
                from_port = str(edge.get("from_port") or "")
                values.append(upstream_state.outputs.get(from_port))
                source_hashes.append(str(upstream_state.output_hashes.get(from_port) or ""))
            if not values:
                continue
            input_payload[port_id] = values if bool(port.get("allow_multiple")) else values[-1]
            input_hashes[port_id] = source_hashes if bool(port.get("allow_multiple")) else source_hashes[-1]

        cacheable = bool(runtime.get("cacheable", False))
        cache_key = _node_cache_key(manifest, active_workflow, node, executor_id, input_hashes) if cacheable else None
        cached = _read_cache_payload(project_dir, node_id, cache_key) if cache_key else None
        start_clock = perf_counter()
        _, started_at = context.begin_node(node, index)

        try:
            if cached is not None:
                outputs, output_hashes, cache_path = cached
                state = NodeExecutionState(outputs=outputs, output_hashes=output_hashes, cache_hit=True, cache_key=cache_key, cache_path=cache_path)
            else:
                outputs = executor(context, node, input_payload)
                if not isinstance(outputs, dict):
                    outputs = {}
                normalized_outputs = _json_ready(outputs)
                output_port_types = {
                    str(port.get("port_id") or ""): str(port.get("port_type") or "")
                    for port in node.get("outputs", [])
                    if isinstance(port, dict)
                }
                output_hashes = {
                    str(port_id): _hash_port_value(output_port_types.get(str(port_id), ""), value)
                    for port_id, value in normalized_outputs.items()
                }
                cache_path = _write_cache_payload(project_dir, node_id, cache_key, normalized_outputs, output_hashes) if cache_key else None
                state = NodeExecutionState(
                    outputs=normalized_outputs,
                    output_hashes=output_hashes,
                    cache_hit=False,
                    cache_key=cache_key,
                    cache_path=cache_path,
                )
        except Exception as error:
            failed_state = NodeExecutionState(outputs={}, output_hashes={}, cache_hit=False, cache_key=cache_key, cache_path=None)
            context.finish_node(
                node,
                node_index=index,
                state=failed_state,
                started_at=started_at,
                start_clock=start_clock,
                status="failed",
                error=str(error),
            )
            raise
        node_states[node_id] = state

        for output_port in node.get("outputs", []):
            if not isinstance(output_port, dict):
                continue
            port_id = str(output_port.get("port_id") or "")
            port_type = str(output_port.get("port_type") or "")
            value = state.outputs.get(port_id)
            if port_type in CORPUS_PORT_TYPES:
                context.sync_corpus(value)
                if port_type == "FilteredTokenCorpus":
                    context.shared["filtered_corpus"] = value
                elif port_type == "TokenCorpus":
                    context.shared["token_corpus"] = value
                elif port_type == "NormalizedCorpus":
                    context.shared["normalized_corpus"] = value
                elif port_type == "CleanCorpus":
                    context.shared["clean_corpus"] = value
                else:
                    context.shared["scoped_corpus"] = value

        for output_port_id, result_key in _result_bundle_bindings(definition):
            context.result_bundle[result_key] = state.outputs.get(output_port_id) or []

        ended_at = utc_now_iso()
        output_summary, sample_outputs = _summarize_runtime_outputs(state.outputs)
        context.node_runs.append(
            {
                "node_id": node_id,
                "node_type": node_type,
                "label": str(node.get("label") or node_type),
                "status": "cached" if state.cache_hit else "completed",
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": round((perf_counter() - start_clock) * 1000, 3),
                "cache_hit": state.cache_hit,
                "cache_key": state.cache_key,
                "cache_path": state.cache_path,
                "output_ports": list(state.outputs.keys()),
                "output_summary": output_summary,
                "sample_outputs": sample_outputs,
            }
        )
        context.finish_node(
            node,
            node_index=index,
            state=state,
            started_at=started_at,
            start_clock=start_clock,
            status="cached" if state.cache_hit else "completed",
        )
        update_log(
            logs,
            _artifact_step_for_node(definition),
            f"节点 {node.get('label') or node_type} 已{'命中缓存' if state.cache_hit else '执行完成'}。",
        )

    scoped_corpus = context.shared.get("scoped_corpus")
    if not isinstance(scoped_corpus, list):
        scoped_corpus = full_corpus
    run_scope = compiled_pipeline.get("run_scope") or {}
    run_record["processed_document_count"] = len(scoped_corpus)
    run_record["run_scope_summary"] = context.shared.get("run_scope_summary") or describe_run_scope(run_scope, len(full_corpus), len(scoped_corpus))
    run_record["output_summary"] = describe_output_bundle(compiled_pipeline.get("export") or {})
    run_record["status"] = "completed" if not errors else "failed"
    run_record["ended_at"] = utc_now_iso()
    run_record["node_runs"] = context.node_runs

    export_enabled = "export" in set(compiled_pipeline.get("enabled_steps") or [])
    export_message = (
        "正在写出原生 DAG 运行快照与导出文件"
        if export_enabled
        else "导出步骤已禁用，仅写出运行快照文件。"
    )
    update_log(logs, "export", export_message)
    context.current_node_id = None
    context.emit_runtime_progress(0.94, "正在写出运行记录与导出文件", stage="exporting", detail=export_message, force=True)
    notify_progress(progress_callback, 0.94, "正在写出运行记录与导出文件")
    report_files = write_run_outputs(
        project_dir,
        run_record["run_id"],
        manifest,
        scoped_corpus,
        context.result_bundle,
        run_record,
        export_selection=export_selection,
        progress_callback=(
            (lambda fraction, message: notify_progress(progress_callback, min(0.995, 0.94 + fraction * 0.055), message))
            if progress_callback is not None
            else None
        ),
    )
    context.result_bundle["report_files"] = report_files

    snapshot_prefix = f"runs/{run_record['run_id']}"
    snapshot_files = [
        f"{snapshot_prefix}/params_snapshot.json",
        f"{snapshot_prefix}/logs.json",
        f"{snapshot_prefix}/logs.txt",
        f"{snapshot_prefix}/corpus_snapshot.json",
    ]

    step_artifacts: dict[str, dict[str, Any]] = defaultdict(lambda: {"output_files": [], "record_count": 0, "cache_hit": True})
    for node_run in context.node_runs:
        definition = registry.definitions_by_type.get(str(node_run["node_type"]) or "") or {}
        step = _artifact_step_for_node(definition)
        bucket = step_artifacts[step]
        if node_run.get("cache_path"):
            cache_path = Path(str(node_run["cache_path"]))
            try:
                bucket["output_files"].append(str(cache_path.relative_to(project_dir).as_posix()))
            except Exception:
                pass
        bucket["record_count"] += len(node_run.get("output_ports") or [])
        bucket["cache_hit"] = bool(bucket["cache_hit"] and node_run.get("cache_hit"))

    step_artifacts["export"]["output_files"].extend([*snapshot_files, *report_files])
    step_artifacts["export"]["record_count"] += len(report_files)
    step_artifacts["export"]["cache_hit"] = False
    run_record["artifacts"] = [
        {
            "step": step,
            "output_files": artifact["output_files"],
            "record_count": artifact["record_count"],
            "cache_hit": artifact["cache_hit"],
        }
        for step, artifact in step_artifacts.items()
        if artifact["output_files"] or artifact["record_count"]
    ]

    manifest["results"] = context.result_bundle
    manifest["updated_at"] = utc_now_iso()
    manifest.setdefault("run_history", []).append(run_record)
    context.current_node_id = None
    context.emit_runtime_progress(1.0, "本次原生 DAG 运行已完成", stage="completed", detail="本次原生 DAG 运行已完成", force=True)
    notify_progress(progress_callback, 1.0, "本次原生 DAG 运行已完成")
    return manifest, full_corpus, run_record
