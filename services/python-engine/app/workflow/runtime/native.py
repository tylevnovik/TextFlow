from __future__ import annotations

from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Any

from ...storage.artifacts import write_artifact
from ...defaults import (
    normalize_workflow_edges,
    utc_now_iso,
    workflow_active_node_ids_from_sinks,
    workflow_reachable_node_ids,
)
from .incremental import (
    build_dependency_index,
    compute_dirty_node_ids,
    detect_changed_doc_ids,
    invalidate_artifacts_for_dirty_nodes,
    select_incremental_scope,
    update_incremental_state,
)
from ..registry import build_node_registry
from ...reporting import result_bundle_table_entries, write_run_outputs

# Imports from restructured submodules
from .context import (
    NodeExecutionState,
    PreparedNodeExecution,
    ExecutedNodeResult,
    WorkflowExecutionContext,
    _copy_corpus_rows,
    _summarize_runtime_outputs,
)
from .previews import _preview_runtime_outputs
from .cache import (
    _read_cache_payload,
    _write_cache_payload,
    _node_cache_enabled,
    _node_cache_key,
    _hash_port_value,
)
from .artifacts import (
    _result_bundle_bindings,
    _result_bundle_binding_map,
    _artifact_kind_for_result_value,
    _explicit_artifact_output_bindings,
    _export_selection_from_active_graph,
    _audit_requested,
    _artifact_step_for_node,
)
from .scheduler import (
    _topological_active_node_batches,
    _node_runtime_parallel_safe,
    dag_parallel_worker_count,
    supports_native_execution,
)
from .support import (
    build_artifact_handle,
    build_run_record,
    describe_output_bundle,
    describe_run_scope,
    notify_progress,
    select_active_workflow,
    update_log,
    workflow_runtime_profile,
)

UTILITY_NODE_TYPES = {"note", "group"}


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
    registry: Any,
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
        from .previews import _json_ready
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

    CORPUS_PORT_TYPES = {
        "CorpusTable",
        "ProjectCorpus",
        "ScopedCorpus",
        "CleanCorpus",
        "NormalizedCorpus",
        "TokenCorpus",
        "FilteredTokenCorpus",
    }

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
    output_previews = _preview_runtime_outputs(state.outputs)
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
            "output_previews": output_previews,
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

    db_path = project_dir / "project.db"
    if db_path.exists():
        from ...storage.database import clear_artifacts_except_run, initialize_project_database

        db = initialize_project_database(db_path)
        cleared = clear_artifacts_except_run(db, run_record["run_id"])
        if cleared:
            context.log({}, f"已清理 {cleared} 条历史 artifact 记录")

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
    manifest["artifact_records"] = run_artifact_records

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
