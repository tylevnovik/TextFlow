from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
import gzip
import hashlib
import json
import os
import pickle
from pathlib import Path
import threading
from time import perf_counter
from typing import Any

import numpy as np

from .artifact_store import write_artifact
from .defaults import (
    empty_result_bundle,
    normalize_workflow_edges,
    utc_now_iso,
    workflow_active_node_ids_from_sinks,
    workflow_reachable_node_ids,
    workflow_payload_hash,
)
from .incremental_runtime import (
    build_dependency_index,
    compute_dirty_node_ids,
    detect_changed_doc_ids,
    invalidate_artifacts_for_dirty_nodes,
    select_incremental_scope,
    update_incremental_state,
)
from .node_registry import NodeRegistry, build_node_registry
from .reporting import result_bundle_table_entries, write_run_outputs
from .runtime_support import (
    build_artifact_handle,
    build_run_record,
    describe_output_bundle,
    describe_run_scope,
    dispatch_progress_callback,
    notify_progress,
    select_active_workflow,
    update_log,
    workflow_runtime_profile,
)

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
DEFAULT_DAG_PARALLEL_WORKERS = 4


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
        encoded = json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.pkl"


def _legacy_json_cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.json"


def _legacy_gzip_cache_payload_path(project_dir: Path, node_id: str, cache_key: str) -> Path:
    return project_dir / "cache" / "nodes" / node_id / f"{cache_key}.json.gz"


def _write_cache_payload(project_dir: Path, node_id: str, cache_key: str, outputs: dict[str, Any], output_hashes: dict[str, str]) -> str:
    cache_path = _cache_payload_path(project_dir, node_id, cache_key)
    payload = {
        "node_id": node_id,
        "cache_key": cache_key,
        "created_at": utc_now_iso(),
        "outputs": outputs,
        "output_hashes": output_hashes,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return str(cache_path)


def _read_cache_payload(project_dir: Path, node_id: str, cache_key: str) -> tuple[dict[str, Any], dict[str, str], str] | None:
    cache_path = _cache_payload_path(project_dir, node_id, cache_key)
    if cache_path.exists():
        with cache_path.open("rb") as handle:
            payload = pickle.load(handle)
    else:
        legacy_cache_path = _legacy_json_cache_payload_path(project_dir, node_id, cache_key)
        if not legacy_cache_path.exists():
            legacy_cache_path = _legacy_gzip_cache_payload_path(project_dir, node_id, cache_key)
            if not legacy_cache_path.exists():
                return None
            with gzip.open(legacy_cache_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            cache_path = legacy_cache_path
        else:
            payload = _read_json_file(legacy_cache_path)
            cache_path = legacy_cache_path
    outputs = payload.get("outputs") if isinstance(payload, dict) else None
    output_hashes = payload.get("output_hashes") if isinstance(payload, dict) else None
    if not isinstance(outputs, dict) or not isinstance(output_hashes, dict):
        return None
    return outputs, {str(key): str(value) for key, value in output_hashes.items()}, str(cache_path)


def _node_cache_enabled(node: dict[str, Any], definition: dict[str, Any]) -> bool:
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    if not bool(runtime.get("cacheable", False)):
        return False
    runtime_meta = node.get("runtime_meta") if isinstance(node.get("runtime_meta"), dict) else {}
    cache_override = runtime_meta.get("cache_enabled")
    if cache_override is None:
        return True
    return bool(cache_override)


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
        "workflow_hash": workflow_payload_hash(workflow_definition),
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
        definition = definition_map.get(node_type)
        if not isinstance(definition, dict):
            return False
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        if executor_id not in registry.executors:
            return False
    return True

def _topological_active_node_batches(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    node_lookup = {str(node.get("node_id") or ""): node for node in nodes}
    node_order = {
        str(node.get("node_id") or ""): index
        for index, node in enumerate(nodes)
        if node.get("node_id")
    }
    indegree = {node_id: 0 for node_id in node_lookup}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        from_node_id = str(edge.get("from_node") or "")
        to_node_id = str(edge.get("to_node") or "")
        if from_node_id not in node_lookup or to_node_id not in node_lookup:
            continue
        outgoing[from_node_id].append(to_node_id)
        indegree[to_node_id] += 1

    ready = sorted(
        [node_id for node_id, degree in indegree.items() if degree == 0],
        key=lambda node_id: node_order.get(node_id, 0),
    )
    batches: list[list[dict[str, Any]]] = []
    order_count = 0
    while ready:
        current_batch = list(ready)
        batches.append([node_lookup[node_id] for node_id in current_batch])
        order_count += len(current_batch)
        next_ready: list[str] = []
        for node_id in current_batch:
            for target_id in sorted(outgoing.get(node_id, []), key=lambda item: node_order.get(item, 0)):
                indegree[target_id] -= 1
                if indegree[target_id] == 0:
                    next_ready.append(target_id)
        ready = sorted(next_ready, key=lambda node_id: node_order.get(node_id, 0))
    if order_count != len(node_lookup):
        raise ValueError("Workflow graph contains an unsupported cycle")
    return batches


def _topological_active_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches = _topological_active_node_batches(nodes, edges)
    return [node for batch in batches for node in batch]


def _node_runtime_parallel_safe(definition: dict[str, Any]) -> bool:
    runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
    if "parallel_safe" in runtime:
        return bool(runtime.get("parallel_safe"))
    category = str(definition.get("category") or "")
    node_type = str(definition.get("type") or "")
    return category in {"analysis", "output"} and node_type not in {"analyze_corpus", "export_results"}


def dag_parallel_worker_count(
    nodes: list[dict[str, Any]],
    definitions_by_type: dict[str, dict[str, Any]],
) -> int:
    if os.environ.get("TEXTFLOW_DISABLE_DAG_PARALLEL") == "1":
        return 1

    override = os.environ.get("TEXTFLOW_DAG_WORKERS")
    if override is not None:
        try:
            requested = max(1, int(override))
        except ValueError:
            requested = 1
        parallel_candidates = sum(
            1
            for node in nodes
            if _node_runtime_parallel_safe(definitions_by_type.get(str(node.get("node_type") or ""), {}))
        )
        return max(1, min(requested, max(parallel_candidates, 1)))

    cpu_count = os.cpu_count() or 1
    if cpu_count <= 1:
        return 1
    parallel_candidates = sum(
        1
        for node in nodes
        if _node_runtime_parallel_safe(definitions_by_type.get(str(node.get("node_type") or ""), {}))
    )
    if parallel_candidates < 2:
        return 1
    return max(1, min(parallel_candidates, min(DEFAULT_DAG_PARALLEL_WORKERS, cpu_count)))


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


def _result_bundle_binding_map(
    workflow_definition: dict[str, Any],
    registry: NodeRegistry,
) -> dict[str, tuple[str, str]]:
    bindings: dict[str, tuple[str, str]] = {}
    for node in workflow_definition.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "")
        node_type = str(node.get("node_type") or "")
        if not node_id or not node_type:
            continue
        definition = registry.definitions_by_type.get(node_type) or {}
        for _port_id, result_key in _result_bundle_bindings(definition):
            bindings[result_key] = (node_id, node_type)
    return bindings


def _artifact_kind_for_result_value(value: Any) -> str | None:
    if isinstance(value, list):
        return "table"
    if isinstance(value, dict):
        return "object"
    return None


def _explicit_artifact_output_bindings(definition: dict[str, Any]) -> list[tuple[str, str]]:
    outputs = definition.get("outputs") if isinstance(definition.get("outputs"), list) else []
    bindings: list[tuple[str, str]] = []
    for output_port in outputs:
        if not isinstance(output_port, dict):
            continue
        port_id = str(output_port.get("port_id") or "")
        artifact_kind = str(output_port.get("artifact_kind") or output_port.get("artifact_output_kind") or "")
        if port_id and artifact_kind:
            bindings.append((port_id, artifact_kind))
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
        sink_config = to_node.get("config") if isinstance(to_node.get("config"), dict) else {}
        include_sink_audit = bool(sink_config.get("include_audit", True))
        if sink_type == "save_csv" and result_key:
            selection["csv_tables"].add(result_key)
        if sink_type == "save_xlsx" and result_key:
            selection["xlsx_tables"].add(result_key)
        if sink_type == "save_png":
            selection["png_charts"].update(_png_chart_ids_for_output_port(source_definition, source_port_id))
        if sink_type == "save_html_report":
            if result_key and not _include_output_in_html_audit(source_definition, source_port_id):
                selection["html_result_keys"].add(result_key)
            if include_sink_audit and _include_output_in_html_audit(source_definition, source_port_id):
                selection["include_audit"].add("audit")
    return selection


def _audit_requested(export_selection: dict[str, set[str]]) -> bool:
    return any(
        (
            "audit" in set(export_selection.get("include_audit") or set()),
            "audit_table" in set(export_selection.get("csv_tables") or set()),
            "audit_table" in set(export_selection.get("xlsx_tables") or set()),
            "audit_table" in set(export_selection.get("html_result_keys") or set()),
        )
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
            # The desktop shell polls the latest task snapshot instead of consuming
            # every intermediate progress event. Emit the full runtime state on
            # every update so fast node transitions do not lose completion status.
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


def _prepare_node_execution(
    *,
    project_dir: Path,
    manifest: dict[str, Any],
    workflow_definition: dict[str, Any],
    node: dict[str, Any],
    node_index: int,
    node_states: dict[str, NodeExecutionState],
    incoming_by_port: dict[tuple[str, str], list[dict[str, Any]]],
    definition_map: dict[str, dict[str, Any]],
    registry: NodeRegistry,
    dirty_node_ids: set[str] | None = None,
) -> PreparedNodeExecution:
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

    cacheable = _node_cache_enabled(node, definition)
    cache_key = _node_cache_key(manifest, workflow_definition, node, executor_id, input_hashes) if cacheable else None
    cached = None if node_id in (dirty_node_ids or set()) else (_read_cache_payload(project_dir, node_id, cache_key) if cache_key else None)
    return PreparedNodeExecution(
        node=node,
        node_index=node_index,
        node_id=node_id,
        node_type=node_type,
        definition=definition,
        executor=executor,
        input_payload=input_payload,
        cache_key=cache_key,
        cached=cached,
    )


def _execute_prepared_node(
    context: WorkflowExecutionContext,
    prepared: PreparedNodeExecution,
    started_at: str,
    start_clock: float,
) -> ExecutedNodeResult:
    try:
        if prepared.cached is not None:
            outputs, output_hashes, cache_path = prepared.cached
            state = NodeExecutionState(
                outputs=outputs,
                output_hashes=output_hashes,
                cache_hit=True,
                cache_key=prepared.cache_key,
                cache_path=cache_path,
            )
            return ExecutedNodeResult(prepared=prepared, state=state, started_at=started_at, start_clock=start_clock)

        outputs = prepared.executor(context, prepared.node, prepared.input_payload)
        if not isinstance(outputs, dict):
            outputs = {}
        normalized_outputs = _json_ready(outputs)
        output_port_types = {
            str(port.get("port_id") or ""): str(port.get("port_type") or "")
            for port in prepared.node.get("outputs", [])
            if isinstance(port, dict)
        }
        output_hashes = {
            str(port_id): _hash_port_value(output_port_types.get(str(port_id), ""), value)
            for port_id, value in normalized_outputs.items()
        }
        cache_path = (
            _write_cache_payload(context.project_dir, prepared.node_id, prepared.cache_key, normalized_outputs, output_hashes)
            if prepared.cache_key
            else None
        )
        state = NodeExecutionState(
            outputs=normalized_outputs,
            output_hashes=output_hashes,
            cache_hit=False,
            cache_key=prepared.cache_key,
            cache_path=cache_path,
        )
        return ExecutedNodeResult(prepared=prepared, state=state, started_at=started_at, start_clock=start_clock)
    except Exception as error:  # pragma: no cover - exercised through integration tests
        failed_state = NodeExecutionState(
            outputs={},
            output_hashes={},
            cache_hit=False,
            cache_key=prepared.cache_key,
            cache_path=None,
        )
        return ExecutedNodeResult(
            prepared=prepared,
            state=failed_state,
            started_at=started_at,
            start_clock=start_clock,
            error=error,
        )


def _record_completed_node(
    context: WorkflowExecutionContext,
    logs: list[dict[str, Any]],
    node_states: dict[str, NodeExecutionState],
    executed: ExecutedNodeResult,
) -> None:
    prepared = executed.prepared
    state = executed.state
    node_states[prepared.node_id] = state

    for output_port in prepared.node.get("outputs", []):
        if not isinstance(output_port, dict):
            continue
        port_id = str(output_port.get("port_id") or "")
        port_type = str(output_port.get("port_type") or "")
        value = state.outputs.get(port_id)
        if port_type in CORPUS_PORT_TYPES:
            context.sync_corpus(value)
            if port_type == "FilteredTokenCorpus":
                context.set_shared_value("filtered_corpus", value)
            elif port_type == "TokenCorpus":
                context.set_shared_value("token_corpus", value)
            elif port_type == "NormalizedCorpus":
                context.set_shared_value("normalized_corpus", value)
            elif port_type == "CleanCorpus":
                context.set_shared_value("clean_corpus", value)
            else:
                context.set_shared_value("scoped_corpus", value)

    for output_port_id, result_key in _result_bundle_bindings(prepared.definition):
        context.result_bundle[result_key] = state.outputs.get(output_port_id) or []

    ended_at = utc_now_iso()
    output_summary, sample_outputs = _summarize_runtime_outputs(state.outputs)
    context.node_runs.append(
        {
            "node_id": prepared.node_id,
            "node_type": prepared.node_type,
            "label": str(prepared.node.get("label") or prepared.node_type),
            "status": "cached" if state.cache_hit else "completed",
            "started_at": executed.started_at,
            "ended_at": ended_at,
            "duration_ms": round((perf_counter() - executed.start_clock) * 1000, 3),
            "cache_hit": state.cache_hit,
            "cache_key": state.cache_key,
            "cache_path": state.cache_path,
            "output_ports": list(state.outputs.keys()),
            "output_summary": output_summary,
            "sample_outputs": sample_outputs,
        }
    )
    context.finish_node(
        prepared.node,
        node_index=prepared.node_index,
        state=state,
        started_at=executed.started_at,
        start_clock=executed.start_clock,
        status="cached" if state.cache_hit else "completed",
    )
    update_log(
        logs,
        _artifact_step_for_node(prepared.definition),
        f"节点 {prepared.node.get('label') or prepared.node_type} 已{'命中缓存' if state.cache_hit else '执行完成'}。",
    )


def _record_failed_node(context: WorkflowExecutionContext, executed: ExecutedNodeResult) -> None:
    prepared = executed.prepared
    context.finish_node(
        prepared.node,
        node_index=prepared.node_index,
        state=executed.state,
        started_at=executed.started_at,
        start_clock=executed.start_clock,
        status="failed",
        error=str(executed.error) if executed.error is not None else "节点执行失败",
    )


def run_project_workflow_native(
    project_dir: Path,
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    progress_callback: Any = None,
    run_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    project_corpus = _copy_corpus_rows(corpus)
    run_options_payload = dict(run_options or {})
    if str(run_options_payload.get("run_mode") or "").lower() == "incremental" and not run_options_payload.get("changed_doc_ids"):
        detected_doc_ids = detect_changed_doc_ids(manifest, project_corpus)
        if detected_doc_ids:
            run_options_payload["changed_doc_ids"] = detected_doc_ids
    incremental_scope = select_incremental_scope(manifest, run_options_payload)
    scope_doc_ids = set(incremental_scope.get("scope_doc_ids", []))
    full_corpus = [
        item
        for item in project_corpus
        if not scope_doc_ids or str(item.get("doc_id") or item.get("id") or "") in scope_doc_ids
    ]
    logs: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    registry = build_node_registry()
    active_workflow = select_active_workflow(manifest)
    runtime_profile = workflow_runtime_profile(active_workflow)

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
    execution_batches = _topological_active_node_batches(selected_nodes, active_edges)
    execution_order = [node for batch in execution_batches for node in batch]
    node_index_by_id = {
        str(node.get("node_id") or ""): index
        for index, node in enumerate(execution_order, start=1)
        if node.get("node_id")
    }
    export_selection = _export_selection_from_active_graph(selected_node_lookup, active_edges, definition_map)
    dependency_index = build_dependency_index(active_workflow)
    dirty_node_ids = (
        compute_dirty_node_ids(active_workflow, incremental_scope, dependency_index)
        if incremental_scope.get("run_mode") == "incremental"
        else set()
    )

    preliminary_scope = describe_run_scope(runtime_profile["run_scope"], len(full_corpus), len(full_corpus))
    run_record = build_run_record(
        manifest,
        logs,
        warnings,
        errors,
        len(full_corpus),
        preliminary_scope,
        runtime_profile["recipe_id"],
        runtime_profile["output_bundle_id"],
        describe_output_bundle(runtime_profile.get("export") or {}),
        active_workflow,
    )
    run_record["run_mode"] = incremental_scope["run_mode"]
    run_record["incremental_scope"] = incremental_scope
    run_record["dirty_node_ids"] = sorted(dirty_node_ids)
    total_nodes = max(len(execution_order), 1)
    context = WorkflowExecutionContext(
        project_dir=project_dir,
        manifest=manifest,
        workflow_definition=active_workflow,
        runtime_profile=runtime_profile,
        full_corpus=full_corpus,
        logs=logs,
        warnings=warnings,
        errors=errors,
        run_id=run_record["run_id"],
        progress_callback=progress_callback,
        total_nodes=total_nodes,
        audit_enabled=_audit_requested(export_selection),
    )

    incoming_by_port: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in active_edges:
        incoming_by_port[(str(edge.get("to_node") or ""), str(edge.get("to_port") or ""))].append(edge)

    update_log(logs, "system", f"本次执行节点：{', '.join(str(node.get('label') or node.get('node_type')) for node in execution_order)}")
    dag_workers = dag_parallel_worker_count(execution_order, definition_map)
    if dag_workers > 1:
        update_log(logs, "system", f"原生 DAG 调度已启用并行执行，最多 {dag_workers} 个节点工作线程。")
    else:
        update_log(logs, "system", "原生 DAG 调度当前以串行模式执行节点。")
    context.emit_runtime_progress(0.08, "正在准备原生 DAG 执行", stage="preparing", detail="正在准备原生 DAG 执行", force=True)
    notify_progress(progress_callback, 0.08, "正在准备原生 DAG 执行")

    node_states: dict[str, NodeExecutionState] = {}
    parallel_executor = (
        ThreadPoolExecutor(max_workers=dag_workers, thread_name_prefix="textflow-dag")
        if dag_workers > 1
        else None
    )
    try:
        for batch in execution_batches:
            prepared_batch = [
                _prepare_node_execution(
                    project_dir=project_dir,
                    manifest=manifest,
                    workflow_definition=active_workflow,
                    node=node,
                    node_index=node_index_by_id[str(node.get("node_id") or "")],
                    node_states=node_states,
                    incoming_by_port=incoming_by_port,
                    definition_map=definition_map,
                    registry=registry,
                    dirty_node_ids=dirty_node_ids,
                )
                for node in batch
            ]
            cached_batch = [
                prepared
                for prepared in prepared_batch
                if prepared.cached is not None
            ]
            serial_batch = [
                prepared
                for prepared in prepared_batch
                if prepared.cached is None and (dag_workers <= 1 or not _node_runtime_parallel_safe(prepared.definition))
            ]
            parallel_batch = [
                prepared
                for prepared in prepared_batch
                if prepared.cached is None and dag_workers > 1 and _node_runtime_parallel_safe(prepared.definition)
            ]

            for prepared in cached_batch:
                start_clock = perf_counter()
                started_at = utc_now_iso()
                executed = _execute_prepared_node(context, prepared, started_at, start_clock)
                if executed.error is not None:
                    _record_failed_node(context, executed)
                    raise executed.error
                _record_completed_node(context, logs, node_states, executed)

            for prepared in serial_batch:
                start_clock = perf_counter()
                _, started_at = context.begin_node(prepared.node, prepared.node_index)
                executed = _execute_prepared_node(context, prepared, started_at, start_clock)
                if executed.error is not None:
                    _record_failed_node(context, executed)
                    raise executed.error
                _record_completed_node(context, logs, node_states, executed)

            if parallel_batch:
                futures: list[Future[ExecutedNodeResult]] = []
                for prepared in parallel_batch:
                    start_clock = perf_counter()
                    _, started_at = context.begin_node(prepared.node, prepared.node_index)
                    future = parallel_executor.submit(_execute_prepared_node, context, prepared, started_at, start_clock) if parallel_executor else None
                    if future is None:
                        continue
                    futures.append(future)

                executed_results = [future.result() for future in futures]
                executed_results.sort(key=lambda executed: executed.prepared.node_index)
                failed_results: list[ExecutedNodeResult] = []
                for executed in executed_results:
                    if executed.error is not None:
                        _record_failed_node(context, executed)
                        failed_results.append(executed)
                        continue
                    _record_completed_node(context, logs, node_states, executed)
                if failed_results:
                    raise failed_results[0].error or RuntimeError("并行节点执行失败")
    finally:
        if parallel_executor is not None:
            parallel_executor.shutdown(wait=True, cancel_futures=False)

    selected_analysis_outputs = [
        str(node.get("label") or node.get("node_type") or "")
        for node in execution_order
        if str(((definition_map.get(str(node.get("node_type") or "")) or {}).get("category") or "")) == "analysis"
    ]
    if selected_analysis_outputs:
        update_log(logs, "analysis", f"已按节点选择生成分析结果：{', '.join(selected_analysis_outputs)}。")
    else:
        update_log(logs, "analysis", "分析步骤已禁用，未生成分析结果。")

    scoped_corpus = context.shared.get("scoped_corpus")
    if not isinstance(scoped_corpus, list):
        scoped_corpus = full_corpus
    run_scope = runtime_profile.get("run_scope") or {}
    run_record["processed_document_count"] = len(scoped_corpus)
    run_record["run_scope_summary"] = context.shared.get("run_scope_summary") or describe_run_scope(run_scope, len(full_corpus), len(scoped_corpus))
    run_record["output_summary"] = describe_output_bundle(runtime_profile.get("export") or {})
    run_record["status"] = "completed" if not errors else "failed"
    run_record["ended_at"] = utc_now_iso()
    run_record["node_runs"] = context.node_runs

    export_enabled = "export" in set(runtime_profile.get("enabled_steps") or [])
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
        active_workflow,
        runtime_profile,
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

    result_binding_map = _result_bundle_binding_map(active_workflow, registry)
    run_artifact_records: list[dict[str, Any]] = []
    for result_key, value in result_bundle_table_entries(context.result_bundle):
        artifact_kind = _artifact_kind_for_result_value(value)
        if artifact_kind is None:
            continue
        node_id, _node_type = result_binding_map.get(result_key, ("workflow-result", result_key))
        run_artifact_records.append(
            write_artifact(
                project_dir,
                run_record["run_id"],
                node_id,
                artifact_kind,
                value,
            )
        )
    for node in active_workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "")
        node_type = str(node.get("node_type") or "")
        state = node_states.get(node_id)
        definition = definition_map.get(node_type) or {}
        if not state:
            continue
        for port_id, artifact_kind in _explicit_artifact_output_bindings(definition):
            if port_id not in state.outputs:
                continue
            run_artifact_records.append(
                write_artifact(
                    project_dir,
                    run_record["run_id"],
                    node_id,
                    artifact_kind,
                    state.outputs.get(port_id),
                )
            )
    run_record["artifacts"] = [build_artifact_handle(record) for record in run_artifact_records]
    run_record["invalidated_artifact_count"] = invalidate_artifacts_for_dirty_nodes(
        manifest,
        dirty_node_ids,
        current_run_id=run_record["run_id"],
    )
    existing_artifacts = [
        deepcopy(item)
        for item in manifest.get("artifact_records", [])
        if isinstance(item, dict) and str(item.get("run_id") or "") != run_record["run_id"]
    ]
    manifest["artifact_records"] = [*existing_artifacts, *run_artifact_records]

    manifest["results"] = context.result_bundle
    manifest["updated_at"] = utc_now_iso()
    update_incremental_state(manifest, project_corpus, run_record, dirty_node_ids, incremental_scope)
    manifest.setdefault("run_history", []).append(run_record)
    context.current_node_id = None
    context.emit_runtime_progress(
        1.0,
        "本次原生 DAG 运行已完成",
        stage="completed",
        detail="本次原生 DAG 运行已完成",
        force=True,
        full_node_state_sync=True,
    )
    notify_progress(progress_callback, 1.0, "本次原生 DAG 运行已完成")
    return manifest, project_corpus, run_record
